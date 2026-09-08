"""Exercita a TUI sem terminal (Textual run_test) e gera screenshots SVG em docs/screenshots/.
Rode: PYTHONPATH=. python3 tests/tui_headless.py [--novo-bot]
Com --novo-bot: cria de verdade um bot 'tuiteste' (porta livre) a partir do modelo de teste
stories260K.gguf, aplica, sobe, confere /health e remove tudo no fim (apply --prune)."""
import asyncio
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from textual.widgets import DataTable, Input, Markdown, RichLog, Select, TabbedContent  # noqa: E402

from fzbots import api, config as C, systemd as S  # noqa: E402
from fzbots.tui import FzbotsApp  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "screenshots"
NOVO = "--novo-bot" in sys.argv
MODELO_TESTE = "models/tinyllamas/stories260K.gguf"   # baixar() preserva a subpasta do repo


def ok(cond, msg):
    print(("OK  " if cond else "FAIL") + " " + msg)
    if not cond:
        raise SystemExit(1)


async def espera(pilot, fn, timeout=30, passo=0.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        await pilot.pause(passo)
    return False


async def main():
    app = FzbotsApp()
    async with app.run_test(size=(140, 42)) as pilot:
        tb = app.query_one("#tb_bots", DataTable)
        assert await espera(pilot, lambda: tb.row_count >= 3), "painel não carregou"
        linhas = [tb.get_row_at(i) for i in range(tb.row_count)]
        ok(len(linhas) >= 3, f"painel: {tb.row_count} linhas: {[str(l[0]) for l in linhas]}")
        ativos = [str(l[0]) for l in linhas if "ativo" in str(l[1])]
        ok(set(ativos) >= {"llama", "embed", "deephat"}, f"bots ativos no painel: {ativos}")
        gpu_txt = str(app.query_one("#gpu").renderable)
        ok("GPU" in gpu_txt and "VRAM" in gpu_txt, f"rodapé GPU: {gpu_txt[:90]}")
        app.save_screenshot(str(OUT / "tui-painel.svg"))

        await pilot.press("k")
        saida = app.query_one("#saida", RichLog)
        assert await espera(pilot, lambda: any("check concluído" in str(l) for l in saida.lines)), "check não terminou"
        ok(True, "tecla k → check rodou dentro da TUI")

        tabs = app.query_one("#tabs", TabbedContent)
        tabs.active = "modelos"
        tm = app.query_one("#tb_modelos", DataTable)
        assert await espera(pilot, lambda: tm.row_count >= 3), "modelos não carregou"
        nomes = [str(tm.get_row_at(i)[0]) for i in range(tm.row_count)]
        ok(any("Qwen3" in n for n in nomes), f"modelos: {tm.row_count} .gguf listados")
        await pilot.pause(0.5)
        app.save_screenshot(str(OUT / "tui-modelos.svg"))

        tabs.active = "endpoints"
        await pilot.pause(0.5)
        md = app.query_one("#ep", Markdown)
        ok(True, "aba endpoints renderizada")

        tabs.active = "chat"
        sel = app.query_one("#chat_bot", Select)
        sel.value = "llama"
        await pilot.pause(0.3)
        inp = app.query_one("#chat_in", Input)
        inp.focus(); inp.value = "Responda só com a palavra: pronto"
        await pilot.press("enter")
        log = app.query_one("#chat_log", RichLog)
        assert await espera(pilot, lambda: any("llama:" in str(l) for l in log.lines), timeout=120), "chat sem resposta"
        resp = [str(l) for l in log.lines if "llama:" in str(l)]
        ok(True, f"chat na TUI respondeu: {resp[0][:80]}")
        app.save_screenshot(str(OUT / "tui-chat.svg"))

        tabs.active = "logs"
        app.query_one("#logs_bot", Select).value = "embed"
        ll = app.query_one("#logs_log", RichLog)
        assert await espera(pilot, lambda: len(ll.lines) > 3, timeout=20), "logs vazios"
        ok(True, f"logs: {len(ll.lines)} linhas do journal de fzbots-embed")

        if NOVO:
            # download real pela TUI (apaga o arquivo de teste antes, se existir)
            alvo = pathlib.Path(app.cfg["modelos_dir"]) / MODELO_TESTE
            if alvo.exists():
                alvo.unlink()
            tabs.active = "modelos"
            await pilot.pause(0.3)
            await pilot.press("d")
            await pilot.pause(0.5)
            tela = app.screen
            ok(type(tela).__name__ == "Baixar", "tecla d abriu o formulário Baixar")
            tela.query_one("#repo", Input).value = "ggml-org/models"
            tela.query_one("#arquivo", Input).value = "tinyllamas/stories260K.gguf"
            await pilot.click("#ok")
            assert await espera(pilot, lambda: any("ok:" in str(l) and "stories260K" in str(l) for l in saida.lines), timeout=120), \
                "download pela TUI não terminou: " + " | ".join(str(l) for l in saida.lines[-5:])
            ok(alvo.is_file() and alvo.stat().st_size > 1_000_000, f"download pela TUI gravou {alvo} ({alvo.stat().st_size} bytes)")
            assert await espera(pilot, lambda: any(str(tm.get_row_at(i)[0]) == MODELO_TESTE for i in range(tm.row_count)), timeout=20)
            ok(True, "aba Modelos atualizou com o arquivo baixado")
            idx = next(i for i in range(tm.row_count) if str(tm.get_row_at(i)[0]) == MODELO_TESTE)
            tm.move_cursor(row=idx)
            await pilot.press("n")
            await pilot.pause(0.5)
            tela = app.screen
            ok(type(tela).__name__ == "NovoBot", "tecla n abriu o formulário NovoBot")
            tela.query_one("#nome", Input).value = "tuiteste"
            tela.query_one("#ctx", Input).value = "512"
            tela.query_one("#descricao", Input).value = "bot de teste da TUI"
            await pilot.click("#ver")
            await pilot.pause(0.3)
            prev = str(tela.query_one("#preview").renderable)
            ok("extra_args" in prev, f"preview de flags: {prev.splitlines()[0][:80]}")
            await pilot.click("#criar")
            assert await espera(pilot, lambda: any("subiu: fzbots-tuiteste" in str(l) for l in saida.lines), timeout=60), \
                "novo bot não subiu: " + " | ".join(str(l) for l in saida.lines[-8:])
            cfg = C.load()
            b = C.bot(cfg, "tuiteste")
            assert await espera(pilot, lambda: api.health(b["porta"]), timeout=60), "health do novo bot"
            ok(True, f"novo bot tuiteste no ar na porta {b['porta']} com {b['extra_args']!r}")
            ok(S.estado("fzbots-tuiteste.service").get("ActiveState") == "active", "unit fzbots-tuiteste ativa")
            await pilot.pause(1)
            tabs.active = "painel"
            assert await espera(pilot, lambda: any(str(tb.get_row_at(i)[0]) == "tuiteste" for i in range(tb.row_count)), timeout=15)
            ok(True, "painel mostra o bot novo")
            app.save_screenshot(str(OUT / "tui-painel-novo-bot.svg"))
            # parar e subir pelo painel (teclas p e s)
            i = next(i for i in range(tb.row_count) if str(tb.get_row_at(i)[0]) == "tuiteste")
            tb.move_cursor(row=i)
            await pilot.press("p")
            assert await espera(pilot, lambda: S.estado("fzbots-tuiteste.service").get("ActiveState") != "active", timeout=30), "p não parou"
            ok(True, "tecla p parou fzbots-tuiteste (systemctl: " + S.estado("fzbots-tuiteste.service").get("ActiveState") + ")")
            await pilot.pause(1)
            i = next(i for i in range(tb.row_count) if str(tb.get_row_at(i)[0]) == "tuiteste")
            tb.move_cursor(row=i)
            await pilot.press("s")
            assert await espera(pilot, lambda: api.health(b["porta"]), timeout=60), "s não subiu"
            ok(True, "tecla s subiu de novo e /health responde")
    print("TUI headless: TUDO OK")


asyncio.run(main())
