# ADR 0005 — Bot privado sem túnel (`tunel: false`)

Data: 2026-08-16 · Status: aceita

**Decisão**: um bot no `bots.yml` pode ter `tunel: false`. Ganha unit systemd e
porta em `127.0.0.1`, mas **não** entra no ingress do Cloudflare e não exige
hostname público.

**Porquê**: o embedder do Metadron (e qualquer serviço interno) precisa viver na
mesma fonte da verdade dos bots, sem ganhar URL na internet. A regra “modelos
privados não entram no túnel” já existia; faltava o campo no yml para o
`aplicar.sh` não mentir.

**Consequência**: `status.sh` continua cobrindo saúde local. `test-tunnel.sh`
ignora esses bots. Bot público continua exigindo `hostname`.
