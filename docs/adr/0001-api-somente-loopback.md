# ADR 0001 — API só em 127.0.0.1

Data: 2026-08-11 · Status: aceita

**Decisão**: todo llama-server escuta apenas em 127.0.0.1; nenhuma porta aberta
no roteador; a única entrada é o Cloudflare Tunnel.

**Porquê**: antes o servidor escutava em 0.0.0.0 na LAN. Com a exposição pública,
qualquer porta escutando na rede vira superfície de ataque e depende do roteador.
O túnel inverte o fluxo (conexão de SAÍDA), eliminando porta aberta.

**Consequência**: o acesso LAN direto (192.168.0.23:8081) deixou de existir.
