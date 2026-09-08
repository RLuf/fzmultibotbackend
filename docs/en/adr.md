# Architecture Decision Records — English summary

Full text (Portuguese, the master copy): `docs/adr/`.

| ADR | Status | Decision | Why |
|---|---|---|---|
| 0001 — API only on 127.0.0.1 | **superseded by 0006** (2026-09-08) | every llama-server bound to loopback; tunnel as the only entry | no open router port; smaller attack surface |
| 0002 — Two-layer Access | accepted | Cloudflare Access requires a valid Service Token **and** a source IP in the authorized network | defence in depth: each layer can fail alone |
| 0003 — bots.yml as source of truth | accepted | bots are declared in `bots.yml`; a generator writes systemd units and the cloudflared ingress; hand-editing is forbidden | copies outside git lie as bots multiply |
| 0004 — One process per bot | accepted | each bot is its own llama-server unit on its own port; no containers | owner asked for the simplest setup; systemd already isolates |
| 0005 — Private bot without tunnel | accepted | `tunel: false` gives a unit and a port but no ingress and no hostname | internal services share the same source of truth without a public URL |
| 0006 — Bind on 0.0.0.0 | accepted (supersedes 0001) | every bot listens on local and LAN; ingress still targets 127.0.0.1 | owner wants direct endpoints for the LAN and for himself; security is not the focus |
| 0007 — External consumers, no adapters | accepted | openclaw and LM Studio are plain consumers; nothing of theirs lives here; llama.cpp is exposed directly | owner's words: no intermediate layers; `deephat` and `embed` become internal bots consumed by openclaw |
