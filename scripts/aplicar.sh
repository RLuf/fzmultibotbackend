#!/bin/bash
# Compatibilidade: aplica o bots.yml. Hoje é só um atalho para `fzbots apply`.
exec "$(dirname "$(readlink -f "$0")")/../bin/fzbots" apply "$@"
