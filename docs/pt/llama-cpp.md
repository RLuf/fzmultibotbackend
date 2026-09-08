# llama.cpp — a dependência vital

Todos os bots rodam em cima do **llama-server** do llama.cpp. Sem ele, nada sobe.

## Onde está

| O quê | Onde |
|---|---|
| Binários (build próprio) | `/home/dev/null/llama.cpp/build/bin/` — `llama-server`, `llama-cli`, `ggml-rpc-server` |
| Fonte | `/home/dev/null/llama.cpp` (clone do github.com/ggml-org/llama.cpp, commit 7ba604f) |
| Versão em uso | `version: 1 (7ba604f)`, GCC 15.2.0 |

## Máquina nova: `scripts/build-llama.sh`

Em uma máquina sem llama.cpp, o `install.sh` chama `scripts/build-llama.sh --prefix /opt/llama.cpp`.
O script detecta sozinho e explica cada escolha: GPU NVIDIA e compute capability
(`nvidia-smi` → `CMAKE_CUDA_ARCHITECTURES`), `nvcc`, compilador host compatível com o nvcc
(`g++-13` quando o gcc padrão é 14/15), flags da CPU (`GGML_NATIVE=ON`), núcleos e RAM (`--jobs`),
sempre `GGML_RPC=ON` e `Release`; alvos `llama-server llama-cli ggml-rpc-server`. Sem GPU (ou
`--cpu-only`) faz build de CPU. `--ref` fixa tag/commit (padrão: última release do GitHub; para
reproduzir o build do walker02, `--ref 7ba604f`). `--detectar` só imprime a detecção e o comando
cmake, sem baixar nem compilar — seguro em qualquer máquina. Nunca toca em `/home/dev/null/llama.cpp`.

Testado em 2026-09-08 num container LXD `ubuntu:24.04` descartável (build CPU completo, `llama-server
--version` = `0.4.0-dev (build 1, commit 5266f24)`) e com `--detectar` no walker02 (RTX 2060 → arch 75,
nvcc 12.4, gcc 15 → g++-13, avx2 fma f16c, 4 núcleos). O caminho CUDA foi validado só até o comando
cmake gerado (idêntico ao build documentado abaixo); não foi compilado em lugar nenhum.

## Como foi compilado no walker02 (NÃO recompilar sem pedido — regra 4 do AGENTS.md)

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

- API OpenAI-compat: `/v1/chat/completions`, `/v1/models`, e `/v1/embeddings` quando o bot sobe com `--embedding`
- API crua: `/completion` · Saúde: `/health` · Webui embutida na porta do bot
- `--parallel N` se um bot precisar atender N conversas simultâneas no mesmo modelo

## Flags usadas pelos bots (geradas pelo `fzbots apply` a partir do bots.yml)

`-ngl 99` (modelo inteiro na GPU) · `-c 4096` (contexto) · `-fa on` (flash attention)
· `--host 0.0.0.0 --port <porta>` (local e rede — ADR 0006). O caminho do binário é o
`llama_bin` do `bots.yml` — único lugar onde ele aparece.

O bot `deephat` usa `--fit on --fit-target 256 --fit-ctx 2048` no lugar de `-ngl 99`: o
llama-server divide o modelo entre GPU e CPU para caber ao lado dos outros bots.

O bot `embed` acrescenta `-b 2048 -ub 2048`. Em modo embedding, o llama-server
iguala o batch lógico ao físico; sem `-ub`, o padrão físico de 512 fazia chunks
válidos do EmbeddingGemma falharem antes da inferência. O paralelismo fica
automático: fixar quatro slots neste build divide a janela em 512 por slot.

## Se quebrar

1. `fzbots status` acusa "binário não encontrado" ou serviço caindo.
2. `journalctl -u fzbots-<nome> -n 50` mostra o erro do llama-server.
3. Erro típico "unable to allocate CUDA buffer" = VRAM estourada — `fzbots check`
   mostra o uso real por unit e o que terceiros (lms, etc.) estão ocupando.
4. Recompilar só em último caso, com o comando acima (e avisar o dono).
