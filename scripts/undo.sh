#!/bin/bash
# Compatibilidade: desfaz SÓ o que o projeto gerou (units fzbots-* e ingress).
# Não apaga túnel, DNS nem Access; não sobe nada no lugar. Ver: fzbots undo --help
exec "$(dirname "$(readlink -f "$0")")/../bin/fzbots" undo "$@"
