#!/bin/bash
# Desfaz TUDO deste projeto e volta o walker02 ao estado de 2026-08-10:
# llama-server em nohup 0.0.0.0:8081, sem túnel, sem Access.
set -x
# 1. Serviços
systemctl disable --now cloudflared fzbots-llama
rm -f /etc/systemd/system/fzbots-llama.service; systemctl daemon-reload
# 2. Túnel e DNS (só o fzbots — NÃO toca nos outros túneis da conta)
cloudflared tunnel delete -f fzbots
echo "DNS: apagar o CNAME fzbots.rogerluft.com.br no painel (route dns não tem delete via cert)"
# 3. Access (precisa do API token)
CF=$(cat /root/.cf-api-token); ACC=6955cc8b42f724d7c15671000441f14e
APP=d39df202-0d92-4cd8-b804-dcb4315ee174
ST=$(grep '^Service Token ID:' /root/walker02-tunnel-access.txt | cut -d' ' -f4)
curl -s -X DELETE -H "Authorization: Bearer $CF" https://api.cloudflare.com/client/v4/accounts/$ACC/access/apps/$APP
curl -s -X DELETE -H "Authorization: Bearer $CF" https://api.cloudflare.com/client/v4/accounts/$ACC/access/service_tokens/$ST
# 4. Volta o llama como era (ver archived/estado-anterior-2026-08-11.md)
nohup /home/dev/null/llama.cpp/build/bin/llama-server \
  -m /root/.lmstudio/models/DeepHat/DeepHat-V1-7B.Q4_K_M.gguf \
  -ngl 99 -c 4096 -fa on --host 0.0.0.0 --port 8081 > /root/deephat.log 2>&1 &
