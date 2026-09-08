"""Leitura, validação e render do bots.yml (fonte da verdade).

Tudo que gera texto a partir do yml mora aqui, para que apply e check
usem exatamente o mesmo render e nunca discordem.
"""
from __future__ import annotations

import os
import pathlib
import re
import shlex
import subprocess

import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent
BOTS_YML = pathlib.Path(os.environ.get("FZBOTS_YML", REPO / "bots.yml"))
SYSTEMD_DIR = pathlib.Path(os.environ.get("FZBOTS_SYSTEMD_DIR", "/etc/systemd/system"))
CLOUDFLARED_CFG = pathlib.Path(os.environ.get("FZBOTS_CLOUDFLARED_CFG", "/etc/cloudflared/config.yml"))
ARCHIVED = REPO / "archived"
CRED_FILE = pathlib.Path("/root/walker02-tunnel-access.txt")

BIND = "0.0.0.0"          # decisão do dono (ADR 0006): endpoints locais e na rede
PREFIXO_UNIT = "fzbots-"

CHAVES_TOPO = {"llama_bin", "modelos_dir", "gpu_vram_gb", "lan_ip", "bots"}
CHAVES_BOT = {"nome", "descricao", "site", "hostname", "porta", "modelo",
              "vram_estimada", "extra_args", "tunel", "consumidores"}
RE_NOME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RE_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")

PADRAO = {
    "llama_bin": "/home/dev/null/llama.cpp/build/bin/llama-server",
    "modelos_dir": "/root/.lmstudio/models",
    "gpu_vram_gb": 6,
    "lan_ip": "auto",
}


class ConfigError(Exception):
    """bots.yml inválido. Nada é aplicado."""


# ---------------------------------------------------------------- leitura

def load(path: pathlib.Path = BOTS_YML) -> dict:
    """Lê e valida o bots.yml. Levanta ConfigError com mensagem em PT."""
    if not path.is_file():
        raise ConfigError(f"bots.yml não encontrado: {path}")
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"bots.yml mal formado: {e}") from e
    if not isinstance(cfg, dict):
        raise ConfigError("bots.yml precisa ser um mapa com a chave 'bots'")
    for k, v in PADRAO.items():
        cfg.setdefault(k, v)
    validate(cfg)
    return cfg


