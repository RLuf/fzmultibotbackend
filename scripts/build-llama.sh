#!/bin/bash
# build-llama.sh — compila o llama.cpp (llama-server, llama-cli, ggml-rpc-server)
# detectando sozinho GPU/CUDA/compilador/CPU e explicando cada escolha.
#
# Uso:
#   build-llama.sh [--prefix DIR] [--ref TAG_OU_COMMIT] [--detectar] [--jobs N] [--cpu-only]
#
#   --prefix DIR   onde clonar e compilar (padrão /opt/llama.cpp).
#                  Fonte em $PREFIX, build em $PREFIX/build, binários em $PREFIX/build/bin.
#   --ref REF      tag, branch ou commit do github.com/ggml-org/llama.cpp.
#                  Padrão: última release publicada no GitHub (API); se a API falhar,
#                  a maior tag de `git ls-remote --tags`; se nada responder, `master`.
#   --detectar     só imprime a tabela de detecção e o comando cmake que usaria.
#                  Não instala, não baixa, não compila. Sai 0. Seguro em qualquer máquina.
#   --jobs N       paralelismo do build (padrão: nproc; limitado a 2 se RAM < 4 GB).
#   --cpu-only     ignora a GPU e faz build só de CPU (-DGGML_CUDA=OFF).
#
# O que ele decide sozinho (e imprime o porquê):
#   GPU NVIDIA  → nvidia-smi dá o compute capability (7.5 → CMAKE_CUDA_ARCHITECTURES=75).
#   nvcc        → PATH ou /usr/local/cuda/bin/nvcc. GPU sem nvcc = aviso + build CPU
#                 (o script NÃO instala o CUDA toolkit sozinho).
#   compilador  → gcc ≥ 14 com g++-13/g++-12 disponível → CMAKE_CUDA_HOST_COMPILER=g++-13
#                 (nvcc 12.x não aceita gcc 14/15 como compilador host).
#   CPU         → flags de /proc/cpuinfo (avx2, avx512f, fma, f16c) → GGML_NATIVE=ON.
#   RAM         → < 4 GB limita jobs a 2.
#   sempre      → -DGGML_RPC=ON -DCMAKE_BUILD_TYPE=Release
#
# Dependências (git, cmake, g++, libcurl4-openssl-dev) são instaladas via apt-get se
# faltarem — isso só acontece fora do --detectar e exige root. O script nunca usa sudo:
# rode como root ou como usuário com permissão de escrita no --prefix.
#
# Sai 0 só se $PREFIX/build/bin/llama-server existir e responder a --version.

set -euo pipefail

# ---------- argumentos ----------
PREFIX=/opt/llama.cpp
REF=""
DETECTAR=0
JOBS=""
CPU_ONLY=0

uso() { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)   PREFIX="${2:?--prefix precisa de um diretório}"; shift 2 ;;
    --ref)      REF="${2:?--ref precisa de uma tag/commit}"; shift 2 ;;
    --detectar) DETECTAR=1; shift ;;
    --jobs)     JOBS="${2:?--jobs precisa de um número}"; shift 2 ;;
    --cpu-only) CPU_ONLY=1; shift ;;
    -h|--help)  uso; exit 0 ;;
    *) echo "ERRO: argumento desconhecido: $1" >&2; uso >&2; exit 2 ;;
  esac
done

msg()   { echo "==> $*"; }
aviso() { echo "AVISO: $*" >&2; }
erro()  { echo "ERRO: $*" >&2; exit 1; }

MOTIVOS=()   # acumula "o que escolhi e por quê" para o resumo final
motivo() { MOTIVOS+=("$*"); }

# ---------- detecção: GPU ----------
GPU_NOME="nenhuma"
GPU_CAP=""       # ex.: 7.5
CUDA_ARCH=""     # ex.: 75 (ou 75;86 com várias GPUs)
if command -v nvidia-smi >/dev/null 2>&1; then
  saida=$(nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader 2>/dev/null || true)
  if [ -n "$saida" ]; then
    GPU_NOME=$(echo "$saida" | head -1 | cut -d, -f1 | sed 's/^ *//;s/ *$//')
    GPU_CAP=$(echo "$saida" | head -1 | cut -d, -f2 | tr -d ' ')
    CUDA_ARCH=$(echo "$saida" | cut -d, -f2 | tr -d ' .' | sort -u | paste -sd';')
    n=$(echo "$saida" | wc -l)
    [ "$n" -gt 1 ] && GPU_NOME="$GPU_NOME (+$((n-1)) outra(s))"
  fi
