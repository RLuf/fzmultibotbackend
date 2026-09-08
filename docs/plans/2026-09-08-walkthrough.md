# Walkthrough — 2026-09-08: review arquitetural → produto (fzbots CLI + TUI + install)

Plano aprovado: `/root/.claude/plans/modules-patterns-depends-peppy-volcano.md` (cópia das decisões
em `AGENTS.md`, ADRs 0006–0008 e no CHANGELOG 0.5.0–0.7.0). Tudo abaixo foi executado nesta
sessão no walker02; as saídas são reais (colhidas dos comandos, não redigidas).

## Fase 1 — núcleo `fzbots` + correções do review (CHANGELOG 0.5.0)

| Passo do plano | Feito | Evidência |
|---|---|---|
| archived/ de tudo que seria alterado | sim | 50 arquivos `archived/*.20260908_*` (inclui as units do openclaw e o config.yml do cloudflared) |
| Pacote `fzbots/` (config/systemd/gpu/api/cli) | sim | `bin/fzbots --help` lista 18 subcomandos |
| Golden diff antes de mudar o bind | sim | `render_unit` com `BIND=127.0.0.1` × `/etc`: `llama: igual`, `embed: igual`, ingress `True` |
| bind 0.0.0.0, `llama_bin`/`modelos_dir`/`lan_ip`, bot `deephat`, validação, VRAM real, escrita atômica, restart vs enable | sim | `ss -tlnp` → `0.0.0.0:8081`, `0.0.0.0:8082`, `0.0.0.0:8084` |
| Cutover deephat (openclaw-deephat → fzbots-deephat, mesma porta/alias) | sim | `curl :8084/v1/models` → `DeepHat-V1-7B`; nvidia-smi: 3318 MiB em `fzbots-deephat.service`; unit antiga em `archived/openclaw-deephat.service.removida.*` |
| Adapter 8083 → openclaw aponta para 8082 direto | sim (10:32, com autorização do dono) | backup `openclaw.json.bak.fzbots-20260908_103211`; `baseUrl: 8083 → 8082`; unit do adapter desativada e arquivada; gateway registrou `[reload] config change detected (memorySearch.remote.baseUrl)` e voltou com o plugin `active-memory`; `fzbots-embed` sem `RequiredBy`; `curl :8082/v1/embeddings` com `input_type` → 200. Os erros no journal do gateway (login Anthropic expirado, MCP firecrawl, xAI 403) são anteriores e alheios. |
| Wrappers + test-tunnel com 403 = aviso | sim | `scripts/test-tunnel.sh` → `TUDO OK (1 aviso(s))` (walker02 está fora da rede autorizada) |
| Docs | sim | AGENTS.md (regra zero + 15 regras), ADR 0001 substituída, 0006, 0007, arquitetura PT+EN, adicionar-bot PT+EN, README, CHANGELOG reordenado, `systemd/` removido |

Verificações do plano: `fzbots check` exit 0 e "em sincronia" · túnel sem credencial → 403 ·
`curl http://192.168.0.23:808{1,2,4}/health` → `{"status":"ok"}` do próprio host **e do walker**
(`ssh walker` → `walker.storageweb`, 8081/8082/8084 `{"status":"ok"}`) · bot fictício `vram_estimada: 2.0` → `ERRO … 7.4 / 6 GB,
Nada aplicado`, rc 2 · `tunnel: false` → `chave desconhecida`, rc 2 · unit `fzbots-teste.service`
à mão → `FALHA: ÓRFÃ`, rc 1 · `apply --prune` com órfã que tem `Requires=` externo → recusa,
rc 2, unit preservada · `fzbots stop embed` → recusa (`openclaw-embeddinggemma-adapter.service,
openclaw`) · yml com modelo inexistente → `Nada aplicado`.

## Fase 2 — CLI completa + install.sh + completions (CHANGELOG 0.6.0)

