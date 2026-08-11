#!/bin/bash
# Saúde do fzmultibotbackend
echo "== Serviços =="
for s in fzbots-llama cloudflared; do printf '%-14s %s\n' "$s:" "$(systemctl is-active $s)"; done
echo "== Portas locais (só 127.0.0.1 esperado) =="
ss -tlnp | grep -E ':8081' || echo "8081 não está escutando!"
echo "== GPU =="
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
echo "== API local =="
curl -s --max-time 5 http://127.0.0.1:8081/health || echo "API não responde"
echo
echo "== Túnel =="
cloudflared tunnel info fzbots 2>/dev/null | head -8