def validate(cfg: dict) -> None:
    extras = set(cfg) - CHAVES_TOPO
    if extras:
        raise ConfigError(f"chave desconhecida no topo do bots.yml: {', '.join(sorted(extras))}")
    bots = cfg.get("bots")
    if not isinstance(bots, list) or not bots:
        raise ConfigError("'bots' precisa ser uma lista com pelo menos um bot")
    try:
        float(cfg["gpu_vram_gb"])
    except (TypeError, ValueError):
        raise ConfigError("gpu_vram_gb precisa ser número")
    if not isinstance(cfg["llama_bin"], str) or not cfg["llama_bin"]:
        raise ConfigError("llama_bin precisa ser um caminho")
    if any(c.isspace() for c in cfg["llama_bin"]) or "%" in cfg["llama_bin"]:
        raise ConfigError("llama_bin: caminho com espaço ou '%' não é suportado na unit")
    if not isinstance(cfg["modelos_dir"], str) or not cfg["modelos_dir"]:
        raise ConfigError("modelos_dir precisa ser um caminho")

    nomes, portas, hosts = set(), set(), set()
    for i, b in enumerate(bots):
        if not isinstance(b, dict):
            raise ConfigError(f"bot #{i+1} não é um mapa")
        rot = b.get("nome", f"#{i+1}")
        extras = set(b) - CHAVES_BOT
        if extras:
            raise ConfigError(f"bot {rot}: chave desconhecida: {', '.join(sorted(extras))} "
                              f"(válidas: {', '.join(sorted(CHAVES_BOT))})")
        for obrig in ("nome", "porta", "modelo", "vram_estimada"):
            if obrig not in b:
                raise ConfigError(f"bot {rot}: falta a chave '{obrig}'")
        nome = b["nome"]
        if not isinstance(nome, str) or not RE_NOME.match(nome):
            raise ConfigError(f"bot {rot}: nome inválido (use ^[a-z0-9][a-z0-9-]*$)")
        if nome in nomes:
            raise ConfigError(f"nome repetido no bots.yml: {nome}")
        nomes.add(nome)
        porta = b["porta"]
        if not isinstance(porta, int) or isinstance(porta, bool) or not 1 <= porta <= 65535:
            raise ConfigError(f"bot {nome}: porta precisa ser inteiro entre 1 e 65535")
        if porta in portas:
            raise ConfigError(f"porta repetida no bots.yml: {porta}")
        portas.add(porta)
        modelo = b["modelo"]
        if not isinstance(modelo, str) or not modelo:
            raise ConfigError(f"bot {nome}: modelo precisa ser um caminho")
        if any(c.isspace() for c in modelo) or "%" in modelo:
            raise ConfigError(f"bot {nome}: caminho do modelo com espaço ou '%' não é suportado na unit")
        try:
            float(b["vram_estimada"])
        except (TypeError, ValueError):
            raise ConfigError(f"bot {nome}: vram_estimada precisa ser número (GB)")
        if "tunel" in b and not isinstance(b["tunel"], bool):
            raise ConfigError(f"bot {nome}: 'tunel' precisa ser true ou false (sem aspas)")
        extra = b.get("extra_args", "")
        if extra is None:
            extra = ""
        if not isinstance(extra, str):
            raise ConfigError(f"bot {nome}: extra_args precisa ser texto")
        b["extra_args"] = extra
        if "%" in extra:
            raise ConfigError(f"bot {nome}: extra_args com '%' não é suportado na unit (systemd expande %)")
        try:
            toks = shlex.split(extra)
        except ValueError as e:
            raise ConfigError(f"bot {nome}: extra_args mal formado: {e}") from e
        for proib in ("--host", "--port", "-m", "--model"):
            if proib in toks:
                raise ConfigError(f"bot {nome}: '{proib}' não vai em extra_args (o gerador põe)")
        if "consumidores" in b:
            if not isinstance(b["consumidores"], list) or not all(isinstance(x, str) for x in b["consumidores"]):
                raise ConfigError(f"bot {nome}: consumidores precisa ser lista de nomes")
        for txt in ("descricao", "site"):
            if txt in b and not isinstance(b[txt], str):
                raise ConfigError(f"bot {nome}: {txt} precisa ser texto")
        if publico(b):
            h = b.get("hostname")
            if not h:
                raise ConfigError(f"bot público sem hostname: {nome} (ou marque tunel: false)")
            if not isinstance(h, str) or not RE_HOST.match(h):
                raise ConfigError(f"bot {nome}: hostname inválido: {h}")
            if h in hosts:
                raise ConfigError(f"hostname repetido no bots.yml: {h}")
            hosts.add(h)


def validar_modelos(cfg: dict) -> list[str]:
    """Modelos que não existem no disco (checado no apply/start, não no load)."""
    return [b["modelo"] for b in cfg["bots"] if not pathlib.Path(b["modelo"]).is_file()]


# ---------------------------------------------------------------- helpers

def publico(b: dict) -> bool:
    return b.get("tunel", True) is not False


def embedding(b: dict) -> bool:
    try:
        return "--embedding" in shlex.split(b.get("extra_args") or "")
    except ValueError:
        return False


def unit_name(b: dict) -> str:
    return f"{PREFIXO_UNIT}{b['nome']}.service"


def unit_path(b: dict) -> pathlib.Path:
    return SYSTEMD_DIR / unit_name(b)


def bot(cfg: dict, nome: str) -> dict:
    for b in cfg["bots"]:
        if b["nome"] == nome:
            return b
    raise ConfigError(f"bot não existe no bots.yml: {nome} (tem: {', '.join(x['nome'] for x in cfg['bots'])})")