fi

# ---------- detecção: nvcc ----------
NVCC=""
NVCC_VER=""
if command -v nvcc >/dev/null 2>&1; then
  NVCC=$(command -v nvcc)
elif [ -x /usr/local/cuda/bin/nvcc ]; then
  NVCC=/usr/local/cuda/bin/nvcc
fi
if [ -n "$NVCC" ]; then
  NVCC_VER=$("$NVCC" --version 2>/dev/null | sed -n 's/.*release \([0-9]*\.[0-9]*\).*/\1/p' | head -1)
fi

# ---------- decisão: CUDA ou CPU ----------
MODO="CPU"
if [ "$CPU_ONLY" = 1 ]; then
  motivo "build CPU: --cpu-only pedido na linha de comando (GPU ignorada)"
elif [ -z "$CUDA_ARCH" ]; then
  motivo "build CPU: nenhuma GPU NVIDIA detectada (nvidia-smi ausente ou sem GPU)"
elif [ -z "$NVCC" ]; then
  aviso "GPU $GPU_NOME encontrada, mas sem nvcc (CUDA toolkit). Instale o toolkit para build CUDA; seguindo com build CPU."
  motivo "build CPU: GPU $GPU_NOME existe mas falta o nvcc (CUDA toolkit não instalado; o script não o instala sozinho)"
else
  MODO="CUDA"
  motivo "build CUDA: GPU $GPU_NOME com compute capability $GPU_CAP → CMAKE_CUDA_ARCHITECTURES=$CUDA_ARCH"
  motivo "nvcc $NVCC_VER em $NVCC"
fi

# ---------- detecção: compilador host para o nvcc ----------
GCC_VER=$(gcc -dumpversion 2>/dev/null | cut -d. -f1 || true)
GCC_VER=${GCC_VER:-0}
HOST_CXX=""
HOST_CXX_MOTIVO="padrão do cmake"
if [ "$GCC_VER" -ge 14 ] 2>/dev/null; then
  for c in g++-13 g++-12; do
    if command -v "$c" >/dev/null 2>&1; then HOST_CXX="$c"; break; fi
  done
  if [ -n "$HOST_CXX" ]; then
    HOST_CXX_MOTIVO="gcc $GCC_VER é recusado pelo nvcc 12.x; usar $HOST_CXX como host compiler"
  else
    HOST_CXX_MOTIVO="gcc $GCC_VER sem g++-13/g++-12 disponível; nvcc 12.x pode recusar (instale g++-13 se falhar)"
  fi
fi
if [ "$MODO" = CUDA ]; then
  motivo "compilador host do nvcc: ${HOST_CXX:-padrão} — $HOST_CXX_MOTIVO"
  [ "$GCC_VER" -ge 14 ] && [ -z "$HOST_CXX" ] && aviso "$HOST_CXX_MOTIVO"
fi

# ---------- detecção: CPU / RAM ----------
CPU_FLAGS=$(grep -m1 '^flags' /proc/cpuinfo 2>/dev/null | tr ' ' '\n' | grep -xE 'avx2|avx512f|fma|f16c' | sort | paste -sd' ' || true)
CPU_FLAGS=${CPU_FLAGS:-nenhuma das esperadas}
NPROC=$(nproc 2>/dev/null || echo 1)
[ "$NPROC" -ge 1 ] || NPROC=1
RAM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)

if [ -z "$JOBS" ]; then
  JOBS=$NPROC
  motivo "jobs=$JOBS: nproc"
else
  motivo "jobs=$JOBS: --jobs pedido na linha de comando"
fi
case "$JOBS" in ''|*[!0-9]*) erro "--jobs precisa ser um inteiro ≥ 1 (recebi '$JOBS')";; esac
[ "$JOBS" -ge 1 ] || JOBS=1
if [ "$RAM_GB" -lt 4 ] && [ "$JOBS" -gt 2 ]; then
  aviso "RAM de ${RAM_GB} GB (< 4 GB): limitando jobs de $JOBS para 2 para não estourar memória."
  JOBS=2
  motivo "jobs limitado a 2: RAM ${RAM_GB} GB < 4 GB"
fi
motivo "GGML_NATIVE=ON: build para esta CPU (flags: $CPU_FLAGS)"
motivo "GGML_RPC=ON e CMAKE_BUILD_TYPE=Release: sempre (GPU remota opcional + otimização)"

