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
8. **Documentação bilíngue**: README e docs em PT e EN, sempre atualizados
   junto com qualquer mudança (CHANGELOG incluso).

## Arquitetura (resumo)
Um túnel (`fzbots`), vários bots: cada bot = um hostname no ingress do
`/etc/cloudflared/config.yml` + um llama-server próprio numa porta 127.0.0.1
com o modelo escolhido. Ver `docs/plans/2026-08-11-tunnel-design.md`.
