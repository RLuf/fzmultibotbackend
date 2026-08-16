#!/bin/bash
# Testa TODOS os bots do bots.yml pelo túnel, com o Service Token do arquivo 600.
# Sai com código != 0 se algum teste falhar.
# ATENÇÃO: o teste positivo só passa saindo da rede autorizada (138.186.228.0/24).
cd "$(dirname "$0")/.."
F=/root/walker02-tunnel-access.txt
CID=$(grep -m1 '^Client ID:' "$F" | awk '{print $3}')
CSEC=$(grep -m1 '^Client Secret:' "$F" | awk '{print $3}')
[ -n "$CID" ] && [ -n "$CSEC" ] || { echo "FALHA: credenciais não lidas de $F"; exit 1; }
H1="CF-Access-Client-Id: $CID"; H2="CF-Access-Client-Secret: $CSEC"
FALHAS=0

while IFS=$'\t' read -r nome hostname; do
  URL="https://$hostname"
  echo "== $nome ($URL) =="
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL/health")
  [ "$code" = 403 ] && echo "sem credencial: 403 (correto)" \
    || { echo "FALHA: sem credencial devia dar 403, deu $code"; FALHAS=$((FALHAS+1)); }
  curl -sf --max-time 15 -H "$H1" -H "$H2" "$URL/health" \
    && echo " health ok" || { echo "FALHA: health com credencial"; FALHAS=$((FALHAS+1)); }
  curl -sf --max-time 60 -H "$H1" -H "$H2" -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"Diga apenas: ok"}],"max_tokens":300}' \
    "$URL/v1/chat/completions" >/dev/null \
    && echo "chat ok" || { echo "FALHA: chat"; FALHAS=$((FALHAS+1)); }
done < <(python3 -c "
import yaml
for b in yaml.safe_load(open('bots.yml'))['bots']:
    if b.get('tunel', True) is False:
        continue
    print(f\"{b['nome']}\t{b['hostname']}\")")

[ $FALHAS = 0 ] && echo "TUDO OK" || echo "$FALHAS FALHA(S)"
exit $FALHAS