# ---------- ref: última release ----------
REF_ORIGEM=""
if [ -z "$REF" ]; then
  REF=$(curl -fsS --max-time 15 https://api.github.com/repos/ggml-org/llama.cpp/releases/latest 2>/dev/null \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)
  if [ -n "$REF" ]; then
    REF_ORIGEM="última release (API do GitHub)"
  else
    REF=$(timeout 30 git ls-remote --tags https://github.com/ggml-org/llama.cpp 2>/dev/null \
          | sed -n 's|.*refs/tags/\([^^]*\)$|\1|p' | sort -V | tail -1 || true)
    if [ -n "$REF" ]; then
      REF_ORIGEM="maior tag via git ls-remote (API do GitHub falhou)"
    else
      REF=master
      REF_ORIGEM="fallback master (GitHub inacessível)"
    fi
  fi
else
  REF_ORIGEM="--ref pedido na linha de comando"
fi
REF_TIPO=tag
if echo "$REF" | grep -qE '^[0-9a-f]{7,40}$'; then REF_TIPO=commit; fi
motivo "ref=$REF ($REF_TIPO): $REF_ORIGEM"

# ---------- comando cmake ----------
BUILD="$PREFIX/build"
CMAKE_ARGS=(-S "$PREFIX" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DGGML_RPC=ON -DGGML_NATIVE=ON)
if [ "$MODO" = CUDA ]; then
  CMAKE_ARGS+=(-DGGML_CUDA=ON "-DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCH")
  [ -n "$HOST_CXX" ] && CMAKE_ARGS+=("-DCMAKE_CUDA_HOST_COMPILER=$HOST_CXX")
  case "$NVCC" in /usr/bin/nvcc) ;; *) CMAKE_ARGS+=("-DCMAKE_CUDA_COMPILER=$NVCC") ;; esac
else
  CMAKE_ARGS+=(-DGGML_CUDA=OFF)
fi
ALVOS=(llama-server llama-cli ggml-rpc-server)

# ---------- tabela de detecção ----------
linha() { printf '  %-22s %s\n' "$1" "$2"; }
echo "Detecção (build-llama.sh):"
linha "GPU NVIDIA"      "${GPU_NOME}${GPU_CAP:+ (compute cap $GPU_CAP → arch $CUDA_ARCH)}"
if [ -n "$NVCC" ]; then linha "nvcc" "$NVCC (release $NVCC_VER)"; else linha "nvcc" "não encontrado"; fi
if [ "$GCC_VER" != 0 ]; then linha "gcc" "$GCC_VER${HOST_CXX:+ → host compiler do nvcc: $HOST_CXX}"; else linha "gcc" "não encontrado (será instalado com build-essential)"; fi
linha "CPU flags"       "$CPU_FLAGS"
linha "CPUs / jobs"     "$NPROC / $JOBS"
linha "RAM"             "${RAM_GB} GB"
linha "modo"            "$MODO"
linha "ref"             "$REF ($REF_TIPO; $REF_ORIGEM)"
linha "prefix"          "$PREFIX"
linha "alvos"           "${ALVOS[*]}"
echo
if [ "$DETECTAR" = 1 ]; then echo "Comando cmake que seria usado:"; else echo "Comando cmake que será usado:"; fi
echo "  cmake ${CMAKE_ARGS[*]}"
echo "  cmake --build $BUILD -j$JOBS --target ${ALVOS[*]}"
echo
echo "Motivos:"
for m in "${MOTIVOS[@]}"; do echo "  - $m"; done

if [ "$DETECTAR" = 1 ]; then
  echo
  echo "--detectar: nada foi instalado, baixado ou compilado."
  exit 0
fi

# ---------- permissões ----------
EU_ROOT=0; [ "$(id -u)" = 0 ] && EU_ROOT=1
if [ -e "$PREFIX" ]; then
  [ -w "$PREFIX" ] || erro "sem permissão de escrita em $PREFIX (rode como root ou ajuste o dono do diretório; o script não usa sudo)"
else
  mkdir -p "$PREFIX" 2>/dev/null || erro "não consigo criar $PREFIX (rode como root ou use --prefix num diretório gravável; o script não usa sudo)"
fi

