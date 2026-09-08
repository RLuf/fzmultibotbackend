# Install

## One line (fresh Ubuntu/Debian machine, as root)

```bash
curl -fsSL https://raw.githubusercontent.com/RLuf/fzmultibotbackend/master/install.sh | bash
```

Or inside a clone: `sudo ./install.sh`. `--build` compiles llama.cpp without asking when it is missing.

## What install.sh does (idempotent)

1. `apt-get install python3 python3-yaml python3-textual python3-rich curl jq git`.
2. Uses the current clone (when run from inside it) or clones into `/opt/fzmultibotbackend`
   (`FZBOTS_DIR` overrides). Existing clone → `git pull --ff-only`.
3. Creates `/usr/local/bin/fzbots` and the bash completion at `/etc/bash_completion.d/fzbots`.
4. Checks `llama_bin` from `bots.yml`. If missing, asks (or `--build`) and runs
   `scripts/build-llama.sh --prefix /opt/llama.cpp`, which downloads and compiles llama.cpp with
   the optimizations it detects itself (GPU/CUDA, host compiler, CPU flags), then writes the new
   path into `llama_bin`. On walker02 the binary already exists → nothing is compiled (rule 4).
5. Warns when a bot has a `hostname` but `cloudflared` is not installed (the tunnel needs the
   account certificate — manual step below).
6. Runs `fzbots check` and prints the next step.

## After install

```bash
fzbots tui                 # the owner's interface: see, start, stop, download, chat
fzbots apply --restart     # apply bots.yml (units + ingress), start/restart what changed
fzbots status              # full health
```

## Cloudflare tunnel (public bots only, once per machine)

1. Install `cloudflared` and copy the account certificate to `/root/.cloudflared/cert.pem`.
2. `cloudflared tunnel create fzbots`; write `tunnel:` and `credentials-file:` into
   `/etc/cloudflared/config.yml` (see `cloudflared/config.yml.example`). `ingress:` is generated
   by `fzbots apply`.
3. `systemctl enable --now cloudflared`.
4. Per hostname: `cloudflared tunnel route dns fzbots <hostname>` + an Access app with a
   Service Token (see `docs/en/add-bot.md`).

## Uninstall what the project generated

`fzbots undo`: stops and removes the `fzbots-*` units (copies in `archived/`) and resets the
ingress. It never deletes the tunnel, DNS or Access — those stay in the Cloudflare dashboard.
It refuses when a foreign unit depends on a bot (`--forca` to insist).
