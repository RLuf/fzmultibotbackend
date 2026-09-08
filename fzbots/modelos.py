"""Modelos GGUF no disco: listar, estimar VRAM (lendo o cabeçalho GGUF), sugerir
flags otimizadas e baixar do Hugging Face. Tudo stdlib."""
from __future__ import annotations

import pathlib
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import config as C

RE_QUANT = re.compile(r"(IQ[1-4]_[A-Z0-9_]+|Q[2-8]_[A-Z0-9_]+|Q[2-8]|F16|BF16|F32)", re.I)

# ------------------------------------------------------------- GGUF header

_TIPOS = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?",
          10: "Q", 11: "q", 12: "d"}
_TAM = {"B": 1, "b": 1, "H": 2, "h": 2, "I": 4, "i": 4, "f": 4, "?": 1, "Q": 8, "q": 8, "d": 8}


class _Leitor:
    def __init__(self, f):
        self.f = f

    def u(self, fmt: str):
        return struct.unpack("<" + fmt, self.f.read(_TAM[fmt]))[0]

    def string(self) -> str:
        n = self.u("Q")
        return self.f.read(n).decode("utf-8", errors="replace")

    def valor(self, tipo: int):
        if tipo == 8:
            return self.string()
        if tipo == 9:
            sub = self.u("I"); n = self.u("Q")
            if n > 50000:            # vocabulários enormes: pula sem materializar
                if sub in _TIPOS:    # subtipo de tamanho fixo → seek direto
                    self.f.seek(n * _TAM[_TIPOS[sub]], 1)
                else:                # strings/arrays: precisa andar elemento a elemento
                    for _ in range(n):
                        self.valor(sub)
                return None
            return [self.valor(sub) for _ in range(n)]
        return self.u(_TIPOS[tipo])


def gguf_meta(path: pathlib.Path, chaves_interesse: tuple[str, ...] = (
        "general.architecture", "general.name", ".block_count", ".embedding_length",
        ".attention.head_count", ".attention.head_count_kv", ".context_length")) -> dict:
    """Lê só os metadados (KV) do cabeçalho GGUF. Retorna {} se não for GGUF."""
    meta: dict = {}
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return meta
            r = _Leitor(f)
            versao = r.u("I")
            if versao < 2:
                return meta
            r.u("Q")                     # nº de tensores
            n_kv = r.u("Q")
            for _ in range(n_kv):
                k = r.string()
                t = r.u("I")
                v = r.valor(t)
                if any(k == c or k.endswith(c) for c in chaves_interesse):
                    meta[k] = v
    except (OSError, struct.error, KeyError, UnicodeDecodeError):
        return meta
    return meta


def _campo(meta: dict, sufixo: str):
    for k, v in meta.items():
        if k.endswith(sufixo):
            return v
    return None


RE_SHARD = re.compile(r"^(.*)-(\d{5})-of-(\d{5})\.gguf$")


def shards(path: pathlib.Path) -> list[pathlib.Path]:
    """Arquivos irmãos de um modelo particionado (-00001-of-00003.gguf); [path] se não for."""
    m = RE_SHARD.match(path.name)
    if not m:
        return [path]
    base, _, total = m.groups()
    return [path.parent / f"{base}-{i:05d}-of-{total}.gguf" for i in range(1, int(total) + 1)]


def tamanho_total(path: pathlib.Path) -> float:
    """GB de todos os shards (o llama-server carrega os irmãos sozinho)."""
    return sum(s.stat().st_size for s in shards(path) if s.is_file()) / 1024**3


def estimar_vram(path: pathlib.Path, ctx: int = 4096, kv_bytes: int = 2, meta: dict | None = None) -> tuple[float, str]:
    """(GB, explicação). Pesos = tamanho do(s) arquivo(s); KV = 2 × camadas × ctx × dim_kv × kv_bytes
    (2 = f16, 1 = q8_0)."""
    tam = tamanho_total(path)
    meta = gguf_meta(path) if meta is None else meta
    camadas = _campo(meta, ".block_count")
    emb = _campo(meta, ".embedding_length")
    heads = _campo(meta, ".attention.head_count")
    heads_kv = _campo(meta, ".attention.head_count_kv") or heads
    if camadas and emb and heads:
        dim_kv = emb / heads * heads_kv
        kv = 2 * camadas * ctx * dim_kv * kv_bytes / 1024**3
        total = tam * 1.03 + kv + 0.15
        return round(total, 2), (f"pesos {tam:.2f} GB + KV {'q8_0' if kv_bytes == 1 else 'f16'} {kv:.2f} GB (ctx {ctx}, "
                                 f"{camadas} camadas, {int(heads_kv)} heads kv) + ~0,15 GB de buffers")
    return round(tam * 1.2 + 0.15, 2), f"pesos {tam:.2f} GB × 1,2 (cabeçalho GGUF não lido) + 0,15 GB"


# ------------------------------------------------------------- listar

@dataclass
class Modelo:
    path: pathlib.Path
    nome: str
    tamanho_gb: float
    quant: str
    arquitetura: str
    ctx_max: int | None
    bots: list[str] = field(default_factory=list)
    vram_est: float = 0.0
    vram_explica: str = ""