# ---------- dependências ----------
FALTAM=()
command -v git   >/dev/null 2>&1 || FALTAM+=(git)
command -v cmake >/dev/null 2>&1 || FALTAM+=(cmake)
command -v g++   >/dev/null 2>&1 || FALTAM+=(build-essential)
command -v curl  >/dev/null 2>&1 || FALTAM+=(curl)
if command -v dpkg-query >/dev/null 2>&1; then
  dpkg-query -W -f='${Status}' libcurl4-openssl-dev 2>/dev/null | grep -q 'install ok installed' || FALTAM+=(libcurl4-openssl-dev)
elif [ ! -e /usr/include/curl/curl.h ] && [ ! -e /usr/include/x86_64-linux-gnu/curl/curl.h ]; then
  FALTAM+=(libcurl4-openssl-dev)
fi
if [ ${#FALTAM[@]} -gt 0 ]; then
  msg "faltam dependências: ${FALTAM[*]} — instalando via apt-get"
  [ "$EU_ROOT" = 1 ] || erro "preciso ser root para instalar ${FALTAM[*]} (o script não usa sudo)"
  command -v apt-get >/dev/null 2>&1 || erro "apt-get não encontrado; instale manualmente: ${FALTAM[*]}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends "${FALTAM[@]}"
  motivo "instalei via apt-get: ${FALTAM[*]}"
else
  msg "dependências de build já presentes (git, cmake, g++, libcurl4-openssl-dev)"
fi

# ---------- clone / checkout (idempotente) ----------
URL=https://github.com/ggml-org/llama.cpp
if [ -d "$PREFIX/.git" ]; then
  msg "$PREFIX já é um clone — atualizando para $REF"
  git -C "$PREFIX" remote set-url origin "$URL"
  if [ "$REF_TIPO" = tag ]; then
    git -C "$PREFIX" fetch --depth 1 origin "refs/tags/$REF:refs/tags/$REF" 2>/dev/null \
      || git -C "$PREFIX" fetch --depth 1 origin "$REF"
    git -C "$PREFIX" checkout -q --detach "$REF" 2>/dev/null \
      || git -C "$PREFIX" checkout -q --detach FETCH_HEAD
  else
    git -C "$PREFIX" fetch --depth 1 origin "$REF" 2>/dev/null || git -C "$PREFIX" fetch --unshallow origin 2>/dev/null || git -C "$PREFIX" fetch origin
    git -C "$PREFIX" checkout -q --detach "$REF"
  fi
elif [ -n "$(ls -A "$PREFIX" 2>/dev/null)" ]; then
  erro "$PREFIX existe, não está vazio e não é um clone git — escolha outro --prefix ou limpe o diretório"
else
  if [ "$REF_TIPO" = tag ]; then
    msg "clonando $URL ($REF, depth 1) em $PREFIX"
    git clone --depth 1 --branch "$REF" "$URL" "$PREFIX"
  else
    msg "clonando $URL em $PREFIX e fazendo checkout do commit $REF"
    git init -q "$PREFIX"
    git -C "$PREFIX" remote add origin "$URL"
    if ! git -C "$PREFIX" fetch --depth 1 origin "$REF" 2>/dev/null; then
      aviso "fetch raso do commit falhou; baixando histórico completo"
      git -C "$PREFIX" fetch origin
    fi
    git -C "$PREFIX" checkout -q --detach "$REF"
  fi
fi
COMMIT=$(git -C "$PREFIX" rev-parse --short HEAD)
msg "fonte em $PREFIX no commit $COMMIT"

# ---------- build ----------
msg "configurando: cmake ${CMAKE_ARGS[*]}"
cmake "${CMAKE_ARGS[@]}"
msg "compilando (-j$JOBS): ${ALVOS[*]}"
cmake --build "$BUILD" -j"$JOBS" --target "${ALVOS[@]}"

# ---------- verificação ----------
BIN="$BUILD/bin/llama-server"
[ -x "$BIN" ] || erro "build terminou mas $BIN não existe"
echo
msg "versão do binário:"
"$BIN" --version 2>&1 || erro "$BIN não respondeu a --version"
for a in "${ALVOS[@]}"; do
  [ -x "$BUILD/bin/$a" ] && linha "$a" "$BUILD/bin/$a" || aviso "alvo $a não gerou binário em $BUILD/bin"
done

echo
echo "Resumo — o que escolhi e por quê:"
for m in "${MOTIVOS[@]}"; do echo "  - $m"; done
echo "  - commit compilado: $COMMIT"
echo "  - binários: $BUILD/bin"
echo
msg "pronto: $BIN"
