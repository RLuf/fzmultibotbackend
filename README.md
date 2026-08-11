# fzmultibotbackend

**PT** | [EN below](#english)

Backend de bots do walker02: modelos locais (llama.cpp) servidos com segurança
pela internet via Cloudflare Tunnel + Access. Cada bot é independente e escolhe
seu próprio modelo.

## Como funciona

```
[ internet ] ──HTTPS──► Cloudflare (Access: Service Token + rede autorizada)
                              │
                    túnel "fzbots" (sem porta aberta no roteador)
                              │
[ walker02 ]  cloudflared ──► 127.0.0.1:8081  bot pessoal (DeepHat-V1-7B)
                         └──► 127.0.0.1:####  próximos bots (1 porta = 1 modelo)
```

- **1 bot = 1 hostname + 1 llama-server + 1 modelo.** Adicionar bot = nova
  entrada no ingress + novo serviço systemd (ver `docs/pt/adicionar-bot.md`).
- API nunca escuta na rede — só `127.0.0.1`. Sem porta aberta no roteador.
- Acesso exige Service Token **e** vir da rede autorizada; o resto leva 403.

## Bots ativos

| Bot | Hostname | Porta local | Modelo | Uso |
|---|---|---|---|---|
| fzbots (pessoal) | fzbots.rogerluft.com.br | 8081 | DeepHat-V1-7B Q4_K_M | dono |

## Operação

```bash
scripts/status.sh       # saúde de tudo (serviços, túnel, GPU, API)
scripts/test-tunnel.sh  # testes pelo túnel (lê credencial do arquivo 600)
scripts/undo.sh         # desfaz tudo e volta ao estado anterior
```

Credenciais e instruções de acesso: `/root/walker02-tunnel-access.txt` (600).
Documentação completa: [`docs/pt/`](docs/pt/) · Design: [`docs/plans/`](docs/plans/)

---

## English

Bot backend for walker02: local models (llama.cpp) served securely to the
internet through Cloudflare Tunnel + Access. Each bot is independent and picks
its own model.

- **1 bot = 1 hostname + 1 llama-server + 1 model.** Adding a bot = new ingress
  entry + new systemd unit (see `docs/en/add-bot.md`).
- The API only listens on `127.0.0.1` — no router ports opened.
- Access requires a Service Token **and** an authorized source network;
  everything else gets 403.

Active bots: see table above. Operations: `scripts/status.sh`,
`scripts/test-tunnel.sh`, `scripts/undo.sh`. Credentials live in
`/root/walker02-tunnel-access.txt` (mode 600). Full docs in [`docs/en/`](docs/en/).
