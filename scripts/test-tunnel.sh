#!/bin/bash
# Testa os bots PÚBLICOS (com hostname) pelo túnel, com o Service Token do arquivo 600.
# Sai com código != 0 se algum teste FALHAR.
# Rodado de fora da rede autorizada, o teste com credencial devolve 403: isso é a
# política funcionando (AVISO), não falha. O positivo só passa de dentro da rede.
cd "$(dirname "$(readlink -f "$0")")/.."
F=/root/walker02-tunnel-access.txt
CID=$(grep -m1 '^Client ID:' "$F" 2>/dev/null | awk '{print $3}')
CSEC=$(grep -m1 '^Client Secret:' "$F" 2>/dev/null | awk '{print $3}')
[ -n "$CID" ] && [ -n "$CSEC" ] || { echo "FALHA: credenciais não lidas de $F"; exit 1; }
H1="CF-Access-Client-Id: $CID"; H2="CF-Access-Client-Secret: $CSEC"
FALHAS=0; AVISOS=0
LISTA=$(bin/fzbots list --publicos) || { echo "FALHA: fzbots list --publicos falhou (bots.yml inválido?)"; exit 1; }
[ -n "$LISTA" ] || { echo "nenhum bot público no bots.yml — nada a testar"; exit 0; }

while IFS=$'\t' read -r nome porta hostname tipo modo; do
  URL="https://$hostname"
  echo "== $nome ($URL, $modo) =="
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL/health")
  if [ "$code" = 403 ]; then echo "sem credencial: 403 (correto)"
  else echo "FALHA: sem credencial devia dar 403, deu $code"; FALHAS=$((FALHAS+1)); fi

  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -H "$H1" -H "$H2" "$URL/health")
  case "$code" in
    200) echo "com credencial: health ok"
         if [ "$modo" = chat ]; then
           curl -sf --max-time 90 -H "$H1" -H "$H2" -H 'Content-Type: application/json' \
             -d '{"messages":[{"role":"user","content":"Diga apenas: ok"}],"max_tokens":50}' \
             "$URL/v1/chat/completions" >/dev/null \
             && echo "chat ok" || { echo "FALHA: chat"; FALHAS=$((FALHAS+1)); }
         else echo "bot de embedding: chat não se aplica"; fi ;;
    403) echo "AVISO: com credencial deu 403 — esta máquina está fora da rede autorizada (política ok)"; AVISOS=$((AVISOS+1)) ;;
    *)   echo "FALHA: com credencial devia dar 200 (ou 403 fora da rede), deu $code"; FALHAS=$((FALHAS+1)) ;;
  esac
done <<< "$LISTA"

[ $FALHAS = 0 ] && echo "TUDO OK ($AVISOS aviso(s))" || echo "$FALHAS FALHA(S)"
exit $FALHAS
