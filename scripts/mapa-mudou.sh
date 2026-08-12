#!/bin/bash
# Refresh inteligente do mapa (ideia do dono): só trabalha se algo mudou.
# Compara o sha256 do que alimenta o mapa com o da última publicação.
#   exit 0 = MUDOU (republicar o mapa)  ·  exit 1 = igual (não fazer nada)
# Quem republica é o agente (Claude), na URL fixa:
#   https://claude.ai/code/artifact/deb23b04-bae3-452b-8e71-62a0bbacf299
cd "$(dirname "$0")/.."
STAMP=.mapa.sha256
ATUAL=$(cat bots.yml docs/pt/arquitetura.md 2>/dev/null | sha256sum | cut -d' ' -f1)
ANTERIOR=$(cat "$STAMP" 2>/dev/null)
if [ "$ATUAL" = "$ANTERIOR" ]; then
  echo "mapa em dia (hash igual) — nada a fazer"
  exit 1
fi
echo "MUDOU: republicar o mapa e depois rodar: echo $ATUAL > $STAMP"
exit 0