def vram_total(cfg: dict) -> float:
    return sum(float(b["vram_estimada"]) for b in cfg["bots"])


def lan_ip(cfg: dict) -> str:
    """IP da LAN para montar URLs. 'auto' = primeira interface física com IPv4 global."""
    v = str(cfg.get("lan_ip") or "auto")
    if v != "auto":
        return v
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr", "show", "scope", "global"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return "127.0.0.1"
    for linha in out.splitlines():
        partes = linha.split()
        if len(partes) < 4:
            continue
        iface, ip = partes[1], partes[3].split("/")[0]
        if iface.startswith(("lxd", "lxc", "docker", "virbr", "br-", "wg", "tun", "tap", "veth", "podman",
                             "cni", "tailscale", "zt", "ppp", "vpn")):
            continue
        return ip
    return "127.0.0.1"


def urls(cfg: dict, b: dict) -> dict[str, str]:
    u = {"local": f"http://127.0.0.1:{b['porta']}",
         "rede": f"http://{lan_ip(cfg)}:{b['porta']}"}
    if publico(b):
        u["tunel"] = f"https://{b['hostname']}"
    return u


# ---------------------------------------------------------------- render

def render_unit(cfg: dict, b: dict) -> str:
    modelo = pathlib.Path(b["modelo"])
    extra = (b.get("extra_args") or "").strip()
    cmd = f"{cfg['llama_bin']} -m {b['modelo']}" + (f" {extra}" if extra else "") \
          + f" --host {BIND} --port {b['porta']}"
    return f"""[Unit]
Description=fzbots bot '{b['nome']}' ({modelo.name}) {BIND}:{b['porta']}
After=network.target

[Service]
Type=simple
ExecStart={cmd}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def render_ingress(cfg: dict) -> list[dict]:
    ing = [{"hostname": b["hostname"], "service": f"http://127.0.0.1:{b['porta']}"}
           for b in cfg["bots"] if publico(b)]
    ing.append({"service": "http_status:404"})
    return ing


def desired(cfg: dict) -> dict:
    """Estado desejado: {'units': {Path: texto}, 'ingress': [...]}."""
    return {
        "units": {unit_path(b): render_unit(cfg, b) for b in cfg["bots"]},
        "ingress": render_ingress(cfg),
    }


# ---------------------------------------------------------------- escrita no yml

def adicionar_bot(bloco: dict, path: pathlib.Path = BOTS_YML) -> dict:
    """Acrescenta um bot ao fim do bots.yml preservando comentários (append textual),
    arquivando antes. Valida o resultado; se inválido, restaura e levanta ConfigError."""
    import shutil
    import datetime as _dt
    arq = ARCHIVED if path.resolve() == BOTS_YML.resolve() else path.parent / "archived"
    arq.mkdir(exist_ok=True)
    backup = arq / f"{path.name}.{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(path, backup)
    ordem = ["nome", "descricao", "site", "hostname", "porta", "modelo", "vram_estimada",
             "extra_args", "tunel", "consumidores"]
    linhas = []
    for i, k in enumerate(ordem):
        if k not in bloco or bloco[k] in (None, ""):
            continue
        v = bloco[k]
        if k == "consumidores":
            v = "[" + ", ".join(v) + "]"
        elif k == "extra_args":
            v = '"' + str(v).replace('"', '\\"') + '"'
        elif isinstance(v, bool):
            v = "true" if v else "false"
        prefixo = "  - " if i == 0 else "    "
        linhas.append(f"{prefixo}{k}: {v}")
    texto = path.read_text(encoding="utf-8")
    if not texto.endswith("\n"):
        texto += "\n"
    path.write_text(texto + "\n".join(linhas) + "\n", encoding="utf-8")
    try:
        return load(path)
    except ConfigError:
        shutil.copy2(backup, path)
        raise
