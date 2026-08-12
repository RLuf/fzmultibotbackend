# Adicionar um bot novo

Cada bot é independente: 1 hostname + 1 llama-server + 1 modelo (escolha livre).

## Passos (exemplo: bot "loja" com qwen na porta 8082)

1. **bots.yml** (fonte da verdade, na raiz do repo) — adicione o bloco:
   ```yaml
   - nome: loja
     hostname: loja.rogerluft.com.br
     porta: 8082
     modelo: /caminho/do/modelo.gguf
     vram_estimada: 1.6
     extra_args: "-ngl 99 -c 4096 -fa on"
   ```
2. **Aplicar** — `scripts/aplicar.sh` (gera unit + ingress, confere a VRAM,
   guarda os antigos em archived/). Depois:
   `systemctl enable --now fzbots-loja && systemctl restart cloudflared`
   e (só na 1ª vez) `cloudflared tunnel route dns fzbots loja.rogerluft.com.br`.
3. **Access** — crie app + Service Token próprios pro bot (mesmo formato do
   fzbots, via API com `/root/.cf-api-token`) — assim cada cliente tem sua
   credencial e dá pra revogar um sem derrubar os outros.
4. **Teste** — `curl -H "CF-Access-Client-Id: ..." -H "CF-Access-Client-Secret: ..." https://loja.rogerluft.com.br/health`
5. Atualize a tabela de bots no README e o CHANGELOG.

## Modelos disponíveis no disco

Ver tabela no README. Modelos maiores que a VRAM da GPU local podem usar GPU
remota via RPC do llama.cpp (recurso opcional, fora deste escopo).
