# Consumidores externos (openclaw, LM Studio, qualquer cliente da LAN)

Este projeto **não configura** o openclaw nem o LM Studio. Eles são clientes dos endpoints do
llama-server, como qualquer outro (ADR 0007). Esta página só diz onde apontar.

## Onde está cada bot

`fzbots url` imprime, por bot, as URLs `local` (`http://127.0.0.1:<porta>`), `rede`
(`http://<ip-da-lan>:<porta>`) e, se público, `tunel` (`https://<hostname>`). Os caminhos são os
do llama-server (compatíveis com OpenAI):

| Bot | Porta | API | Alias do modelo |
|---|---|---|---|
| `embed` | 8082 | `POST /v1/embeddings` | `embeddinggemma-300m` |
| `deephat` | 8084 | `POST /v1/chat/completions`, `/completion` | `DeepHat-V1-7B` |
| `llama` | 8081 | `POST /v1/chat/completions` | (o arquivo do modelo) |

Porta e alias são contrato com quem consome: mudar um deles no `bots.yml` exige avisar o
consumidor (o campo `consumidores:` do bot é o lembrete; `fzbots stop`/`undo` recusam derrubar
sem `--forca`).

## openclaw — o que aponta para cá (estado em 2026-09-08)

- `models.providers.deephat.baseUrl = http://127.0.0.1:8084/v1` → bot `deephat`.
- `agents.defaults.memorySearch.remote.baseUrl = http://127.0.0.1:8082/v1/` → bot `embed`,
  direto (trocado em 2026-09-08; backup em `/root/.openclaw/openclaw.json.bak.fzbots-*`). O adapter
  de prefixos `openclaw-embeddinggemma-adapter` (8083) foi desativado e arquivado pela decisão
  "sem adapters"; o llama-server aceita o campo `input_type` que o openclaw envia (é ignorado). Risco aceito: sem os prefixos `task: search result | query:` /
  `title: none | text:` do EmbeddingGemma, a busca de memória pode perder um pouco de qualidade.
  A edição do `openclaw.json` é do openclaw (fora deste repo): faça backup antes.

Passos que foram executados no lado do openclaw (fora deste repo), para referência:

```bash
cp -p /root/.openclaw/openclaw.json /root/.openclaw/openclaw.json.bak.$(date +%Y%m%d_%H%M%S)
jq '.agents.defaults.memorySearch.remote.baseUrl = "http://127.0.0.1:8082/v1/"' \
  /root/.openclaw/openclaw.json > /root/.openclaw/openclaw.json.novo \
  && mv /root/.openclaw/openclaw.json.novo /root/.openclaw/openclaw.json
systemctl disable --now openclaw-embeddinggemma-adapter.service   # unit com Requires=fzbots-embed
XDG_RUNTIME_DIR=/run/user/0 systemctl --user restart openclaw-gateway.service
```

## LM Studio (`lms`)

Roda como daemon próprio no walker02 e carrega modelos por conta (local e remoto). Compartilha
o diretório `/root/.lmstudio/models` (o `modelos_dir` do `bots.yml`): um `.gguf` baixado por um
aparece para o outro. A VRAM que o lms ocupar entra na trava real do `fzbots apply`/`start` como
"terceiros" — se ele carregar um modelo grande, um bot pode não subir até liberar.

## Qualquer outro cliente

```bash
curl http://<ip>:8081/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"oi"}]}'
curl http://<ip>:8082/v1/embeddings -H 'Content-Type: application/json' -d '{"input":["texto"]}'
```

Pela internet (só bots com hostname): mesmos caminhos em `https://<hostname>` com os headers
`CF-Access-Client-Id` e `CF-Access-Client-Secret`, vindo da rede autorizada.
