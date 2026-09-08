# ADR 0007 — openclaw e lms são consumidores externos; sem adapters

Data: 2026-09-08 · Status: aceita

**Decisão**: o openclaw (agente que roda no walker02) e o LM Studio (`lms`, que carrega
modelos local e remotamente junto do papaimach) **não fazem parte deste projeto**.
Eles consomem os endpoints do llama-server como qualquer cliente da LAN. Nenhuma
camada intermediária (adapter, proxy, prefixador) é criada ou mantida aqui: o
llama.cpp é exposto direto.

**Porquê** (palavras do dono): "o openclaw não deve ser disponibilizado pelo projeto;
é apenas um consumidor local/rede como qualquer outro"; "não use adapters para expor
os modelos locais, use o llama.cpp diretamente sem camadas intermediárias".

**Consequência**:
- O bot `embed` (EmbeddingGemma, 8082) e o bot `deephat` (DeepHat-7B, 8084) vivem no
  `bots.yml` como bots internos (`tunel: false`) com `consumidores: [openclaw]`
  (campo informativo: `fzbots stop` e `fzbots undo` avisam antes de derrubar).
- A unit `openclaw-deephat.service` foi substituída por `fzbots-deephat.service`
  (mesma porta 8084, mesmo alias `DeepHat-V1-7B`); o openclaw não percebeu.
- O adapter de prefixos `openclaw-embeddinggemma-adapter` (8083) deixa de ser usado:
  o openclaw aponta `memorySearch.remote.baseUrl` para `http://127.0.0.1:8082/v1/`.
  Risco aceito: o adapter acrescentava os prefixos `task: search result | query:` e
  `title: none | text:` do EmbeddingGemma; sem ele a busca de memória do openclaw
  pode perder um pouco de qualidade. Essa edição é do openclaw, fora deste repo.
- A VRAM que esses consumidores usam por conta própria (ex.: um modelo carregado pelo
  lms) entra na trava real do `fzbots apply`/`start` como "terceiros".
