# AGENTS.md — regras do projeto fzmultibotbackend

## REGRAS DE OURO
1. **archived/ antes de tudo**: antes de modificar ou apagar QUALQUER coisa,
   copie/mova o arquivo pra `archived/` (que está no .gitignore). Sem exceção.
2. **Nunca gravar segredos no repo nem mostrar na conversa**: tokens, certs e
   credenciais ficam em `/root/` com permissão 600. O repo só tem `.example`.
3. **Não tocar nos túneis dos outros servidores** (walker: fzmonitor, drjose,
   petshop, 5galaxia, drandres). Este projeto só gerencia o túnel `fzbots`.
4. **Não recompilar o llama.cpp** sem pedido explícito — usar o binário de
   `/home/dev/null/llama.cpp/build/bin/`.
5. **Não mexer no DNS local** do walker02 (resolv.conf estático do dono).
6. **Executar comandos à risca**: sem extras, sem palpites sobre a rede do dono.
7. **API só em 127.0.0.1**: nenhum llama-server escuta em 0.0.0.0. A saída pro
   mundo é exclusivamente o Cloudflare Tunnel + Access.
8. **Documentação bilíngue e em conformidade**: toda modificação DEVE
   criar/revisar/atualizar os arquivos relacionados: `.gitignore`, `AGENTS.md`,
   `CHANGELOG.md`, `README.md` (página inicial, PT e EN, prints se conveniente)
   e TODA a documentação em `./docs/` — corrigindo o que existe e criando o
   que falta.
9. **bots.yml é a fonte da verdade**: units systemd e ingress do cloudflared
   NÃO se editam na mão — edita-se o `bots.yml` e roda-se `scripts/aplicar.sh`.
   Editar direto faz o repo mentir.
10. **llama.cpp é dependência vital do projeto**: binário em
   `/home/dev/null/llama.cpp/build/bin/` (build próprio, CUDA+RPC, arch 75).
   Está DENTRO do escopo: documentado em `docs/pt/llama-cpp.md`, verificado
   pelo `status.sh`. Não recompilar sem pedido explícito (regra 4).

## Arquitetura (resumo)
Um túnel (`fzbots`), vários bots: cada bot = um hostname no ingress do
`/etc/cloudflared/config.yml` + um llama-server próprio numa porta 127.0.0.1
com o modelo escolhido. Ver `docs/plans/2026-08-11-tunnel-design.md`.
