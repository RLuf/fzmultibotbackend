# Adicionar um bot novo

Cada bot é independente: 1 porta + 1 llama-server + 1 modelo (escolha livre). Bot público
tem também 1 hostname no túnel. Todo bot escuta em `0.0.0.0` (local e rede).

## Pelo yml (funciona hoje)

1. **bots.yml** (fonte da verdade, na raiz do repo) — adicione o bloco:
   ```yaml
   - nome: loja                 # ^[a-z0-9][a-z0-9-]*$ → unit fzbots-loja.service
     descricao: bot da loja X   # livre
     site: loja-x.com.br        # informativo: a quem atende
     hostname: loja.rogerluft.com.br   # só bot público
     porta: 8085
     modelo: /root/.lmstudio/models/<pasta>/<arquivo>.gguf
     vram_estimada: 1.6         # GB — a trava soma com o que já está na GPU
     extra_args: "-ngl 99 -c 4096 -fa on"
   ```
   Chaves válidas: `nome porta modelo vram_estimada` (obrigatórias), `descricao site hostname
   extra_args tunel consumidores`. Chave desconhecida = erro, nada aplicado.
2. **Aplicar** — `fzbots apply --restart` (ou `scripts/aplicar.sh --restart`): valida o yml,
   confere a VRAM real, arquiva o que sobrescreve em `archived/`, grava unit + ingress,
   sobe/reinicia só o que mudou. Sem `--restart`, ele imprime os `systemctl` a rodar.
3. **DNS** (só na 1ª vez do hostname): `cloudflared tunnel route dns fzbots loja.rogerluft.com.br`.
4. **Access** — crie app + Service Token próprios pro bot (mesmo formato do fzbots, via API
   com `/root/.cf-api-token`) — assim cada cliente tem sua credencial e dá pra revogar um
   sem derrubar os outros.
5. **Teste** — `fzbots status` (local) e `scripts/test-tunnel.sh` (pelo túnel; de fora da rede
   autorizada o teste com credencial dá 403 e isso é AVISO, não falha).
6. Atualize a tabela de bots no README e o CHANGELOG.

## Bot só local (sem túnel)

Serviço interno — embedder, modelo do openclaw, teste — entra com `tunel: false` e **sem**
hostname. Ganha unit e porta, não entra no ingress. Continua acessível na LAN
(`http://<ip>:<porta>`). Exemplo real (`bots.yml`):

```yaml
  - nome: embed
    descricao: embeddings (memória do openclaw)
    porta: 8082
    modelo: /root/.lmstudio/models/embeddinggemma-300m/embeddinggemma-300m-qat-Q8_0.gguf
    vram_estimada: 0.5
    extra_args: "-ngl 99 -c 2048 -b 2048 -ub 2048 --embedding --alias embeddinggemma-300m"
    tunel: false
    consumidores: [openclaw]   # informativo: fzbots stop/undo avisam antes de derrubar
```

## Remover ou renomear um bot

Tire (ou renomeie) o bloco no yml e rode `fzbots apply`. A unit antiga vira **órfã**:
`fzbots check` acusa; `fzbots apply --prune` remove (arquivando antes), **recusando** se
alguma unit de fora depender dela (`Requires=`). Avise os consumidores listados em
`consumidores` antes — o openclaw, por exemplo, aponta para porta e alias fixos.

## Modelos no disco

`modelos_dir` do `bots.yml` (`/root/.lmstudio/models`, compartilhado com o LM Studio).
Modelos maiores que a VRAM da GPU: use `--fit on` no lugar de `-ngl 99` (o llama-server
divide entre GPU e CPU), como faz o bot `deephat`.
