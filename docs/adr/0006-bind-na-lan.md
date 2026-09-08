# ADR 0006 — Todo bot escuta em 0.0.0.0 (local + rede)

Data: 2026-09-08 · Status: aceita · Substitui a ADR 0001

**Decisão**: cada llama-server sobe com `--host 0.0.0.0`. O endpoint fica acessível em
`127.0.0.1:<porta>`, em `<ip-da-lan>:<porta>` e, se o bot tiver `hostname`, em
`https://<hostname>` pelo túnel. O ingress do cloudflared continua apontando para
`127.0.0.1:<porta>`.

**Porquê** (palavras do dono): o software deve "proporcionar ao dono interação com os
modelos carregados" e "fornecer endpoint llama.cpp diretamente para ser usado também
local e pela rede". Segurança não é o foco deste trabalho; simplicidade e
funcionalidade são. O roteador continua sem porta aberta — a LAN é a rede do dono.

**Consequência**: a regra 7 antiga (loopback) saiu do AGENTS.md. `fzbots url` mostra
as três URLs de cada bot. Consumidores locais (openclaw, lms) falam direto com o
llama-server. Quem está na LAN alcança qualquer bot, inclusive os privados (`tunel: false`)
— "privado" significa "fora do túnel", não "fora da LAN".
