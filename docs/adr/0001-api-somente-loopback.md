# ADR 0001 — API só em 127.0.0.1

Data: 2026-08-11 · Status: **substituída pela ADR 0006 em 2026-09-08**

**Decisão (na época)**: todo llama-server escuta apenas em 127.0.0.1; nenhuma porta aberta
no roteador; a única entrada é o Cloudflare Tunnel.

**Porquê**: antes o servidor escutava em 0.0.0.0 na LAN. Com a exposição pública,
qualquer porta escutando na rede vira superfície de ataque e depende do roteador.
O túnel inverte o fluxo (conexão de SAÍDA), eliminando porta aberta.

**O que mudou**: o dono decidiu que os endpoints devem servir também a rede local
(consumidores como openclaw, LM Studio e o próprio dono). Ver ADR 0006. O túnel
continua sendo a única entrada pela internet; o roteador continua sem porta aberta.
