# Adicionar um bot novo

Cada bot é independente: 1 hostname + 1 llama-server + 1 modelo (escolha livre).

## Passos (exemplo: bot "loja" com qwen na porta 8082)

1. **Serviço do modelo** — copie `/etc/systemd/system/fzbots-llama.service` para
   `fzbots-loja.service`, troque `-m <caminho-do-gguf>` e `--port 8082`
   (mantenha `--host 127.0.0.1`). Cuide da VRAM: a 2060 tem 6 GB no total.
   `systemctl daemon-reload && systemctl enable --now fzbots-loja`
2. **Ingress** — em `/etc/cloudflared/config.yml`, adicione ANTES do 404:
   ```yaml
   - hostname: loja.rogerluft.com.br
     service: http://127.0.0.1:8082
   ```
   Depois: `cloudflared tunnel route dns fzbots loja.rogerluft.com.br`
   e `systemctl restart cloudflared`.
3. **Access** — crie app + Service Token próprios pro bot (mesmo formato do
   fzbots, via API com `/root/.cf-api-token`) — assim cada cliente tem sua
   credencial e dá pra revogar um sem derrubar os outros.
4. **Teste** — `curl -H "CF-Access-Client-Id: ..." -H "CF-Access-Client-Secret: ..." https://loja.rogerluft.com.br/health`
5. Atualize a tabela de bots no README e o CHANGELOG.

## Modelos disponíveis no disco

Ver tabela no README. Modelos grandes (King 11 GB) precisam da GPU remota
(hermano via RPC — ver projeto pangeia, `docs/pt/cluster-llamacpp-rpc.md`).
