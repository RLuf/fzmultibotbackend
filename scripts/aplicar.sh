#!/bin/bash
# Lê bots.yml (fonte da verdade) e aplica:
#  - gera 1 unit systemd por bot (fzbots-<nome>.service, 127.0.0.1:<porta>)
#  - gera o ingress do /etc/cloudflared/config.yml (túnel fzbots intacto)
#  - confere a soma de VRAM antes de subir
#  - guarda os arquivos antigos em archived/ (REGRA DE OURO)
# NÃO mexe em DNS nem em Access — bot novo ainda precisa de:
#   cloudflared tunnel route dns fzbots <hostname>   (uma vez)
#   app Access + Service Token (ver docs/pt/adicionar-bot.md)
set -euo pipefail
cd "$(dirname "$0")/.."
STAMP=$(date +%Y%m%d_%H%M%S)

python3 - "$STAMP" <<'PY'
import subprocess, sys, yaml, pathlib, shutil

stamp = sys.argv[1]
cfg = yaml.safe_load(open('bots.yml'))
bots, cap = cfg['bots'], float(cfg.get('gpu_vram_gb', 6))

total = sum(float(b['vram_estimada']) for b in bots)
if total > cap:
    sys.exit(f"ERRO: VRAM estimada {total:.1f} GB > {cap} GB da GPU. Nada aplicado.")

portas = [b['porta'] for b in bots]
if len(portas) != len(set(portas)):
    sys.exit("ERRO: porta repetida no bots.yml. Nada aplicado.")
for b in bots:
    if not pathlib.Path(b['modelo']).is_file():
        sys.exit(f"ERRO: modelo não existe: {b['modelo']}. Nada aplicado.")

arch = pathlib.Path('archived'); arch.mkdir(exist_ok=True)

# units systemd
for b in bots:
    unit = pathlib.Path(f"/etc/systemd/system/fzbots-{b['nome']}.service")
    novo = f"""[Unit]
Description=fzbots bot '{b['nome']}' ({pathlib.Path(b['modelo']).name}) 127.0.0.1:{b['porta']}
After=network.target

[Service]
Type=simple
ExecStart=/home/dev/null/llama.cpp/build/bin/llama-server -m {b['modelo']} {b['extra_args']} --host 127.0.0.1 --port {b['porta']}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    if unit.exists() and unit.read_text() != novo:
        shutil.copy(unit, arch / f"{unit.name}.{stamp}")
    if not unit.exists() or unit.read_text() != novo:
        unit.write_text(novo)
        print(f"unit atualizada: {unit.name}")

# ingress do cloudflared
cf = pathlib.Path('/etc/cloudflared/config.yml')
atual = yaml.safe_load(cf.read_text())
ingress = [{'hostname': b['hostname'], 'service': f"http://127.0.0.1:{b['porta']}"} for b in bots]
ingress.append({'service': 'http_status:404'})
if atual.get('ingress') != ingress:
    shutil.copy(cf, arch / f"config.yml.{stamp}")
    atual['ingress'] = ingress
    cf.write_text("# GERADO por scripts/aplicar.sh a partir de bots.yml — editar lá\n"
                  + yaml.safe_dump(atual, sort_keys=False, allow_unicode=True))
    print("ingress atualizado")

print(f"OK: {len(bots)} bot(s), VRAM {total:.1f}/{cap} GB")
for b in bots:
    print(f"  systemctl enable --now fzbots-{b['nome']}")
PY

systemctl daemon-reload
echo "Agora: suba as units listadas acima e, se mudou o ingress: systemctl restart cloudflared"
