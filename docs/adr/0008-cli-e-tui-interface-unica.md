# ADR 0008 — `fzbots` (CLI + TUI) é a interface única de operação

Data: 2026-09-08 · Status: aceita

**Decisão**: toda operação dos bots passa pelo pacote `fzbots/`: a CLI (`fzbots apply|check|
status|start|stop|restart|logs|url|chat|embed|modelos|flags|baixar|undo`) e a TUI (`fzbots tui`),
que chama exatamente as mesmas funções. Os scripts antigos em `scripts/` viraram atalhos.
Instalação em uma linha (`install.sh`), completion bash e testes (`tests/`) acompanham.

**Porquê** (pedido do dono): "o software deve poder proporcionar ao dono interação com os modelos
carregados"; "uma TUI interagível e funcional para ver visualmente o que está rodando, o que pode
ser carregado, o que está associado a determinado site, listar, iniciar, parar e baixar modelos";
"facilmente instalado com install.sh e curl | bash"; "quanto mais simples para mim depois, melhor".
Um único leitor do `bots.yml` evita quatro scripts com quatro parsers e faz `check` e `apply`
concordarem sempre (mesmo `desired()`).

**Consequência**: o único comando a lembrar é `fzbots tui`. Lógica nova entra em `fzbots/*.py`,
nunca na TUI nem em shell. `AGENTS.md` regra 9: o pacote é o único que lê o yml.
