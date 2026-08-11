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
