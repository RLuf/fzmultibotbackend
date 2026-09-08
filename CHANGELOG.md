# Changelog

## [0.7.0] — 2026-09-08

### Added
- **`scripts/build-llama.sh`**: baixa e compila o llama.cpp detectando sozinho GPU/compute
  capability, nvcc, compilador host (`g++-13` com gcc 14/15), flags de CPU, núcleos e RAM;
  `--detectar` (só mostra), `--prefix`, `--ref`, `--jobs`, `--cpu-only`; instala dependências de
  build via apt só quando compila; nunca toca no build existente do walker02. Chamado pelo
  `install.sh` quando `llama_bin` não existe. Testado em container LXD `ubuntu:24.04` descartável
  (build CPU completo até `llama-server --version`) e com `--detectar` no walker02. O caminho
  CUDA foi validado só até o comando cmake gerado.
- Docs: seção "Máquina nova" em `docs/pt/llama-cpp.md` e `docs/en/llama-cpp.md`;
  `docs/pt/consumidores-externos.md` e `docs/en/external-consumers.md` (onde openclaw, lms e
  qualquer cliente apontam; comandos da troca do adapter, que ficam do lado do openclaw).

### Fixed (revisão de código da Fase 1)
- `test-tunnel.sh` dizia "TUDO OK" se o `fzbots list` falhasse (loop vazio); agora aborta.
- `fzbots undo` não depende mais do `bots.yml` (tem que funcionar com o yml quebrado).
- `extra_args` com aspa aberta virava traceback; agora é `ERRO no bots.yml` (exit 2). `%` em
  caminhos/flags é rejeitado (o systemd expande `%`). `llama_bin` com espaço é rejeitado.
- `nvidia-smi` falhando era tratado como "GPU vazia": agora a trava e o `start` recusam
  ("não sei" ≠ "livre"); uso `[N/A]` idem. `systemctl show` falhando em `dependentes()` vira erro
  em vez de "sem dependente". Unit `fzbots-*` órfã rodando conta como terceiro na VRAM.
- `apply --restart` também sobe unit igual mas parada/falhada.
- `--port=8081` (forma com `=`) reconhecido ao identificar processos por porta.
- `dependentes()` ignora qualquer `*.target` (não só `multi-user.target`).
- Início do cloudflared lido do timestamp monotônico (sem depender de locale); se não der,
  AVISO explícito em vez de silêncio. `start` avisa quando a porta já está ocupada.
- Wrappers `scripts/*.sh` seguem symlink (`readlink -f`). Exceção inesperada na CLI vira
  `ERRO (...)` com exit 1, não traceback. `check` com avisos não diz só "em sincronia".
- `info()` soma todas as GPUs; `lan_ip` ignora também tailscale/zerotier/ppp/tap.
- `fzbots check` acusa modelo que sumiu do disco (antes só o `apply` conferia).

### Fixed (revisão de código das Fases 2 e 3)
- Estimativa de VRAM e flags agora concordam: com ctx ≥ 8192 a decisão "cabe na GPU" usa KV em
  q8_0, o mesmo que as flags pedem (antes decidia com f16 e mandava q8_0).
- Modelos particionados (`-00001-of-0000N.gguf`): tamanho soma todos os shards e a lista mostra
  um só item; antes cada shard aparecia sozinho e a VRAM ficava subestimada.
- `listar()` lia o cabeçalho GGUF duas vezes por arquivo e andava vocabulários inteiros elemento
  a elemento; agora reaproveita o cabeçalho e pula arrays grandes com `seek`.
- TUI: F5 não apaga mais a conversa do chat (os Selects preservam a escolha ao repopular);
  bot recém-criado entra nos Selects assim que o yml novo é carregado; `c`/`l` num bot que ainda
  não está na lista avisam em vez de derrubar a TUI; `journalctl` é aberto na thread principal.
- Detecção de embedding pela arquitetura do GGUF (`bert`, `gemma-embedding`, …), nome só como
  fallback. Alias com espaço é rejeitado (quebraria a unit).
