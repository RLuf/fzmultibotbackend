# Instalar

## Em uma linha (máquina nova, Ubuntu/Debian, como root)

```bash
curl -fsSL https://raw.githubusercontent.com/RLuf/fzmultibotbackend/master/install.sh | bash
```

Ou, dentro de um clone: `sudo ./install.sh`. Opção `--build`: compila o llama.cpp sem perguntar
se ele não existir.

## O que o install.sh faz (idempotente — pode rodar de novo)

1. `apt-get install` de `python3 python3-yaml python3-textual python3-rich curl jq git`.
2. Usa o clone atual (se rodar de dentro dele) ou clona em `/opt/fzmultibotbackend`
   (`FZBOTS_DIR` muda o destino). Se já existe, `git pull --ff-only`.
3. Cria `/usr/local/bin/fzbots` e o completion bash em `/etc/bash_completion.d/fzbots`.
4. Confere o `llama_bin` do `bots.yml`. Se não existir, pergunta (ou `--build`) e chama
   `scripts/build-llama.sh --prefix /opt/llama.cpp`, que baixa e compila o llama.cpp com as
   otimizações que ele mesmo detecta (GPU/CUDA, compilador, flags da CPU); depois grava o
   caminho novo em `llama_bin`. No walker02 o binário já existe → nada é compilado (regra 4).
5. Se há bot com `hostname` e o `cloudflared` não está instalado, avisa (o túnel precisa do
   cert da conta Cloudflare — passo manual, ver abaixo).
6. Roda `fzbots check` e mostra o próximo passo.

## Depois do install

```bash
fzbots tui                 # a interface do dono: ver, subir, parar, baixar, conversar
fzbots apply --restart     # aplica o bots.yml (units + ingress) e sobe/reinicia o que mudou
fzbots status              # saúde completa
```

## Túnel Cloudflare (só para bots públicos, uma vez por máquina)

1. Instale o `cloudflared` (pacote oficial) e copie o cert da conta para `/root/.cloudflared/cert.pem`.
2. `cloudflared tunnel create fzbots` → anote o UUID; `/etc/cloudflared/config.yml` com
   `tunnel:` e `credentials-file:` (ver `cloudflared/config.yml.example`). O `ingress:` é
   gerado pelo `fzbots apply`.
3. `systemctl enable --now cloudflared`.
4. Para cada hostname: `cloudflared tunnel route dns fzbots <hostname>` + app do Access com
   Service Token (ver `docs/pt/adicionar-bot.md`).

## Desinstalar o que o projeto gerou

`fzbots undo`: para e remove as units `fzbots-*` (cópias em `archived/`) e zera o ingress.
Não apaga túnel, DNS nem Access — isso fica no painel Cloudflare. Recusa se alguma unit de
fora depender de um bot (`--forca` para insistir).
