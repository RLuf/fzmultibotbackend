#!/bin/bash
# Desfaz o projeto no walker02 — MULTIBOT, sem ID na unha:
#  - bots: lidos do bots.yml
#  - IDs do Access: lidos de /root/walker02-tunnel-access.txt
# NÃO toca nos outros túneis da conta (regra 3 do AGENTS.md).
# Estado restaurado: llama-server solto em 0.0.0.0:8081 (archived/estado-anterior-*.md).
set -x
cd "$(dirname "$0")/.."
F=/root/walker02-tunnel-access.txt

# 1. Serviços dos bots (do bots.yml) + túnel
for nome in $(python3 -c "
import yaml
print(' '.join(b['nome'] for b in yaml.safe_load(open('bots.yml'))['bots']))"); do
  systemctl disable --now "fzbots-$nome"
  rm -f "/etc/systemd/system/fzbots-$nome.service"
done
systemctl disable --now cloudflared
systemctl daemon-reload

# 2. Túnel fzbots e só ele
cloudflared tunnel delete -f fzbots
echo "DNS: apagar os CNAMEs dos bots no painel (route dns não tem delete via cert)"

# 3. Access — apps e service tokens listados no arquivo de credenciais
CF=$(cat /root/.cf-api-token)
ACC=$(grep -m1 '^Conta Cloudflare:' "$F" | awk '{print $3}')
for APP in $(grep '^App Access:' "$F" | awk '{print $3}'); do
  curl -s -X DELETE -H "Authorization: Bearer $CF" \
    "https://api.cloudflare.com/client/v4/accounts/$ACC/access/apps/$APP"
done
for ST in $(grep '^Service Token ID:' "$F" | awk '{print $4}'); do
  curl -s -X DELETE -H "Authorization: Bearer $CF" \
    "https://api.cloudflare.com/client/v4/accounts/$ACC/access/service_tokens/$ST"
done

# 4. Volta o llama como era antes do projeto
nohup /home/dev/null/llama.cpp/build/bin/llama-server \
  -m /root/.lmstudio/models/DeepHat/DeepHat-V1-7B.Q4_K_M.gguf \
  -ngl 99 -c 4096 -fa on --host 0.0.0.0 --port 8081 > /root/deephat.log 2>&1 &
