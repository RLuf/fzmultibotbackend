# Changelog

## [0.1.0] — 2026-08-11

### Added
- Projeto criado: walker02 como backend de bots multi-modelo.
- `fzbots-llama.service` (systemd): llama-server (binário existente, sem
  recompilar) com DeepHat-V1-7B em `127.0.0.1:8081` — antes era nohup em 0.0.0.0.
- cloudflared 2026.7.3 instalado; túnel nomeado `fzbots`
  (80ff35e6-f060-41e3-b986-de8df30fb3b5) → `fzbots.rogerluft.com.br`,
  serviço systemd, cert reaproveitado do walker (só leitura, túneis existentes intocados).
- Cloudflare Access: app `fzbots` com política Service Token + require rede
  `138.186.228.0/24`. Testado: sem credencial → 403; credencial com IP fora → 403.
- Credenciais em `/root/walker02-tunnel-access.txt` (root:root 600).
- Scripts: `status.sh`, `test-tunnel.sh`, `undo.sh`. Docs PT/EN.

### Changed
- Acesso LAN direto `192.168.0.23:8081` desativado (API só em loopback).

### Security
- Nenhuma porta aberta no roteador; RPC/distribuído (hermano) fora do túnel.

## [0.1.1] — 2026-08-11

### Changed
- Bot público (fzbots) agora usa **Qwen3-1.7B Q4_K_M** (unsloth, 1,1 GB) —
  modelo dedicado pra tarefa, ~1,6 GB de VRAM.
- **DeepHat-V1-7B é pessoal**: removido do túnel; movido pro hermano (papaimach),
  servido só pela VPN (llama-server via bundle portátil em ~/rpc-bundle).
- Unit antiga salva em `archived/fzbots-llama.service.deephat-2026-08-11`.

### Validado (2026-08-11)
- Teste positivo pelo túnel confirmado por cliente na rede 138.186.228.0/24
  (IP .18) com Service Token: /health, /v1/models e chat OK.

## [0.2.0] — 2026-08-11

### Added
- **bots.yml**: fonte única da verdade dos bots (nome, hostname, porta, modelo,
  VRAM) — recomendação do architecture-review.
- **scripts/aplicar.sh**: gera units systemd + ingress do cloudflared a partir
  do bots.yml, confere soma de VRAM e porta duplicada, arquiva versões antigas.
- Fluxo de bot novo reduzido a: bloco no bots.yml + aplicar.sh (docs atualizadas).
