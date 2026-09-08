"""Aplicar, conferir e operar as units geradas e o ingress do cloudflared."""
from __future__ import annotations

import datetime as _dt
import difflib
import os
import pathlib
import shutil
import subprocess
import tempfile

import yaml

from . import config as C
from . import gpu


class OperError(Exception):
    """Falha operacional (systemctl, escrita, dependência externa)."""


# ---------------------------------------------------------------- utilitários

def stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def sh(*cmd: str, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise OperError(f"{' '.join(cmd)} → rc={r.returncode}: {(r.stderr or r.stdout).strip()}")
    return r


def archive(path: pathlib.Path, st: str | None = None) -> pathlib.Path | None:
    """REGRA DE OURO: copia para archived/ antes de sobrescrever/apagar."""
    if not path.exists():
        return None
    C.ARCHIVED.mkdir(exist_ok=True)
    dest = C.ARCHIVED / f"{path.name}.{st or stamp()}"
    shutil.copy2(path, dest)
    return dest


def write_atomic(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise


def show(unit: str, *props: str) -> dict[str, str]:
    r = sh("systemctl", "show", unit, "-p", ",".join(props), check=False)
    d: dict[str, str] = {}
    for linha in r.stdout.splitlines():
        if "=" in linha:
            k, v = linha.split("=", 1)
            d[k] = v
    return d


def estado(unit: str) -> dict[str, str]:
    return show(unit, "ActiveState", "SubState", "MainPID", "UnitFileState",
                "NeedDaemonReload", "ActiveEnterTimestamp", "ActiveEnterTimestampMonotonic", "LoadState")


def _ts_monotonic_para_epoch(e: dict[str, str]) -> float | None:
    """Início da unit em epoch, sem depender de locale: usa o timestamp monotônico (µs) + uptime."""
    try:
        mono_us = int(e.get("ActiveEnterTimestampMonotonic") or 0)
        if mono_us <= 0:
            return None
        uptime = float(pathlib.Path("/proc/uptime").read_text().split()[0])
        import time as _t
        return _t.time() - uptime + mono_us / 1e6
    except (ValueError, OSError):
        return None


def dependentes(unit: str) -> list[str]:
    """Quem exige esta unit (Requires/Wants/BindsTo), fora das metas de boot (*.target).
    Se o systemctl falhar, levanta OperError: 'não sei' é diferente de 'ninguém'."""
    r = sh("systemctl", "show", unit, "-p", "RequiredBy,WantedBy,BoundBy", check=False)
    if r.returncode != 0:
        raise OperError(f"systemctl show {unit} falhou: {(r.stderr or r.stdout).strip()}")
    res = []
    for linha in r.stdout.splitlines():
        if "=" in linha:
            res += [x for x in linha.split("=", 1)[1].split() if x and not x.endswith(".target")]
    return sorted(set(res))


def units_instaladas() -> list[pathlib.Path]:
    return sorted(C.SYSTEMD_DIR.glob(f"{C.PREFIXO_UNIT}*.service"))


def cloudflared_ler() -> dict | None:
    if not C.CLOUDFLARED_CFG.is_file():
        return None
    try:
        d = yaml.safe_load(C.CLOUDFLARED_CFG.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise OperError(f"{C.CLOUDFLARED_CFG} mal formado: {e}") from e
    return d if isinstance(d, dict) else {}


def cloudflared_render(atual: dict, ingress: list[dict]) -> str:
    novo = dict(atual)
    novo["ingress"] = ingress
    return ("# GERADO por fzbots apply a partir de bots.yml — editar lá\n"
            + yaml.safe_dump(novo, sort_keys=False, allow_unicode=True))


# ---------------------------------------------------------------- planejar / aplicar

def planejar(cfg: dict) -> dict:
    """Calcula tudo que o apply faria, sem escrever nada."""
    des = C.desired(cfg)
    plano = {"novas": [], "alteradas": [], "iguais": [], "orfas": [],
             "ingress_muda": False, "ingress_texto": None, "erros": []}
    for path, texto in des["units"].items():
        try:
            atual_u = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            plano["novas"].append(path)
            continue
        if atual_u != texto:
            plano["alteradas"].append(path)
        else:
            plano["iguais"].append(path)
    plano["orfas"] = [p for p in units_instaladas() if p not in des["units"]]

    publicos = [b for b in cfg["bots"] if C.publico(b)]
    atual = cloudflared_ler()
    if atual is None:
        if publicos:
            plano["erros"].append(f"{C.CLOUDFLARED_CFG} não existe e há bot com hostname "
                                  f"({', '.join(b['nome'] for b in publicos)}); crie o túnel antes")
    elif atual.get("ingress") != des["ingress"]:
        plano["ingress_muda"] = True
        plano["ingress_texto"] = cloudflared_render(atual, des["ingress"])

    faltam = C.validar_modelos(cfg)
    if faltam:
        plano["erros"].append("modelo não existe: " + ", ".join(faltam))
    ok, msg = gpu.trava(cfg)
    plano["vram_msg"] = msg
    if not ok:
        plano["erros"].append("não cabe na GPU — " + msg)
    return plano


def apply(cfg: dict, prune: bool = False, restart: bool = False, out=print) -> int:
    """Aplica o bots.yml. Retorna 0 se ok. Valida TUDO antes de escrever qualquer coisa."""
    plano = planejar(cfg)
    if plano["erros"]:
        for e in plano["erros"]:
            out(f"ERRO: {e}")
        out("Nada aplicado.")
        return 2
    out(plano["vram_msg"])
    des = C.desired(cfg)
    st = stamp()

    for path in plano["orfas"]:
        deps = dependentes(path.name)
        if prune:
            if deps:
                out(f"ERRO: {path.name} é órfã mas tem dependente externo: {', '.join(deps)}. "
                    "Nada aplicado.")
                return 2
        else:
            out(f"AVISO: unit órfã (não está no bots.yml): {path.name}"
                + (f" — dependentes: {', '.join(deps)}" if deps else "")
                + " — remova com: fzbots apply --prune")

    for path in plano["novas"] + plano["alteradas"]:
        archive(path, st)
        write_atomic(path, des["units"][path])
        out(f"unit {'criada' if path in plano['novas'] else 'atualizada'}: {path.name}")
    if plano["ingress_muda"]:
        archive(C.CLOUDFLARED_CFG, st)
        write_atomic(C.CLOUDFLARED_CFG, plano["ingress_texto"])
        out("ingress atualizado")

    removidas = []
    if prune:
        for path in plano["orfas"]:
            archive(path, st)
            sh("systemctl", "disable", "--now", path.name, check=False)
            path.unlink()
            removidas.append(path.name)
            out(f"unit órfã removida (cópia em archived/): {path.name}")

    if plano["novas"] or plano["alteradas"] or removidas:
        sh("systemctl", "daemon-reload")

    acoes = []
    for path in plano["novas"]:
        acoes.append(("enable", path.name))
    for path in plano["alteradas"]:
        acoes.append(("restart", path.name))
    if plano["ingress_muda"]:
        acoes.append(("restart", "cloudflared"))
    for path in plano["iguais"]:             # unit igual mas parada/falhada: sobe também
        if estado(path.name).get("ActiveState") != "active":
            acoes.append(("enable", path.name))

    out(f"OK: {len(cfg['bots'])} bot(s) no bots.yml")
    if not acoes:
        out("Nada mudou nas units nem no ingress.")
        return 0
    if restart:
        for acao, unit in acoes:
            if acao == "enable":
                sh("systemctl", "enable", "--now", unit)
                out(f"  subiu: {unit}")
            else:
                sh("systemctl", "restart", unit)
                out(f"  reiniciou: {unit}")
    else:
        out("Agora rode (ou use: fzbots apply --restart):")
        for acao, unit in acoes:
            out(f"  systemctl {'enable --now' if acao == 'enable' else 'restart'} {unit}")
    return 0


# ---------------------------------------------------------------- check (drift)

def check(cfg: dict) -> list[tuple[str, str]]:
    """Compara bots.yml com o host. Retorna [(nivel, msg)], nivel ∈ FALHA|AVISO|ok."""
    achados: list[tuple[str, str]] = []
    des = C.desired(cfg)
    for m in C.validar_modelos(cfg):
        achados.append(("FALHA", f"modelo não existe no disco: {m}"))

    # a) arquivos
    for path, texto in des["units"].items():
        if not path.exists():
            achados.append(("FALHA", f"unit não existe: {path.name} (rode fzbots apply)"))
            continue
        atual = path.read_text(encoding="utf-8")
        if atual != texto:
            diff = "".join(difflib.unified_diff(atual.splitlines(True), texto.splitlines(True),
                                                f"{path.name} (host)", f"{path.name} (bots.yml)"))
            achados.append(("FALHA", f"unit diferente do bots.yml: {path.name}\n{diff.rstrip()}"))
    atual_cf = cloudflared_ler()
    publicos = [b for b in cfg["bots"] if C.publico(b)]
    if atual_cf is None:
        if publicos:
            achados.append(("FALHA", f"{C.CLOUDFLARED_CFG} não existe"))
    elif atual_cf.get("ingress") != des["ingress"]:
        achados.append(("FALHA", "ingress do cloudflared diferente do bots.yml (rode fzbots apply)"))

    # b) órfãs
    for p in units_instaladas():
        if p not in des["units"]:
            deps = dependentes(p.name)
            achados.append(("FALHA", f"ÓRFÃ: {p.name} não está no bots.yml"
                            + (f" — dependentes: {', '.join(deps)}" if deps else "")))

    # c) processo vs unit
    for b in cfg["bots"]:
        u = C.unit_name(b)
        e = estado(u)
        if e.get("LoadState") == "not-found":
            continue
        if e.get("NeedDaemonReload") == "yes":
            achados.append(("FALHA", f"{u}: daemon-reload pendente"))
        if e.get("UnitFileState") not in ("enabled", "enabled-runtime", "static"):
            achados.append(("AVISO", f"{u}: não está enabled (não sobe no boot)"))
        if e.get("ActiveState") != "active":
            achados.append(("FALHA", f"{u}: {e.get('ActiveState')}/{e.get('SubState')}"))
            continue
        pid = int(e.get("MainPID") or 0)
        cmd = gpu.cmdline(pid) if pid else []
        esperado = _execstart(des["units"][C.unit_path(b)])
        if cmd and cmd != esperado:
            achados.append(("FALHA", f"{u}: processo no ar difere da unit (unit alterada, processo antigo) "
                            f"→ systemctl restart {u}"))

    # d) cloudflared
    if publicos:
        e = estado("cloudflared")
        if e.get("ActiveState") != "active":
            achados.append(("FALHA", "cloudflared parado"))
        elif C.CLOUDFLARED_CFG.is_file():
            ts = e.get("ActiveEnterTimestamp", "")
            inicio = _ts_monotonic_para_epoch(e)
            if inicio is None:
                achados.append(("AVISO", f"não consegui interpretar o início do cloudflared ({ts!r}) — checagem 'config mais nova que o start' pulada"))
            elif C.CLOUDFLARED_CFG.stat().st_mtime > inicio:
                achados.append(("FALHA", "config.yml do cloudflared mudou depois do start → systemctl restart cloudflared"))

    # e) GPU real
    ginfo = gpu.info()
    if ginfo is None:
        achados.append(("FALHA", "nvidia-smi não respondeu"))
    else:
        lista = gpu.procs()
        ok, msg = gpu.trava(cfg)
        achados.append(("ok" if ok else "FALHA", msg))
        uso = gpu.uso_por_unit(lista)
        for b in cfg["bots"]:
            real = uso.get(C.unit_name(b))
            est = float(b["vram_estimada"]) * 1024
            if real and real > est * 1.3:
                achados.append(("AVISO", f"{b['nome']}: usa {real} MiB, estimado {est:.0f} MiB — ajuste vram_estimada"))
        for p in gpu.substituiveis(cfg, lista):
            achados.append(("AVISO", f"porta {p.arg('--port')} ocupada por processo fora do projeto "
                            f"({p.unit or 'pid ' + str(p.pid)}, {p.mib} MiB) — será substituído pela unit fzbots"))
    return achados


def _execstart(unit_text: str) -> list[str]:
    import shlex
    for linha in unit_text.splitlines():
        if linha.startswith("ExecStart="):
            return shlex.split(linha[len("ExecStart="):])
    return []


# ---------------------------------------------------------------- operar

def start(cfg: dict, nome: str, out=print) -> None:
    b = C.bot(cfg, nome)
    u = C.unit_name(b)
    if not C.unit_path(b).exists():
        raise OperError(f"unit {u} não existe — rode fzbots apply")
    if estado(u).get("ActiveState") == "active":
        out(f"{u} já está ativo")
        return
    ginfo = gpu.info()
    if ginfo is None:
        raise OperError("nvidia-smi não respondeu — não dá para conferir a VRAM livre; não vou subir às cegas")
    livre = (ginfo["total_mib"] - ginfo["usado_mib"]) / 1024
    ocupantes = [p for p in gpu.substituiveis(cfg) if p.arg("--port") == str(b["porta"])]
    for p in ocupantes:
        out(f"AVISO: porta {b['porta']} já está ocupada por {p.unit or 'pid ' + str(p.pid)} ({p.mib} MiB) — "
            f"pare-o antes, senão {u} vai falhar ao abrir a porta")
    mesma_porta = sum(max(p.mib, 0) for p in ocupantes) / 1024
    if float(b["vram_estimada"]) > livre + mesma_porta:
        raise OperError(f"VRAM livre {livre:.1f} GB < estimado {b['vram_estimada']} GB de {nome}. "
                        f"Pare outro bot ou ajuste vram_estimada.")
    sh("systemctl", "enable", "--now", u)
    out(f"subiu: {u}")


def stop(cfg: dict, nome: str, forca: bool = False, out=print) -> None:
    b = C.bot(cfg, nome)
    u = C.unit_name(b)
    deps = dependentes(u)
    cons = b.get("consumidores") or []
    if (deps or cons) and not forca:
        raise OperError(f"{u} tem quem dependa dele: {', '.join(deps + cons)}. Use --forca para parar mesmo assim.")
    sh("systemctl", "stop", u)
    out(f"parou: {u}")


def restart(cfg: dict, nome: str, out=print) -> None:
    b = C.bot(cfg, nome)
    u = C.unit_name(b)
    sh("systemctl", "restart", u)
    out(f"reiniciou: {u}")


def logs(cfg: dict, nome: str, linhas: int = 50, seguir: bool = False) -> int:
    b = C.bot(cfg, nome)
    cmd = ["journalctl", "-u", C.unit_name(b), "-n", str(linhas), "--no-pager"]
    if seguir:
        cmd.append("-f")
    return subprocess.call(cmd)


def undo(cfg: dict | None = None, forca: bool = False, out=print) -> int:
    """Desfaz SÓ o que este projeto gerou: units fzbots-* e o ingress.
    Não apaga túnel, DNS nem Access; não sobe nada no lugar."""
    st = stamp()
    for p in units_instaladas():
        deps = dependentes(p.name)
        if deps and not forca:
            out(f"ERRO: {p.name} tem dependente externo ({', '.join(deps)}). Use --forca. Nada desfeito.")
            return 2
    for p in units_instaladas():
        archive(p, st)
        sh("systemctl", "disable", "--now", p.name, check=False)
        p.unlink()
        out(f"removida: {p.name} (cópia em archived/)")
    sh("systemctl", "daemon-reload")
    atual = cloudflared_ler()
    if atual is not None and atual.get("ingress") != [{"service": "http_status:404"}]:
        archive(C.CLOUDFLARED_CFG, st)
        write_atomic(C.CLOUDFLARED_CFG, cloudflared_render(atual, [{"service": "http_status:404"}]))
        sh("systemctl", "restart", "cloudflared", check=False)
        out("ingress zerado (só 404); cloudflared reiniciado")
    out("Ficou por sua conta, no painel Cloudflare: túnel, CNAMEs e apps do Access.")
    return 0
