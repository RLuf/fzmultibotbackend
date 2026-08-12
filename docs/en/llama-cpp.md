# llama.cpp — the vital dependency

All bots run on llama.cpp's **llama-server**. Binaries (own build, commit 7ba604f,
CUDA arch 75 + PTX, RPC enabled) live in `/home/dev/null/llama.cpp/build/bin/`.

Build command, serving endpoints, per-bot flags and troubleshooting: see the
Portuguese master doc [`docs/pt/llama-cpp.md`](../pt/llama-cpp.md). Key rules:
never recompile without an explicit request (AGENTS.md rule 4) and bots always
bind `127.0.0.1` (rule 7). `scripts/status.sh` checks the binary on every run.
