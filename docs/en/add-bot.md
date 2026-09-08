# Adding a new bot

Each bot is independent: 1 port + 1 llama-server + 1 model of its choice. A public bot
also has 1 hostname on the tunnel. Every bot listens on `0.0.0.0` (local and LAN).

## Through the yml

1. **bots.yml** (source of truth, repo root) — add a block:
   ```yaml
   - nome: shop                 # ^[a-z0-9][a-z0-9-]*$ → unit fzbots-shop.service
     descricao: shop X bot      # free text
     site: shop-x.com           # informational: who it serves
     hostname: shop.rogerluft.com.br   # public bots only
     porta: 8085
     modelo: /root/.lmstudio/models/<folder>/<file>.gguf
     vram_estimada: 1.6         # GB — the guard adds what is already on the GPU
     extra_args: "-ngl 99 -c 4096 -fa on"
   ```
   Valid keys: `nome porta modelo vram_estimada` (required), `descricao site hostname
   extra_args tunel consumidores`. Unknown key = error, nothing applied.
2. **Apply** — `fzbots apply --restart`: validates the yml, checks real VRAM, archives what
   it overwrites into `archived/`, writes unit + ingress, starts/restarts only what changed.
   Without `--restart` it prints the `systemctl` commands to run.
3. **DNS** (first time only): `cloudflared tunnel route dns fzbots shop.rogerluft.com.br`.
4. **Access** — create a dedicated Access app + Service Token per bot (same shape as fzbots,
   via API using `/root/.cf-api-token`) so each client can be revoked independently.
5. **Test** — `fzbots status` (local) and `scripts/test-tunnel.sh` (through the tunnel; from
   outside the authorized network the credentialed test returns 403 — a WARNING, not a failure).
6. Update the bot table in README and the CHANGELOG.

## Local-only bot (no tunnel)

Internal service (embedder, openclaw's model, tests): add it with `tunel: false` and **no**
hostname. It gets a unit and a port, never an ingress, and stays reachable on the LAN
(`http://<ip>:<port>`). Real example in `bots.yml`: the `embed` bot (EmbeddingGemma, 8082,
`consumidores: [openclaw]` — informational; `fzbots stop`/`undo` warn before taking it down).

## Removing or renaming a bot

Remove (or rename) the block and run `fzbots apply`. The old unit becomes an **orphan**:
`fzbots check` reports it; `fzbots apply --prune` removes it (archiving first) and **refuses**
if any foreign unit depends on it (`Requires=`). Warn the consumers listed in `consumidores`
first — openclaw, for instance, points at a fixed port and alias.

## Models on disk

`modelos_dir` in `bots.yml` (`/root/.lmstudio/models`, shared with LM Studio). Models larger
than the GPU: use `--fit on` instead of `-ngl 99` (llama-server splits GPU/CPU), as the
`deephat` bot does.
