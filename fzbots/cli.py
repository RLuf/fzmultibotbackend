"""CLI: fzbots <comando>. A TUI (fzbots tui) usa as mesmas funções."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from . import config as C
from . import gpu
from . import systemd as S


def _cfg() -> dict:
    return C.load()


def cmd_apply(a) -> int:
    return S.apply(_cfg(), prune=a.prune, restart=a.restart)


def cmd_check(a) -> int:
    cfg = _cfg()
    achados = S.check(cfg)
    pior = 0
    for nivel, msg in achados:
        print(f"{nivel}: {msg}" if nivel != "ok" else msg)
        pior = max(pior, {"ok": 0, "AVISO": 0, "FALHA": 1}[nivel])
    avisos = sum(1 for n, _ in achados if n == "AVISO")
    if not any(n == "FALHA" for n, _ in achados):
        print("em sincronia: bots.yml == host" + (f" (com {avisos} aviso(s) acima)" if avisos else ""))
    return pior


def cmd_render(a) -> int:
    cfg = _cfg()
    if a.alvo == "ingress":
        import yaml
        print(yaml.safe_dump({"ingress": C.render_ingress(cfg)}, sort_keys=False), end="")
    else:
        print(C.render_unit(cfg, C.bot(cfg, a.alvo)), end="")
    return 0


def cmd_list(a) -> int:
    cfg = _cfg()
    for b in cfg["bots"]:
        if a.publicos and not C.publico(b):
            continue
        campos = [b["nome"], str(b["porta"]), b.get("hostname") or "-",
                  "publico" if C.publico(b) else "privado",
                  "embedding" if C.embedding(b) else "chat"]
        print("\t".join(campos))
    return 0


def cmd_status(a) -> int:
    cfg = _cfg()
    falhas = 0
    import pathlib
    print("== llama.cpp (dependência vital) ==")
    lb = pathlib.Path(cfg["llama_bin"])
    if lb.is_file() and lb.stat().st_mode & 0o111:
        v = S.sh(str(lb), "--version", check=False)
        print(f"binário ok: {lb} ({(v.stdout or v.stderr).strip().splitlines()[0] if (v.stdout or v.stderr).strip() else '?'})")
    else:
        print(f"FALHA: binário não encontrado: {lb}"); falhas += 1

    publicos = [b for b in cfg["bots"] if C.publico(b)]
    print("== Túnel ==")
    if publicos:
        if S.estado("cloudflared").get("ActiveState") == "active":
            print("cloudflared: active")
        else:
            print("FALHA: cloudflared parado"); falhas += 1
    else:
        print("sem bot público — túnel não é exigido")

    print("== Bots (bots.yml) ==")
    from . import api
    for b in cfg["bots"]:
        u = C.unit_name(b)
        ok = True
        e = S.estado(u)
        if e.get("ActiveState") != "active":
            print(f"FALHA: {u} {e.get('ActiveState', '?')}"); ok = False
        if not api.health(b["porta"]):
            print(f"FALHA: {b['nome']} não responde em 127.0.0.1:{b['porta']}/health"); ok = False
        if ok:
            u_ = C.urls(cfg, b)
            print(f"ok: {b['nome']} (porta {b['porta']}, {u_.get('tunel', 'interno')})")
        else:
            falhas += 1

    print("== Drift (bots.yml vs host) ==")
    for nivel, msg in S.check(cfg):
        if nivel == "FALHA":
            print(f"FALHA: {msg.splitlines()[0]}"); falhas += 1
        elif nivel == "AVISO":
            print(f"AVISO: {msg}")
    print("== GPU ==")
    g = gpu.info()
    if g is None:
        print("FALHA: nvidia-smi não respondeu"); falhas += 1
    else:
        print(f"{g['nome']}: {g['usado_mib']} / {g['total_mib']} MiB")
        for unit, mib in sorted(gpu.uso_por_unit().items(), key=lambda x: -x[1]):
            print(f"  {mib:>6} MiB  {unit}")
    print("TUDO OK" if falhas == 0 else f"{falhas} FALHA(S)")
    return 1 if falhas else 0


def cmd_start(a) -> int:
    S.start(_cfg(), a.bot); return 0


def cmd_stop(a) -> int:
    S.stop(_cfg(), a.bot, forca=a.forca); return 0


def cmd_restart(a) -> int:
    S.restart(_cfg(), a.bot); return 0


def cmd_logs(a) -> int:
    return S.logs(_cfg(), a.bot, linhas=a.linhas, seguir=a.seguir)


def cmd_url(a) -> int:
    cfg = _cfg()
    bots = [C.bot(cfg, a.bot)] if a.bot else cfg["bots"]
    for b in bots:
        for k, v in C.urls(cfg, b).items():
            print(f"{b['nome']}\t{k}\t{v}")
    return 0


def cmd_undo(a) -> int:
    # não depende do bots.yml: undo tem que funcionar mesmo com o yml quebrado
    return S.undo(None, forca=a.forca)


def cmd_tui(a) -> int:
    try:
        from . import tui
    except ImportError as e:
        print(f"ERRO: a TUI precisa do Textual (apt install python3-textual): {e}", file=sys.stderr); return 2
    return tui.main()


def cmd_vram(a) -> int:
    cfg = _cfg()
    ok, msg = gpu.trava(cfg)
    print(msg)
    return 0 if ok else 1


def cmd_modelos(a) -> int:
    from . import modelos as M
    cfg = _cfg()
    g = gpu.info()
    livre = (g["total_mib"] - g["usado_mib"]) / 1024 if g else 0.0
    lista = M.listar(cfg, ctx=a.ctx)
    if not lista:
        print(f"nenhum .gguf em {cfg['modelos_dir']}"); return 1
    print(f"modelos em {cfg['modelos_dir']} (VRAM livre agora: {livre:.2f} GB; estimativa p/ ctx {a.ctx}, modelo inteiro na GPU)")
    print(f"{'tamanho':>8} {'quant':7} {'arq':16} {'est.VRAM':>9} {'cabe':5} {'bots':14} arquivo")
    for m in lista:
        cabe = "sim" if m.vram_est <= livre else "não"
        print(f"{m.tamanho_gb:7.2f}G {m.quant:7} {m.arquitetura[:16]:16} {m.vram_est:8.2f}G {cabe:5} {','.join(m.bots) or '-':14} {m.nome}")
    return 0


def cmd_flags(a) -> int:
    from . import modelos as M
    import pathlib
    cfg = _cfg()
    p = pathlib.Path(a.modelo)
    if not p.is_absolute():
        p = pathlib.Path(cfg["modelos_dir"]) / p
    if not p.is_file():
        print(f"ERRO: modelo não existe: {p}"); return 2
    g = gpu.info()
    livre = (g["total_mib"] - g["usado_mib"]) / 1024 if g else 0.0
    try:
        flags, exp = M.perfil_flags(p, a.ctx, livre, embedding=(True if a.embedding else None), alias=a.alias)
    except ValueError as e:
        print(f"ERRO: {e}"); return 2
    print(flags); print(f"# {exp}")
    return 0


def cmd_baixar(a) -> int:
    from . import modelos as M
    import urllib.error
    cfg = _cfg()
    arquivo = a.arquivo
    try:
        if not arquivo:
            ggufs = M.hf_listar(a.repo)
            if not ggufs:
                print(f"nenhum .gguf em {a.repo}"); return 1
            if len(ggufs) > 1:
                print(f"{a.repo} tem {len(ggufs)} arquivos .gguf — escolha um:")
                for f in ggufs:
                    print(f"  fzbots baixar {a.repo} {f}")
                return 1
            arquivo = ggufs[0]
        def prog(feito, total):
            if total:
                print(f"\r  {feito/1024**2:8.1f} / {total/1024**2:.1f} MiB ({100*feito/total:5.1f}%)", end="", flush=True)
            else:
                print(f"\r  {feito/1024**2:8.1f} MiB", end="", flush=True)
        print(f"baixando {a.repo}/{arquivo} → {cfg['modelos_dir']}")
        dest = M.baixar(cfg, a.repo, arquivo, progresso=prog)
        print(f"\nok: {dest} ({dest.stat().st_size/1024**2:.1f} MiB)")
        return 0
    except urllib.error.HTTPError as e:
        print(f"\nERRO: Hugging Face devolveu {e.code} para {a.repo}/{arquivo or ''}"); return 1
    except urllib.error.URLError as e:
        print(f"\nERRO de rede: {e.reason}"); return 1


def cmd_chat(a) -> int:
    from . import api
    import time
    import urllib.error
    cfg = _cfg()
    b = C.bot(cfg, a.bot)
    if C.embedding(b):
        print(f"{a.bot} é bot de embedding — use: fzbots embed {a.bot} \"texto\""); return 2
    if not api.health(b["porta"]):
        print(f"ERRO: {a.bot} não responde em 127.0.0.1:{b['porta']} (fzbots start {a.bot}?)"); return 1
    historico: list[dict] = []
    if a.sistema:
        historico.append({"role": "system", "content": a.sistema})

    def rodada(texto: str) -> None:
        historico.append({"role": "user", "content": texto})
        t0, n, partes, pensou = time.time(), 0, [], False
        try:
            for tipo, pedaco in api.chat_stream(b["porta"], historico, max_tokens=a.max_tokens):
                n += 1
                if tipo == "raciocinio":
                    if a.raciocinio:
                        print(f"\033[2m{pedaco}\033[0m", end="", flush=True)
                    elif not pensou:
                        print("\033[2m(pensando…)\033[0m ", end="", flush=True)
                    pensou = True
                    continue
                print(pedaco, end="", flush=True); partes.append(pedaco)
        except (urllib.error.URLError, OSError, ValueError) as e:   # rede caiu / servidor reiniciou
            historico.pop()
            print(f"\n\033[31merro de rede com {a.bot}: {e}\033[0m")
            return
        dt = time.time() - t0
        print(f"\n\033[2m[{n} tokens em {dt:.1f}s ≈ {n/dt if dt else 0:.1f} tok/s]\033[0m")
        historico.append({"role": "assistant", "content": "".join(partes)})

    if a.mensagem:
        rodada(a.mensagem); return 0
    print(f"chat com {a.bot} ({', '.join(api.modelos(b['porta'])) or b['modelo']}). Ctrl-D ou /sair para sair.")
    while True:
        try:
            texto = input("você> ").strip()
        except EOFError:
            print(); return 0
        if texto in ("/sair", "/quit", "/q"):
            return 0
        if texto:
            rodada(texto)


def cmd_embed(a) -> int:
    from . import api
    cfg = _cfg()
    b = C.bot(cfg, a.bot)
    if not api.health(b["porta"]):
        print(f"ERRO: {a.bot} não responde em 127.0.0.1:{b['porta']}"); return 1
    try:
        vs = api.embeddings(b["porta"], [a.texto])
    except (OSError, ValueError) as e:
        print(f"ERRO de rede com {a.bot}: {e}"); return 1
    if not vs:
        print("ERRO: sem vetor na resposta"); return 1
    v = vs[0]
    print(f"dimensão {len(v)}; primeiros 5: {[round(x, 4) for x in v[:5]]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fzbots", description="Backend de bots: bots.yml → llama-server por bot.")
    p.add_argument("--version", action="version", version=f"fzbots {__version__}")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("apply", help="aplica o bots.yml (units + ingress)")
    s.add_argument("--prune", action="store_true", help="remove units órfãs (sem dependente externo)")
    s.add_argument("--restart", action="store_true", help="sobe/reinicia o que mudou")
    s.set_defaults(f=cmd_apply)

    s = sp.add_parser("check", help="drift: bots.yml vs host (exit 1 se houver FALHA)")
    s.set_defaults(f=cmd_check)

    s = sp.add_parser("render", help="mostra a unit de um bot ou o ingress")
    s.add_argument("alvo", help="nome do bot ou 'ingress'")
    s.set_defaults(f=cmd_render)

    s = sp.add_parser("list", help="bots do yml em TSV: nome porta hostname publico|privado chat|embedding")
    s.add_argument("--publicos", action="store_true")
    s.set_defaults(f=cmd_list)

    s = sp.add_parser("status", help="saúde de tudo (exit != 0 se algo falhou)")
    s.set_defaults(f=cmd_status)

    for nome, fn, ajuda in (("start", cmd_start, "sobe um bot (confere VRAM livre)"),
                            ("restart", cmd_restart, "reinicia um bot")):
        s = sp.add_parser(nome, help=ajuda)
        s.add_argument("bot")
        s.set_defaults(f=fn)
    s = sp.add_parser("stop", help="para um bot (recusa se tiver dependente, salvo --forca)")
    s.add_argument("bot")
    s.add_argument("--forca", action="store_true")
    s.set_defaults(f=cmd_stop)

    s = sp.add_parser("logs", help="journal do bot")
    s.add_argument("bot")
    s.add_argument("-n", "--linhas", type=int, default=50)
    s.add_argument("-f", "--seguir", action="store_true")
    s.set_defaults(f=cmd_logs)

    s = sp.add_parser("url", help="URLs de cada bot (local, rede, túnel)")
    s.add_argument("bot", nargs="?")
    s.set_defaults(f=cmd_url)

    s = sp.add_parser("vram", help="trava de VRAM: yml + terceiros vs GPU")
    s.set_defaults(f=cmd_vram)


    s = sp.add_parser("modelos", help="lista os .gguf de modelos_dir com VRAM estimada e quem usa")
    s.add_argument("--ctx", type=int, default=4096)
    s.set_defaults(f=cmd_modelos)

    s = sp.add_parser("flags", help="sugere extra_args otimizados para um modelo")
    s.add_argument("modelo", help="caminho (absoluto ou relativo a modelos_dir)")
    s.add_argument("--ctx", type=int, default=4096)
    s.add_argument("--embedding", action="store_true")
    s.add_argument("--alias")
    s.set_defaults(f=cmd_flags)

    s = sp.add_parser("baixar", help="baixa um .gguf do Hugging Face para modelos_dir")
    s.add_argument("repo", help="ex.: unsloth/Qwen3-1.7B-GGUF")
    s.add_argument("arquivo", nargs="?", help="nome do .gguf (se omitido e houver só um, usa ele)")
    s.set_defaults(f=cmd_baixar)

    s = sp.add_parser("chat", help="conversa com um bot (stream); -m para uma pergunta só")
    s.add_argument("bot")
    s.add_argument("-m", "--mensagem")
    s.add_argument("-s", "--sistema", help="prompt de sistema")
    s.add_argument("--max-tokens", type=int, default=1024)
    s.add_argument("--raciocinio", action="store_true", help="mostra o raciocínio (reasoning_content) em cinza")
    s.set_defaults(f=cmd_chat)

    s = sp.add_parser("embed", help="gera o embedding de um texto num bot --embedding")
    s.add_argument("bot")
    s.add_argument("texto")
    s.set_defaults(f=cmd_embed)

    s = sp.add_parser("tui", help="interface interativa (Textual)")
    s.set_defaults(f=cmd_tui)

    s = sp.add_parser("undo", help="remove units fzbots-* e zera o ingress (não toca túnel/Access)")
    s.add_argument("--forca", action="store_true")
    s.set_defaults(f=cmd_undo)
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    try:
        return int(a.f(a) or 0)
    except C.ConfigError as e:
        print(f"ERRO no bots.yml: {e}", file=sys.stderr)
        return 2
    except S.OperError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as e:      # último recurso: mensagem limpa em vez de traceback
        print(f"ERRO ({type(e).__name__}): {e}", file=sys.stderr)
        return 1