def listar(cfg: dict, ctx: int = 4096) -> list[Modelo]:
    raiz = pathlib.Path(cfg["modelos_dir"])
    usados: dict[str, list[str]] = {}
    for b in cfg["bots"]:
        usados.setdefault(str(pathlib.Path(b["modelo"]).resolve()), []).append(b["nome"])
    res = []
    if not raiz.is_dir():
        return res
    for p in sorted(raiz.rglob("*.gguf")):
        if not p.is_file():
            continue
        m = RE_SHARD.match(p.name)
        if m and m.group(2) != "00001":      # shards 2..N ficam agrupados no primeiro
            continue
        meta = gguf_meta(p)
        q = RE_QUANT.search(p.name)
        est, exp = estimar_vram(p, ctx, meta=meta)
        res.append(Modelo(
            path=p, nome=str(p.relative_to(raiz)) + (f" (+{int(m.group(3)) - 1} shards)" if m else ""),
            tamanho_gb=round(tamanho_total(p), 2),
            quant=(q.group(1).upper() if q else "?"),
            arquitetura=str(meta.get("general.architecture") or "?"),
            ctx_max=_campo(meta, ".context_length"),
            bots=usados.get(str(p.resolve()), []), vram_est=est, vram_explica=exp))
    return res


# ------------------------------------------------------------- flags otimizadas

ARQS_EMBEDDING = ("bert", "nomic-bert", "jina-bert", "gemma-embedding", "xlm-roberta")


def eh_embedding(path: pathlib.Path, meta: dict | None = None) -> bool:
    """Arquitetura do GGUF primeiro; nome do arquivo como fallback."""
    meta = gguf_meta(path) if meta is None else meta
    arq = str(meta.get("general.architecture") or "").lower()
    if arq:
        return arq in ARQS_EMBEDDING or arq.endswith("-embedding")
    n = path.name.lower()
    return any(x in n for x in ("embed", "bge-", "gte-", "e5-"))


def perfil_flags(path: pathlib.Path, ctx: int, vram_livre_gb: float, embedding: bool | None = None,
                 alias: str | None = None) -> tuple[str, str]:
    """(extra_args, explicação). Regras simples e verificáveis para o llama-server."""
    if alias and any(c.isspace() for c in alias):
        raise ValueError("alias com espaço não é suportado na unit")
    kv_bytes = 1 if ctx >= 8192 else 2          # a decisão de caber usa o KV que as flags vão pedir
    est, exp = estimar_vram(path, ctx, kv_bytes=kv_bytes)
    if embedding is None:
        embedding = eh_embedding(path)
    flags, por = [], []
    if est <= vram_livre_gb:
        flags.append("-ngl 99"); por.append(f"cabe inteiro na GPU ({est:.2f} ≤ {vram_livre_gb:.2f} GB livres)")
    else:
        flags.append("--fit on"); por.append(f"não cabe inteiro ({est:.2f} > {vram_livre_gb:.2f} GB): --fit divide GPU/CPU")
    flags.append(f"-c {ctx}")
    flags.append("-fa on"); por.append("flash attention: menos VRAM no KV e mais rápido")
    if embedding:
        flags += ["--embedding", f"-b {ctx}", f"-ub {ctx}"]
        por.append("embedding: batch lógico e físico iguais à janela (senão o servidor cai para 512)")
    else:
        if ctx >= 8192:
            flags += ["-ctk q8_0", "-ctv q8_0"]; por.append("ctx ≥ 8192: KV em q8_0 corta o cache pela metade")
        flags.append("--jinja"); por.append("--jinja: usa o template de chat do próprio modelo")
    if alias:
        flags.append(f"--alias {alias}")
    return " ".join(flags), f"VRAM estimada {est:.2f} GB ({exp}). " + "; ".join(por)


# ------------------------------------------------------------- download

def hf_listar(repo: str) -> list[str]:
    """Arquivos .gguf de um repo do Hugging Face (API pública)."""
    url = f"https://huggingface.co/api/models/{urllib.parse.quote(repo, safe='/')}"
    import json
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read().decode())
    return sorted(s["rfilename"] for s in d.get("siblings", []) if s["rfilename"].endswith(".gguf"))


def baixar(cfg: dict, repo: str, arquivo: str, progresso=None) -> pathlib.Path:
    """Baixa https://huggingface.co/<repo>/resolve/main/<arquivo> para modelos_dir/<repo-nome>/.
    progresso(bytes_baixados, total_ou_None) é chamado a cada bloco."""
    raiz = pathlib.Path(cfg["modelos_dir"])
    rel = pathlib.PurePosixPath(arquivo)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"nome de arquivo inválido: {arquivo}")
    destino = raiz / repo.split("/")[-1] / pathlib.Path(*rel.parts)   # preserva a subpasta do repo
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(arquivo)}"
    parcial = destino.with_suffix(destino.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "fzbots"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(parcial, "wb") as f:
            total = r.headers.get("Content-Length")
            total = int(total) if total else None
            feito, ultimo = 0, 0.0
            while True:
                bloco = r.read(1024 * 1024)
                if not bloco:
                    break
                f.write(bloco)
                feito += len(bloco)
                if progresso and (time.time() - ultimo > 0.5 or feito == total):
                    progresso(feito, total); ultimo = time.time()
        parcial.replace(destino)
    except BaseException:          # erro de rede ou Ctrl-C: não deixa .part para trás
        parcial.unlink(missing_ok=True)
        raise
    if progresso:
        progresso(feito, total)
    return destino
