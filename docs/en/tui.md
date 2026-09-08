# TUI — `fzbots tui`

The owner's interface. Everything it does calls the same functions as the CLI (`fzbots/*.py`);
the TUI carries no logic of its own. Needs `python3-textual` (installed by `install.sh`).

![Panel](../screenshots/tui-painel.svg)

## Tabs

| Tab | Shows | Keys |
|---|---|---|
| **Painel** (panel) | every bot in `bots.yml`: state (unit + `/health`), port, model, estimated/real VRAM, site, description, consumers; llama-server processes **outside** the yml show as `(externo)`; footer with GPU and the VRAM guard (green = fits) | `s` start · `p` stop · `r` restart · `l` logs · `c` chat · `a` apply --restart · `k` check · `e` edit bots.yml in `$EDITOR` · `F5` refresh |
| **Modelos** (models) | every `.gguf` in `modelos_dir`: size, quant, architecture, max ctx, **estimated VRAM** (read from the GGUF header: weights + KV cache), fits in free VRAM now?, which bots use it | `n` new bot from the selected model · `d` download from Hugging Face |
| **Chat** | streaming chat with a bot; "thinking" models (Qwen3) show `(pensando…)` until the answer; tokens/s at the end | pick the bot, type, Enter |
| **Logs** | `journalctl -f` of the chosen bot's unit | pick the bot |
| **Endpoints** | local / LAN / tunnel URLs per bot with ready `curl` lines; for public bots the Service Token header names (values only in the mode-600 file) | — |

The bottom strip ("saída") shows the result of each action. `q` quits.

## New bot (`n` on the Modelos tab)

Form: name, port (suggested = highest port + 1), context, hostname (empty = internal bot,
`tunel: false`), description, site, alias, "embedding bot". **Ver flags** previews the `extra_args`
that `fzbots flags` suggests and why (fits in free VRAM → `-ngl 99`, else `--fit on`; `-fa on`;
`q8_0` KV for ctx ≥ 8192; `--embedding -b -ub` for embedders; `--jinja`). **Criar e aplicar**
appends the block to `bots.yml` (previous copy in `archived/`, comments preserved), runs `apply`
and starts the unit. The real VRAM guard runs before starting.

## Download (`d`)

Hugging Face repo + `.gguf` file. Without a file it lists the repo's `.gguf` files in the output.
Progress in the output; the model shows up in the Modelos tab when done.

## Headless test

`PYTHONPATH=. python3 tests/tui_headless.py` drives the TUI without a terminal (Textual
`run_test`): loads the panel, runs `check`, lists models, chats with `llama`, follows `embed`
logs and writes the SVGs in `docs/screenshots/`. `--novo-bot` really creates a `tuiteste` bot
from `models/tinyllamas/stories260K.gguf` (download first with `fzbots baixar ggml-org/models
tinyllamas/stories260K.gguf`), starts it, checks `/health` and leaves it in the yml for you to
remove (`apply --prune` after deleting the block).
