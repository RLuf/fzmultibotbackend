#!/bin/bash
# Compatibilidade: saúde de tudo. Hoje é só um atalho para `fzbots status`.
exec "$(dirname "$(readlink -f "$0")")/../bin/fzbots" status "$@"
