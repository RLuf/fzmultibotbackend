#!/usr/bin/env bash
# =============================================================================
# fzmultibotbackend — instalador
#   curl -fsSL https://raw.githubusercontent.com/RLuf/fzmultibotbackend/master/install.sh | bash
#   ou, dentro de um clone:  sudo ./install.sh
#
# O que faz (idempotente):
#   1. apt: python3, python3-yaml, python3-textual, python3-rich, curl, jq, git
#   2. usa o clone atual (se rodar de dentro dele) ou clona em /opt/fzmultibotbackend
#   3. /usr/local/bin/fzbots + completions bash
#   4. se o llama-server do bots.yml não existir: scripts/build-llama.sh (--build pula a pergunta)
#   5. avisa se há bot com hostname e o cloudflared não está instalado
#   6. fzbots check
# O que NÃO faz: não recompila um llama.cpp que já existe; não instala cloudflared
# (precisa do cert da conta); não mexe em túnel, DNS ou Access.
# =============================================================================
set -euo pipefail

REPO_URL="${FZBOTS_REPO_URL:-https://github.com/RLuf/fzmultibotbackend.git}"
DEST="${FZBOTS_DIR:-/opt/fzmultibotbackend}"
BUILD_AUTO=0
for arg in "$@"; do
  case "$arg" in
    --build) BUILD_AUTO=1 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '\033[1;34m[fzbots]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "rode como root (sudo)."
command -v apt-get >/dev/null 2>&1 || die "este instalador usa apt (Ubuntu/Debian)."

# 1) dependências
log "instalando dependências (apt)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -q >/dev/null
apt-get install -y -q python3 python3-yaml python3-textual python3-rich curl jq git >/dev/null
python3 -c 'import yaml, textual, rich' || die "python3-yaml/python3-textual/python3-rich não importam."

# 2) onde fica o repo
# BASH_SOURCE só existe quando o script roda como ARQUIVO; via `curl | bash` fica vazio
AQUI=""
if [ -n "${BASH_SOURCE[0]:-}" ]; then
  AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
fi
if [ -n "$AQUI" ] && [ -f "$AQUI/bots.yml" ] && [ -f "$AQUI/bin/fzbots" ]; then
  DEST="$AQUI"
  log "usando o clone atual: $DEST"
elif [ -d "$DEST/.git" ]; then
  log "atualizando $DEST (git pull)..."
  git -C "$DEST" pull -q --ff-only || log "git pull falhou (alterações locais?) — seguindo com o que está"
else
  log "clonando $REPO_URL em $DEST..."
  git clone -q "$REPO_URL" "$DEST"
fi
chmod +x "$DEST/bin/fzbots" "$DEST"/scripts/*.sh 2>/dev/null || true

# 3) comando + completions
ln -sfn "$DEST/bin/fzbots" /usr/local/bin/fzbots
if [ -d /etc/bash_completion.d ]; then
  ln -sfn "$DEST/completions/fzbots.bash" /etc/bash_completion.d/fzbots
fi
log "comando: fzbots ($("$DEST/bin/fzbots" --version))"

# 4) llama-server
LLAMA_BIN="$(python3 -c "import yaml,sys; print(yaml.safe_load(open('$DEST/bots.yml')).get('llama_bin',''))")"
if [ -n "$LLAMA_BIN" ] && [ -x "$LLAMA_BIN" ]; then
  log "llama-server ok: $LLAMA_BIN ($("$LLAMA_BIN" --version 2>&1 | head -1))"
else
  log "llama-server NÃO encontrado em: ${LLAMA_BIN:-<vazio>}"
  RESP=n
  if [ "$BUILD_AUTO" = 1 ]; then RESP=s
  elif [ -t 0 ]; then read -r -p "Baixar e compilar o llama.cpp agora com scripts/build-llama.sh? [s/N] " RESP </dev/tty || true
  fi
  case "$RESP" in
    s|S|y|Y)
      "$DEST/scripts/build-llama.sh" --prefix /opt/llama.cpp
      NOVO=/opt/llama.cpp/build/bin/llama-server
      [ -x "$NOVO" ] || die "build terminou mas $NOVO não existe"
      cp -p "$DEST/bots.yml" "$DEST/archived/bots.yml.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
      sed -i "s#^llama_bin:.*#llama_bin: $NOVO#" "$DEST/bots.yml"
      log "bots.yml: llama_bin → $NOVO" ;;
    *) log "sem llama-server: rode depois  $DEST/scripts/build-llama.sh --prefix /opt/llama.cpp  e ajuste llama_bin no bots.yml" ;;
  esac
fi

# 5) cloudflared
if python3 -c "import yaml,sys; sys.exit(0 if any(b.get('hostname') and b.get('tunel',True) is not False for b in yaml.safe_load(open('$DEST/bots.yml'))['bots']) else 1)"; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    log "há bot com hostname mas o cloudflared não está instalado — veja docs/pt/instalar.md (túnel exige o cert da conta)"
  fi
fi

# 6) estado
log "conferindo (fzbots check)..."
"$DEST/bin/fzbots" check || true
log "pronto. Próximo passo: fzbots tui   (ou: fzbots status / fzbots apply --restart)"
