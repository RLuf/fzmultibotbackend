# Changelog

## [0.4.0] — 2026-08-16

### Added
- Campo `tunel: false` no `bots.yml`: bot interno (unit + loopback) sem ingress
  no Cloudflare. ADR 0005.
- Bot `embed` (porta 8082): EmbeddingGemma 300M QAT Q8_0, só embeddings,
  fora do túnel. Modelo em `/root/.lmstudio/models/embeddinggemma-300m/`.
- `aplicar.sh` / `test-tunnel.sh` respeitam o campo. Docs PT/EN atualizados.

## [0.1.0] — 2026-08-11

### Added
- Projeto criado: walker02 como backend de bots multi-modelo.
- `fzbots-llama.service` (systemd): llama-server (binário existente, sem
  recompilar) servindo em `127.0.0.1:8081` — antes era processo solto em 0.0.0.0.
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
- Nenhuma porta aberta no roteador; serviços fora do bots.yml ficam fora do túnel.

## [0.1.1] — 2026-08-11

### Changed
- Bot público (fzbots) agora usa **Qwen3-1.7B Q4_K_M** (unsloth, 1,1 GB) —
  modelo dedicado pra tarefa, ~1,6 GB de VRAM.
- Modelo de uso privado removido do túnel e realocado fora deste servidor
  (acesso somente por rede privada).
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

## [0.3.0] — 2026-08-12

### Added
- **llama.cpp oficialmente no escopo**: doc dedicada (`docs/pt/llama-cpp.md` +
  EN), regra 10 no AGENTS.md, checagem do binário no `status.sh`.
- **Documentação de arquitetura**: `docs/pt/arquitetura.md` (C4 níveis 1-2 em
  mermaid, fluxo, invariantes) + 4 ADRs em `docs/adr/` (loopback, dupla camada,
  bots.yml, 1 processo por bot).
- README (PT/EN): diagrama mermaid na página inicial, links pra arquitetura/ADRs.

### Changed
- **Scripts multibot** (recomendações do architecture-review, antigos em archived/):
  `status.sh`, `test-tunnel.sh` e `undo.sh` agora leem o bots.yml — zero ID na
  unha — e retornam código de erro (servem de sonda). undo.sh lê IDs do Access
  do arquivo de credenciais.
- AGENTS.md: regras 8 (conformidade total de docs), 9 (bots.yml fonte da verdade).

### Added (mapa vivo)
- Mapa do fluxo publicado como página (URL fixa, atualizada a cada mudança):
  https://claude.ai/code/artifact/deb23b04-bae3-452b-8e71-62a0bbacf299
- `scripts/mapa-mudou.sh`: refresh inteligente por sha256 (só republica se
  bots.yml ou arquitetura.md mudaram). Carimbo em `.mapa.sha256`.

### Changed (sanitização pra apresentação)
- Documentação limpa de nomes de modelos privados e de máquinas fora deste
  servidor — apta pra apresentação de produto. Originais em archived/.
- Mapa publicado atualizado na mesma URL.
