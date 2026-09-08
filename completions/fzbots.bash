# bash completion para fzbots — instalado por install.sh em /etc/bash_completion.d/fzbots
_fzbots() {
  local cur prev cmds bots
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  cmds="apply check status list render start stop restart logs url vram undo modelos flags baixar chat embed tui"
  if [ "$COMP_CWORD" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "$cmds --version --help" -- "$cur") ); return
  fi
  case "${COMP_WORDS[1]}" in
    start|stop|restart|logs|url|chat|embed|render)
      bots="$(fzbots list 2>/dev/null | cut -f1 | tr '\n' ' ')"
      [ "${COMP_WORDS[1]}" = render ] && bots="$bots ingress"
      case "$prev" in
        start|stop|restart|logs|url|chat|embed|render) COMPREPLY=( $(compgen -W "$bots" -- "$cur") ); return ;;
      esac
      case "${COMP_WORDS[1]}" in
        stop) COMPREPLY=( $(compgen -W "--forca" -- "$cur") ) ;;
        logs) COMPREPLY=( $(compgen -W "-n -f --linhas --seguir" -- "$cur") ) ;;
        chat) COMPREPLY=( $(compgen -W "-m -s --mensagem --sistema --max-tokens" -- "$cur") ) ;;
      esac ;;
    apply) COMPREPLY=( $(compgen -W "--prune --restart" -- "$cur") ) ;;
    undo)  COMPREPLY=( $(compgen -W "--forca" -- "$cur") ) ;;
    list)  COMPREPLY=( $(compgen -W "--publicos" -- "$cur") ) ;;
    modelos) COMPREPLY=( $(compgen -W "--ctx" -- "$cur") ) ;;
    flags) if [ "$prev" = flags ]; then COMPREPLY=( $(compgen -f -- "$cur") ); else COMPREPLY=( $(compgen -W "--ctx --embedding --alias" -- "$cur") ); fi ;;
  esac
}
complete -F _fzbots fzbots
