# ADR 0002 — Dupla camada no Access (Service Token E rede)

Data: 2026-08-11 · Status: aceita

**Decisão**: a política do Cloudflare Access exige Service Token válido E origem
na rede 138.186.228.0/24, simultaneamente.

**Porquê** (palavras do dono): "a rede é segura, é só uma segurança adicional" —
defesa em camadas: a rede fecha o perímetro, o token diz QUEM é. Cada camada pode
falhar sozinha que a outra segura. Token vazado sem a rede não entra; máquina na
rede sem token não entra.

**Consequência**: testes positivos só passam de dentro da rede autorizada;
validado em 2026-08-11 do IP .18.