- `fzbots chat`/`embed`: erro de rede no meio da resposta vira mensagem e o chat continua, sem
  traceback. Download: `.part` é removido em erro/Ctrl-C; subpasta do repo preservada no destino.
- `install.sh`: `apt-get update` antes do install (máquina nova); `BASH_SOURCE` vazio no
  `curl | bash` não é mais confundido com "dentro do clone" (o `git pull` volta a rodar);
  chamadas ao `fzbots` por caminho absoluto (não dependem do PATH).
- `tests/test_config.py` não grava mais em `archived/` do repo (arquivo temporário arquiva ao lado).

## [0.6.0] — 2026-09-08

### Added
- **`install.sh`** (`curl | bash` ou `sudo ./install.sh`): apt (python3-yaml, python3-textual,
  python3-rich, curl, jq, git), clone/uso do repo, `/usr/local/bin/fzbots`, completion bash,
  checagem do `llama_bin` (chama `scripts/build-llama.sh` só se faltar), aviso de cloudflared,
  `fzbots check` no fim. Idempotente.
- `completions/fzbots.bash`: completa subcomandos, nomes de bot (lê o yml) e opções.
- `fzbots chat <bot> [-m]`: conversa com stream pelo `/v1/chat/completions`, mostra tok/s;
  trata `reasoning_content` (Qwen3 pensa antes de responder; `--raciocinio` mostra).
  `fzbots embed <bot> "texto"` para bots `--embedding`.
- `fzbots modelos`: lista os `.gguf` de `modelos_dir` com tamanho, quant, arquitetura, ctx
  máximo, **VRAM estimada lendo o cabeçalho GGUF** (pesos + KV cache por camadas/heads_kv/ctx)
  e quais bots usam cada um.
- `fzbots flags <modelo> --ctx N`: sugere `extra_args` (`-ngl 99` se cabe na VRAM livre real,
  senão `--fit on`; `-fa on`; `-ctk/-ctv q8_0` para ctx ≥ 8192; `--embedding -b -ub` para
  embedders; `--jinja` para chat) com a explicação de cada escolha.
- `fzbots baixar <repo> [arquivo]`: download do Hugging Face para `modelos_dir/<repo>/`, com
  progresso; sem `arquivo`, lista os `.gguf` do repo para escolher.
- **TUI `fzbots tui`** (Textual 2.1, apt): abas Painel (estado por unit + `/health`, VRAM
  estimada/real, site, descrição, consumidores, processos llama-server de fora do yml, rodapé
  com GPU e trava), Modelos (`.gguf` do disco com VRAM estimada e quem usa; `n` novo bot com
  formulário e flags sugeridas → grava no yml preservando comentários, `apply`, `start`;
  `d` download do Hugging Face), Chat (stream, `(pensando…)`, tok/s), Logs (`journalctl -f`),
  Endpoints (URLs local/rede/túnel + `curl` pronto). Teclas `s p r l c a k e n d F5 q`.
  Nenhuma lógica na TUI: só chama `fzbots/*.py`. ADR 0008.
- `fzbots/config.py::adicionar_bot`: acrescenta um bot ao `bots.yml` por append textual
  (comentários preservados), arquiva antes, valida depois e restaura se inválido.
- Testes: `tests/test_config.py` (14 casos de validação/render, `unittest` stdlib) e
  `tests/tui_headless.py` (TUI via `run_test`: painel, check, modelos, chat, logs; `--novo-bot`
  cria, sobe e confere um bot real). Screenshots SVG em `docs/screenshots/`.
- Docs: `docs/pt/instalar.md`, `docs/en/install.md`, `docs/pt/tui.md`, `docs/en/tui.md`;
  README com a linha de instalação, a TUI e o screenshot.

## [0.5.0] — 2026-09-08

### Changed (decisões do dono — AGENTS.md regra zero)
- **Todo bot escuta em `0.0.0.0`** (local + rede). ADR 0001 substituída pela ADR 0006;
  regra 7 antiga (loopback) removida do AGENTS.md. Ingress continua em `127.0.0.1:<porta>`.
