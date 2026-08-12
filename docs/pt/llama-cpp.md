# llama.cpp — a dependência vital

Todos os bots rodam em cima do **llama-server** do llama.cpp. Sem ele, nada sobe.

## Onde está

| O quê | Onde |
|---|---|
| Binários (build próprio) | `/home/dev/null/llama.cpp/build/bin/` — `llama-server`, `llama-cli`, `ggml-rpc-server` |
| Fonte | `/home/dev/null/llama.cpp` (clone do github.com/ggml-org/llama.cpp, commit 7ba604f) |
| Versão em uso | `version: 1 (7ba604f)`, GCC 15.2.0 |

## Como foi compilado (NÃO recompilar sem pedido — regra 4 do AGENTS.md)

```bash
cd /home/dev/null/llama.cpp
cmake -B build -DGGML_CUDA=ON -DGGML_RPC=ON \
  -DCMAKE_CUDA_ARCHITECTURES=75 -DCMAKE_CUDA_HOST_COMPILER=g++-13 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4 --target llama-server llama-cli ggml-rpc-server
```

- `CUDA_ARCHITECTURES=75` = RTX 2060 (com PTX junto: o binário também roda em
  GPUs mais novas via JIT).
- `GGML_RPC=ON` habilita GPU remota (recurso opcional, fora deste escopo).

## O que o llama-server dá pros bots

- API OpenAI-compat: `/v1/chat/completions`, `/v1/models`
- API crua: `/completion` · Saúde: `/health` · Webui embutida na porta do bot
- `--parallel N` se um bot precisar atender N conversas simultâneas no mesmo modelo

## Flags usadas pelos bots (geradas pelo aplicar.sh a partir do bots.yml)

`-ngl 99` (modelo inteiro na GPU) · `-c 4096` (contexto) · `-fa on` (flash attention)
· `--host 127.0.0.1 --port <porta>` (nunca 0.0.0.0 — regra 7).

## Se quebrar

1. `scripts/status.sh` acusa "binário não encontrado" ou serviço caindo.
2. `journalctl -u fzbots-<nome> -n 50` mostra o erro do llama-server.
3. Erro típico "unable to allocate CUDA buffer" = VRAM estourada — conferir
   `vram_estimada` no bots.yml contra a realidade (`nvidia-smi`).
4. Recompilar só em último caso, com o comando acima (e avisar o dono).
