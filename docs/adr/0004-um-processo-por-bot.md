# ADR 0004 — 1 bot = 1 processo (sem containers)

Data: 2026-08-11 · Status: aceita

**Decisão**: cada bot é um llama-server próprio (unit systemd) numa porta local,
com o modelo que escolher. Sem LXC/containers.

**Porquê**: pedido do dono ("da forma mais simples possível, sem lxc se possível").
O isolamento necessário (falha de um bot não derruba outro; modelos independentes)
o processo + systemd já dão. Container acrescentaria camada de operação sem
benefício proporcional nesta escala. Orquestradores prontos foram avaliados e
descartados antes.

**Consequência**: escala limitada pela VRAM da 2060 (6 GB) — conferida pelo
aplicar.sh. Modelos grandes têm caminho (RPC do llama.cpp pra GPU remota).
