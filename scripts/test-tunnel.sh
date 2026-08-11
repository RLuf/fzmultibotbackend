#!/bin/bash
# Testa a API pelo túnel usando o Service Token (lê de /root/walker02-tunnel-access.txt).
# ATENÇÃO: o teste positivo só passa se este host sair pela rede autorizada (138.186.228.0/24).
set -e
F=/root/walker02-tunnel-access.txt
CID=$(grep '^Client ID:' $F | cut -d' ' -f3)
CSEC=$(grep '^Client Secret:' $F | cut -d' ' -f3)
URL=https://fzbots.rogerluft.com.br
H1="CF-Access-Client-Id: $CID"; H2="CF-Access-Client-Secret: $CSEC"

echo "== Sem credencial (esperado 403) =="
curl -s -o /dev/null -w '%{http_code}\n' --max-time 15 $URL/health
echo "== Health =="
curl -s --max-time 15 -H "$H1" -H "$H2" $URL/health; echo
echo "== Modelos =="
curl -s --max-time 15 -H "$H1" -H "$H2" $URL/v1/models | head -c 300; echo
echo "== Chat curto =="
curl -s --max-time 60 -H "$H1" -H "$H2" -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Diga apenas: ok"}],"max_tokens":20}' \
  $URL/v1/chat/completions | head -c 500; echo
