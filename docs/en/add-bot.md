# Adding a new bot

Each bot is independent: 1 hostname + 1 llama-server + 1 model of its choice.

1. **Model service** — copy `/etc/systemd/system/fzbots-llama.service` to a new
   unit, change `-m <gguf-path>` and `--port` (keep `--host 127.0.0.1`).
   Mind VRAM: the RTX 2060 has 6 GB total. Enable and start it.
2. **Ingress** — add a hostname entry in `/etc/cloudflared/config.yml` before
   the 404 catch-all, then `cloudflared tunnel route dns fzbots <hostname>` and
   `systemctl restart cloudflared`.
3. **Access** — create a dedicated Access app + Service Token per bot (same
   shape as fzbots, via API using `/root/.cf-api-token`) so each client can be
   revoked independently.
4. **Test** with the Service Token headers against `https://<hostname>/health`.
5. Update the bot table in README and the CHANGELOG.

## Local-only bot (no internet)

Internal service (embedder, private model): add it to `bots.yml` with
`tunel: false` and **no** hostname. `aplicar.sh` writes the unit and leaves the
Cloudflare ingress untouched. Then: `systemctl enable --now fzbots-<name>`.
No DNS route, no Access app.

Models larger than the local GPU's VRAM can use a remote GPU through llama.cpp
RPC (optional feature, out of this scope).
