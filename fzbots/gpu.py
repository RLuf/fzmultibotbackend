"""GPU real via nvidia-smi: quem usa VRAM, quanto, e de que unit systemd veio.

A trava de VRAM do apply/start soma o que o bots.yml estima COM o que
processos de fora (LMS, Pangeia, o que for) estão usando de verdade.
"""
from __future__ import annotations

import pathlib
import subprocess
from dataclasses import dataclass

from .config import PREFIXO_UNIT


@dataclass
class Proc:
    pid: int
    mib: int
    unit: str          # unit systemd (ex.: fzbots-llama.service) ou '' se não achou
    cmd: list[str]

    @property
    def nosso(self) -> bool:
        return self.unit.startswith(PREFIXO_UNIT)

    def arg(self, flag: str) -> str | None:
        """Valor de uma flag na linha de comando (--port 8081 ou --port=8081 → '8081')."""
        for i, t in enumerate(self.cmd):
            if t == flag and i + 1 < len(self.cmd):
                return self.cmd[i + 1]
            if t.startswith(flag + "="):
                return t[len(flag) + 1:]
        return None


def _smi(*args: str) -> str | None:
    try:
        return subprocess.run(["nvidia-smi", *args], capture_output=True, text=True,
                              check=True, timeout=10).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def info() -> dict | None:
    """{'nome', 'usado_mib', 'total_mib'} ou None se nvidia-smi falhar."""
    out = _smi("--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits")
    if not out or not out.strip():
        return None
    nomes, usado, total = [], 0, 0
    try:
        for linha in out.strip().splitlines():      # uma linha por GPU: soma todas
            n, u, t = [x.strip() for x in linha.split(",")]
            nomes.append(n); usado += int(u); total += int(t)
    except ValueError:
        return None
    return {"nome": " + ".join(nomes), "usado_mib": usado, "total_mib": total}


def unit_of_pid(pid: int) -> str:
    try:
        cg = pathlib.Path(f"/proc/{pid}/cgroup").read_text().strip()
    except OSError:
        return ""
    ultimo = cg.rsplit("/", 1)[-1]
    return ultimo if ultimo.endswith((".service", ".scope")) else ""


def cmdline(pid: int) -> list[str]:
    try:
        raw = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [x.decode(errors="replace") for x in raw.split(b"\0") if x]


def procs() -> list[Proc]:
    """Processos com VRAM alocada agora (lista vazia se nvidia-smi falhar)."""
    out = _smi("--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits")
    res: list[Proc] = []
    if not out:
        return res
    for linha in out.strip().splitlines():
        if not linha.strip():
            continue
        pid_s, mib_s = [x.strip() for x in linha.split(",")[:2]]
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        try:
            mib = int(float(mib_s))
        except ValueError:          # "[N/A]" / "Not Supported": uso desconhecido, não zero
            mib = -1
        res.append(Proc(pid=pid, mib=mib, unit=unit_of_pid(pid), cmd=cmdline(pid)))
    return res


def estranhos(cfg: dict, lista: list[Proc] | None = None) -> list[Proc]:
    """Processos de fora do projeto que ocupam VRAM.

    Um processo externo que já escuta na porta de um bot do yml (caso de uma
    unit antiga sendo substituída) NÃO conta como estranho: a VRAM dele é a do
    próprio bot, que vai tomar o lugar.
    """
    lista = procs() if lista is None else lista
    portas = {str(b["porta"]) for b in cfg["bots"]}
    units = {f"{PREFIXO_UNIT}{b['nome']}.service" for b in cfg["bots"]}
    # unit fzbots-* órfã (fora do yml) também é "terceiro": ocupa VRAM e não é deste yml
    return [p for p in lista if p.unit not in units and p.arg("--port") not in portas]


def substituiveis(cfg: dict, lista: list[Proc] | None = None) -> list[Proc]:
    """Processos externos que ocupam a porta de um bot do yml (a substituir)."""
    lista = procs() if lista is None else lista
    portas = {str(b["porta"]) for b in cfg["bots"]}
    units = {f"{PREFIXO_UNIT}{b['nome']}.service" for b in cfg["bots"]}
    return [p for p in lista if p.unit not in units and p.arg("--port") in portas]


def uso_por_unit(lista: list[Proc] | None = None) -> dict[str, int]:
    lista = procs() if lista is None else lista
    d: dict[str, int] = {}
    for p in lista:
        d[p.unit or f"pid {p.pid}"] = d.get(p.unit or f"pid {p.pid}", 0) + p.mib
    return d


def trava(cfg: dict) -> tuple[bool, str]:
    """(ok, mensagem). ok=False quando estimativa do yml + VRAM de terceiros > GPU."""
    cap = float(cfg["gpu_vram_gb"])
    from .config import vram_total
    est = vram_total(cfg)
    if info() is None:
        return False, "VRAM: nvidia-smi não respondeu — não dá para saber quanto a GPU tem livre"
    lista = procs()
    desconhecidos = [p for p in lista if p.mib < 0]
    if desconhecidos:
        quem = ", ".join(p.unit or f"pid {p.pid}" for p in desconhecidos)
        return False, f"VRAM: nvidia-smi não informou o uso de memória de: {quem}"
    ext = estranhos(cfg, lista)
    ext_gb = sum(p.mib for p in ext) / 1024
    total = est + ext_gb
    quem = ", ".join(f"{p.unit or ('pid ' + str(p.pid))} {p.mib} MiB" for p in ext) or "nenhum"
    msg = (f"VRAM: bots.yml {est:.1f} GB + terceiros {ext_gb:.1f} GB = {total:.1f} / {cap:g} GB"
           f" (terceiros: {quem})")
    return total <= cap, msg
