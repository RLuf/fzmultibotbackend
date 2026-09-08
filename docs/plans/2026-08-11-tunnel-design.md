# Design — fzmultibotbackend: llama.cpp atrás de Cloudflare Tunnel

> Histórico. O bind mudou para `0.0.0.0` (ADR 0006) e o undo virou `fzbots undo`, que só
> remove units/ingress gerados e não religa nada no lugar. Ver `docs/pt/arquitetura.md`.

Data: 2026-08-11. Validado com o dono na conversa.

## Objetivo
Expor a API do llama.cpp do walker02 pra internet de forma segura, sem abrir porta
no roteador, protegida por Cloudflare Access (Service Token + rede 138.186.228.0/24).
Base do futuro servidor de bots.

## Arquitetura

```
[ internet ] ──HTTPS──► Cloudflare (Access: Service Token + IP 138.186.228.0/24)
                              │
                    túnel nomeado "fzbots" (conexão de SAÍDA do walker02)
                              │
[ walker02 ]  cloudflared (systemd) ──► http://127.0.0.1:8081  (llama-server)
```

## Decisões
1. **llama-server**: binário existente `/home/dev/null/llama.cpp/build/bin/llama-server`,
   SEM recompilar. Mesmos parâmetros de hoje, só `--host 127.0.0.1`.
   Vira serviço systemd `fzbots-llama.service` (hoje é nohup solto).
   Efeito: acesso via LAN 192.168.0.23:8081 deixa de existir; tudo pelo túnel.
2. **Cert Cloudflare**: reaproveitado de outro servidor da conta (mesmo domínio)
   — sem login no navegador.
3. **Túnel NOVO e separado** `fzbots` → `fzbots.rogerluft.com.br`.
   REGRA: não tocar nos túneis e hostnames já existentes na conta.
4. **Access**: aplicação self-hosted em fzbots.rogerluft.com.br, política
   Service Auth (Service Token) + require IP 138.186.228.0/24. Sem credencial → 403.
5. **Segredos**: nunca no repo nem na conversa. Ficam em
   `/root/walker02-tunnel-access.txt` (root:root 600) e `/etc/cloudflared/`.
6. **RPC/distribuído** (GPU remota): fora do túnel, intocado.

## Estado anterior (pro undo)
Ver `archived/estado-anterior-2026-08-11.md`.

## Undo
`scripts/undo.sh`: para e desabilita os serviços, apaga túnel fzbots + DNS +
app Access, religa o llama-server em 0.0.0.0:8081 via nohup como era.