- **openclaw e lms são consumidores externos, sem adapters** (ADR 0007). O bot `deephat`
  (DeepHat-V1-7B, 8084, `--fit on`) entrou no `bots.yml` como bot interno e substituiu a
  unit `openclaw-deephat.service` (arquivada). O adapter de prefixos (8083) deixa de ser
  usado: o openclaw aponta direto para `http://127.0.0.1:8082/v1/`.
- `bots.yml` v2: chaves de topo `llama_bin`, `modelos_dir`, `gpu_vram_gb`, `lan_ip`; por bot
  `descricao`, `site`, `consumidores` (informativo). Chave desconhecida = erro.

### Added
- **Pacote `fzbots/`** (Python, stdlib + PyYAML) — único leitor do `bots.yml`:
  `config.py` (load/validate/render), `systemd.py` (apply/check/prune/start/stop/restart/logs/undo),
  `gpu.py` (VRAM real por unit via nvidia-smi + cgroup), `api.py`, `cli.py`. Entrypoint `bin/fzbots`.
- `fzbots check`: drift em 5 eixos (arquivos, órfãs, processo × unit, cloudflared, GPU real).
  Exit 1 se houver FALHA. `fzbots status` inclui a seção Drift.
- **Trava de VRAM real**: `apply` e `start` somam a estimativa do yml com o que processos
  de fora (lms, etc.) ocupam de verdade na GPU. Processo externo na porta de um bot do yml
  conta como "a substituir", não como terceiro.
- `fzbots apply --prune` remove units órfãs (arquiva antes; recusa se houver `Requires=` externo).
  `fzbots apply --restart` sobe o que é novo e **reinicia** o que mudou (antes o script mandava
  `enable --now`, que não reinicia unit já no ar).
- Escrita atômica (tmp + rename) e validação de tudo (yml, modelos, VRAM, config do
  cloudflared) **antes** de gravar qualquer arquivo.
- `fzbots stop` e `fzbots undo` recusam derrubar unit com dependente externo (`--forca` para insistir).
- `fzbots url`, `fzbots list`, `fzbots render`, `fzbots vram`.
- Docs: `docs/en/architecture.md`, `docs/en/adr.md`; `docs/pt/arquitetura.md` com módulos e eixos do check.

### Fixed (achados do architecture-review de 2026-09-08)
- `undo.sh` ecoava o token da API Cloudflare (`set -x` + `cat`), subia uma segunda cópia do
  DeepHat em `0.0.0.0:8081` sem VRAM e apagava túnel/Access com o cert da conta inteira.
  Agora é atalho para `fzbots undo`, que só remove o que o projeto gerou.
- `tunnel: false` (grafia errada) ou `tunel: "false"` viravam bot público — agora é erro.
- `systemd/fzbots-llama.service` (cópia manual obsoleta, contradizia a ADR 0003) removido.
- `docs/en/add-bot.md` e README mandavam editar unit e ingress na mão — reescritos.
- `test-tunnel.sh`: 403 com credencial fora da rede autorizada é AVISO (política funcionando),
  não FALHA; bot de embedding não recebe teste de chat; lê os bots via `fzbots list --publicos`.
- `status.sh` não tratava `nvidia-smi` falhando como FALHA — `fzbots status` trata.
- CHANGELOG reordenado (mais novo em cima).

### Removed
- `systemd/` (unit copiada à mão). `scripts/aplicar.sh`, `status.sh`, `undo.sh` viraram atalhos de 1 linha.

## [0.4.1] — 2026-08-18

### Fixed
- O EmbeddingGemma agora sobe com batch lógico e físico de 2048 tokens. Isso
  impede o llama-server de reduzir ambos para 512 e recusar chunks de memória
  entre 513 e 2048 tokens.
- O paralelismo permanece automático; nesta versão do llama.cpp, fixá-lo em
  quatro dividiria a janela de 2048 em slots de 512 tokens.

