# AGENTS.md — regras do projeto fzmultibotbackend

## REGRA ZERO
**A palavra atual do dono revoga qualquer diretriz contrária.** Diretriz que contradiga
uma decisão nova do dono é removida deste arquivo, dos ADRs e das docs na mesma mudança.

## REGRAS DE OURO
1. **archived/ antes de tudo**: antes de modificar ou apagar QUALQUER coisa,
   copie/mova o arquivo pra `archived/` (que está no .gitignore). Sem exceção.
   O `fzbots apply` faz isso sozinho para units e ingress.
2. **Nunca gravar segredos no repo nem mostrar na conversa**: tokens, certs e
   credenciais ficam em `/root/` com permissão 600. O repo só tem `.example`.
3. **Não tocar nos túneis de outros servidores da conta.** Este projeto só
   gerencia o túnel `fzbots`. `fzbots undo` não apaga túnel, DNS nem Access.
4. **Não recompilar o llama.cpp** do walker02 sem pedido explícito — usar o binário
   apontado por `llama_bin` no `bots.yml`. Em máquina nova, `install.sh` chama
   `scripts/build-llama.sh` (que nunca toca no build existente).
5. **Não mexer no DNS local** do walker02 (resolv.conf estático do dono).
6. **Executar comandos à risca**: sem extras, sem palpites sobre a rede do dono.
7. **Todo bot escuta em `0.0.0.0`** (local e rede) — decisão do dono, ADR 0006.
   Só bot com `hostname` entra no túnel Cloudflare (com Access na frente).
8. **Documentação bilíngue e em conformidade**: toda modificação DEVE
   criar/revisar/atualizar `.gitignore`, `AGENTS.md`, `CHANGELOG.md`, `README.md`
   (página inicial, PT e EN, prints se conveniente), `install.sh`, `completions/`
   e TODA a documentação em `./docs/` — corrigindo o que existe e criando o que falta,
   **antes de começar a próxima modificação**.
9. **bots.yml é a fonte da verdade** e o pacote `fzbots/` é o único que o lê.
   Units systemd e ingress do cloudflared NÃO se editam na mão — edita-se o
   `bots.yml` e roda-se `fzbots apply` (ou pela TUI). Editar direto faz o repo mentir;
   `fzbots check` acusa o drift.
10. **llama.cpp é dependência vital do projeto**: binário em `llama_bin`
   (build próprio no walker02, CUDA+RPC, arch 75). Documentado em
   `docs/pt/llama-cpp.md`, verificado pelo `fzbots status`.
11. **openclaw e LM Studio (lms) são consumidores externos.** Nada deles entra neste
   repo. Eles usam os endpoints do llama-server direto, **sem adapters nem camadas
   intermediárias** (ADR 0007). A VRAM que eles usam é contabilizada pela trava real.
12. **DeepHat nunca atende bot de site.** O bot `deephat` existe só para o openclaw:
   `tunel: false`, sem hostname, nunca no ingress.
13. **Segurança não é o foco deste trabalho**: não trocar simplicidade, estabilidade ou
   funcionalidade por hardening. O que protege os bots públicos é o Cloudflare Access.
14. **Sem containers para os bots** (ADR 0004). LXD só serve para testar
   `scripts/build-llama.sh` em container descartável.
15. **Porta 8081 é do bot público `llama`.** O projeto Pangeia (cluster de GPU entre
   máquinas, `../pangeia`) é outro produto e não entra aqui; seu runbook usa a 8081 —
   não subir os dois ao mesmo tempo.

## Arquitetura (resumo)
`bots.yml` → `fzbots apply` → 1 unit systemd por bot (`fzbots-<nome>.service`,
llama-server em `0.0.0.0:<porta>`) + ingress do `/etc/cloudflared/config.yml` para
os bots com hostname. `fzbots check` compara yml × host (units, processos, ingress,
GPU real). `fzbots tui` é a interface do dono. Ver `docs/pt/arquitetura.md` e `docs/adr/`.
