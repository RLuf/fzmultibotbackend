# External consumers (openclaw, LM Studio, any LAN client)

This project **does not configure** openclaw or LM Studio. They are clients of the llama-server
endpoints like anyone else (ADR 0007). This page only says where to point.

`fzbots url` prints, per bot, the `local` (`http://127.0.0.1:<port>`), `rede` (LAN,
`http://<lan-ip>:<port>`) and, when public, `tunel` (`https://<hostname>`) URLs. Paths are
llama-server's OpenAI-compatible ones:

| Bot | Port | API | Model alias |
|---|---|---|---|
| `embed` | 8082 | `POST /v1/embeddings` | `embeddinggemma-300m` |
| `deephat` | 8084 | `POST /v1/chat/completions`, `/completion` | `DeepHat-V1-7B` |
| `llama` | 8081 | `POST /v1/chat/completions` | (model file) |

Port and alias are a contract with consumers: changing either in `bots.yml` means warning the
consumer (`consumidores:` is the reminder; `fzbots stop`/`undo` refuse without `--forca`).

**openclaw** points `models.providers.deephat.baseUrl` at 8084 (bot `deephat`) and its memory
search at the embedder — directly at `http://127.0.0.1:8082/v1/` (switched 2026-09-08; the prefix
adapter on 8083 is disabled and archived by the "no adapters" decision; llama-server ignores the `input_type` field openclaw
sends). Accepted risk: without EmbeddingGemma's `query:`/`text:` prefixes, memory search may lose
a little quality. Editing `openclaw.json` belongs to openclaw (outside this repo; back it up first —
the exact commands are in the Portuguese page).

**LM Studio (`lms`)** runs its own daemon on walker02 and loads models on its own. It shares
`/root/.lmstudio/models` (`modelos_dir`). Whatever VRAM lms uses counts as "third parties" in the
real VRAM guard of `fzbots apply`/`start`.

Any client: `curl http://<ip>:8081/v1/chat/completions -H 'Content-Type: application/json' -d
'{"messages":[{"role":"user","content":"hi"}]}'`. Over the internet (bots with a hostname): same
paths on `https://<hostname>` with the `CF-Access-Client-Id` / `CF-Access-Client-Secret` headers,
from the authorized network.
