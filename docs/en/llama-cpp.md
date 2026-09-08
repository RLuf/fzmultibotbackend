# llama.cpp — the vital dependency

All bots run on llama.cpp's **llama-server**. Binaries (own build, commit 7ba604f,
CUDA arch 75 + PTX, RPC enabled) live in `/home/dev/null/llama.cpp/build/bin/`.

Build command, serving endpoints, per-bot flags and troubleshooting: see the
Portuguese master doc [`docs/pt/llama-cpp.md`](../pt/llama-cpp.md). Key rules:
never recompile without an explicit request (AGENTS.md rule 4) and bots always
bind `0.0.0.0` (ADR 0006). The binary path is `llama_bin` in `bots.yml` — the only place it
appears. `fzbots status` checks the binary on every run.

The `embed` bot also sets `-b 2048 -ub 2048`. In embedding mode llama-server
aligns the logical batch with the physical batch; the default 512-token
physical batch otherwise rejects valid EmbeddingGemma chunks before inference.
Parallelism remains automatic because forcing four slots on this build divides
the context into 512 tokens per slot.

The `deephat` bot uses `--fit on --fit-target 256 --fit-ctx 2048` instead of `-ngl 99`, so
llama-server splits the model between GPU and CPU to fit next to the other bots.

## New machine: `scripts/build-llama.sh`

When llama.cpp is missing, `install.sh` runs `scripts/build-llama.sh --prefix /opt/llama.cpp`. It
detects and explains every choice: NVIDIA GPU + compute capability (`CMAKE_CUDA_ARCHITECTURES`),
`nvcc`, a host compiler the nvcc accepts (`g++-13` when the default gcc is 14/15), CPU flags
(`GGML_NATIVE=ON`), cores and RAM (`--jobs`); always `GGML_RPC=ON` + `Release`; targets
`llama-server llama-cli ggml-rpc-server`. No GPU (or `--cpu-only`) → CPU build. `--ref` pins a
tag/commit (default: latest GitHub release; `--ref 7ba604f` reproduces walker02's build).
`--detectar` only prints the detection and the cmake command — safe anywhere. It never touches
`/home/dev/null/llama.cpp`. Tested 2026-09-08 in a throwaway LXD `ubuntu:24.04` container (full CPU
build, `llama-server --version` = `0.4.0-dev (build 1, commit 5266f24)`) and with `--detectar` on
walker02 (RTX 2060 → arch 75, nvcc 12.4, gcc 15 → g++-13, avx2 fma f16c, 4 cores). The CUDA path
was validated only up to the generated cmake command.
