# ADR 0003 — bots.yml como fonte da verdade + gerador

Data: 2026-08-11 · Status: aceita

**Decisão**: os bots são declarados em bots.yml; scripts/aplicar.sh gera units
systemd e ingress do cloudflared a partir dele. Proibido editar unit/ingress na mão.

**Porquê**: o architecture-review apontou que o estado real vivia fora do git
(/etc) e o repo tinha só cópias — com vários bots, as cópias mentiriam. Com mais
bots a caminho, o custo de arrumar cresceria a cada bot novo.

**Consequência**: bot novo = 5 linhas no yml + 1 comando; o gerador (hoje `fzbots apply`)
valida VRAM real, porta duplicada e existência do modelo antes de aplicar; arquiva o que
sobrescreve; `fzbots check` acusa qualquer drift entre o yml e o host.
