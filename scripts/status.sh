#!/bin/bash
# Saúde do fzmultibotbackend — multibot, lê bots.yml.
# Sai com código != 0 se algo estiver mal (serve de sonda pra automação).
cd "$(dirname "$0")/.."
FALHAS=0
LLAMA_BIN=/home/dev/null/llama.cpp/build/bin/llama-server

echo "== llama.cpp (dependência vital) =="
if [ -x "$LLAMA_BIN" ]; then
  echo "binário ok: $LLAMA_BIN ($($LLAMA_BIN --version 2>&1 | head -1))"
else
  echo "FALHA: binário não encontrado: $LLAMA_BIN"; FALHAS=$((FALHAS+1))
fi

echo "== Túnel =="
if systemctl is-active --quiet cloudflared; then
  echo "cloudflared: active"
else
  echo "FALHA: cloudflared parado"; FALHAS=$((FALHAS+1))
fi

echo "== Bots (bots.yml) =="
while IFS=$'\t' read -r nome porta hostname; do
  svc="fzbots-$nome"
  ok=1
  systemctl is-active --quiet "$svc" || { echo "FALHA: $svc parado"; ok=0; }
  curl -sf --max-time 5 "http://127.0.0.1:$porta/health" >/dev/null \
    || { echo "FALHA: $nome não responde em 127.0.0.1:$porta"; ok=0; }
  ss -tln "sport = :$porta" | grep -q 127.0.0.1 \
    || { echo "AVISO: porta $porta não está restrita a 127.0.0.1"; ok=0; }
  [ $ok = 1 ] && echo "ok: $nome (porta $porta, $hostname)" || FALHAS=$((FALHAS+1))
done < <(python3 -c "
import yaml
for b in yaml.safe_load(open('bots.yml'))['bots']:
    print(f\"{b['nome']}\t{b['porta']}\t{b.get('hostname') or '-'}\")")

echo "== GPU =="
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader

[ $FALHAS = 0 ] && echo "TUDO OK" || echo "$FALHAS FALHA(S)"
exit $FALHAS