## [0.4.0] — 2026-08-16

### Added
- Campo `tunel: false` no `bots.yml`: bot interno (unit + loopback) sem ingress
  no Cloudflare. ADR 0005.
- Bot `embed` (porta 8082): EmbeddingGemma 300M QAT Q8_0, só embeddings,
  fora do túnel. Modelo em `/root/.lmstudio/models/embeddinggemma-300m/`.
- `aplicar.sh` / `test-tunnel.sh` respeitam o campo. Docs PT/EN atualizados.

## [0.3.0] — 2026-08-12

### Added
- **llama.cpp oficialmente no escopo**: doc dedicada (`docs/pt/llama-cpp.md` +
  EN), regra 10 no AGENTS.md, checagem do binário no `status.sh`.
- **Documentação de arquitetura**: `docs/pt/arquitetura.md` (C4 níveis 1-2 em
  mermaid, fluxo, invariantes) + 4 ADRs em `docs/adr/` (loopback, dupla camada,
  bots.yml, 1 processo por bot).
- README (PT/EN): diagrama mermaid na página inicial, links pra arquitetura/ADRs.
- Mapa vivo do fluxo publicado como página (URL fixa) e `scripts/mapa-mudou.sh`:
  refresh inteligente por sha256 (só republica se bots.yml ou arquitetura.md mudaram).

### Changed
- **Scripts multibot**: `status.sh`, `test-tunnel.sh` e `undo.sh` passaram a ler o
  bots.yml — zero ID na unha — e a retornar código de erro (servem de sonda).
- AGENTS.md: regras 8 (conformidade total de docs), 9 (bots.yml fonte da verdade).
- Documentação limpa de nomes de modelos privados e de máquinas fora deste
  servidor — apta pra apresentação de produto. Originais em archived/.

## [0.2.0] — 2026-08-11

### Added
- **bots.yml**: fonte única da verdade dos bots (nome, hostname, porta, modelo,
  VRAM) — recomendação do architecture-review.
- **scripts/aplicar.sh**: gera units systemd + ingress do cloudflared a partir
  do bots.yml, confere soma de VRAM e porta duplicada, arquiva versões antigas.
- Fluxo de bot novo reduzido a: bloco no bots.yml + aplicar.sh (docs atualizadas).

## [0.1.1] — 2026-08-11

### Changed
- Bot público (fzbots) agora usa **Qwen3-1.7B Q4_K_M** (unsloth, 1,1 GB) —
  modelo dedicado pra tarefa, ~1,6 GB de VRAM.
- Modelo de uso privado removido do túnel (voltou ao walker02 em 2026-08-31 como
  modelo do openclaw; desde 0.5.0 é o bot interno `deephat`).
- Unit antiga salva em `archived/`.

### Validado (2026-08-11)
- Teste positivo pelo túnel confirmado por cliente na rede 138.186.228.0/24
  (IP .18) com Service Token: /health, /v1/models e chat OK.

## [0.1.0] — 2026-08-11

### Added
- Projeto criado: walker02 como backend de bots multi-modelo.
- `fzbots-llama.service` (systemd): llama-server (binário existente, sem
  recompilar) servindo em `127.0.0.1:8081` — antes era processo solto em 0.0.0.0.
- cloudflared 2026.7.3 instalado; túnel nomeado `fzbots` → `fzbots.rogerluft.com.br`,
  serviço systemd, cert reaproveitado do walker (só leitura, túneis existentes intocados).
- Cloudflare Access: app `fzbots` com política Service Token + require rede
  `138.186.228.0/24`. Testado: sem credencial → 403; credencial com IP fora → 403.
- Credenciais em `/root/walker02-tunnel-access.txt` (root:root 600).
- Scripts: `status.sh`, `test-tunnel.sh`, `undo.sh`. Docs PT/EN.

### Changed
- Acesso LAN direto `192.168.0.23:8081` desativado (API só em loopback).

### Security
- Nenhuma porta aberta no roteador; serviços fora do bots.yml ficam fora do túnel.