| Passo | Evidência |
|---|---|
| `fzbots modelos` | 6 `.gguf` listados com quant, arquitetura, ctx máx e VRAM estimada do cabeçalho GGUF (llama 1,65 GB × yml 1,6; embed 0,51 × 0,5) |
| `fzbots flags` | ctx 8192 → `--fit on -c 8192 -fa on -ctk q8_0 -ctv q8_0 --jinja` com explicação; alias com espaço → rc 2 |
| `fzbots baixar` | `ggml-org/models tinyllamas/stories260K.gguf` → 1,1 MiB com progresso; repo com 26 ggufs → lista e pede escolha |
| `fzbots chat` | `llama -m "Responda só com a palavra: pronto"` → `(pensando…) pronto`, 103 tokens, 139 tok/s; `deephat` responde |
| `fzbots embed` | dimensão 768 |
| `install.sh` | rodado 2× de dentro do clone: apt ok, symlinks `/usr/local/bin/fzbots` e `/etc/bash_completion.d/fzbots`, `llama-server ok`, `em sincronia`, rc 0 |
| completions | `complete -F _fzbots fzbots` |

## Fase 3 — TUI Textual (CHANGELOG 0.6.0, ADR 0008)

`PYTHONPATH=. python3 tests/tui_headless.py --novo-bot` (Textual `run_test`, sem terminal), última execução:

```
OK   painel: 3 linhas: ['llama', 'embed', 'deephat']
OK   bots ativos no painel: ['llama', 'embed', 'deephat']
OK   rodapé GPU: GPU NVIDIA GeForce RTX 2060: 5458 / 6144 MiB · VRAM: bots.yml 5.4 GB + terceiros 0.0 …
OK   tecla k → check rodou dentro da TUI
OK   modelos: 7 .gguf listados
OK   aba endpoints renderizada
OK   chat na TUI respondeu: … 'llama:' …
OK   logs: 95 linhas do journal de fzbots-embed
OK   tecla d abriu o formulário Baixar
OK   download pela TUI gravou /root/.lmstudio/models/models/tinyllamas/stories260K.gguf (1185376 bytes)
OK   aba Modelos atualizou com o arquivo baixado
OK   tecla n abriu o formulário NovoBot
OK   preview de flags: extra_args: -ngl 99 -c 512 -fa on --jinja
OK   novo bot tuiteste no ar na porta 8085 com '-ngl 99 -c 512 -fa on --jinja'
OK   unit fzbots-tuiteste ativa
OK   painel mostra o bot novo
OK   tecla p parou fzbots-tuiteste (systemctl: deactivating)
OK   tecla s subiu de novo e /health responde
TUI headless: TUDO OK
```

Depois: bloco `tuiteste` removido do yml, `apply --prune` removeu a unit (cópia em `archived/`),
modelo de teste apagado. Screenshots SVG em `docs/screenshots/` (README os exibe).

## Fase 4 — `scripts/build-llama.sh` (CHANGELOG 0.7.0)

Feito por agente separado. Container LXD `ubuntu:24.04` `fzbots-build`: build CPU completo,
`llama-server --version` → `0.4.0-dev (build 1, commit 5266f24)`; `llama-cli`, `ggml-rpc-server`
respondem; container apagado (`lxc list` vazio). No walker02 só `--detectar`: RTX 2060 → arch 75,
nvcc 12.4, gcc 15 → g++-13, avx2 fma f16c, 4 núcleos; `/home/dev/null/llama.cpp` segue em `7ba604f`;
`/opt/llama.cpp` não existe. Caminho CUDA validado só até o comando cmake gerado.

## Revisões de código (agente `code-reviewer`, 2 rodadas)

Fase 1: 17 achados → 17 tratados (lista no CHANGELOG 0.7.0 "Fixed — revisão da Fase 1").
Fases 2+3: 18 achados → 16 tratados (CHANGELOG 0.7.0 "Fixed — revisão das Fases 2 e 3"); os 2 restantes
são observações (teste acoplado ao host por desenho; `-c` fixo mesmo com `--fit`, decisão mantida:
contexto do bot não muda sozinho).

## Limites

- Build CUDA real do `build-llama.sh` não foi executado (só o comando cmake gerado).
- Antes de tornar o repo público, o histórico foi varrido: nenhum valor de token/segredo. Ficam no
  histórico (não na árvore) o UUID do túnel, o id da conta Cloudflare e o id do app Access — não são
  segredos (exigem credencial para servir de algo); o dono decidiu publicar.

## Estado final

`fzbots check` → em sincronia · `fzbots status` → TUDO OK · 3 units ativas em `0.0.0.0` ·
GPU 5458/6144 MiB (deephat 3318, llama 1654, embed 476) · `lxc list` vazio · 14 unittests OK.
