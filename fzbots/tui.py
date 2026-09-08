"""TUI do dono: fzbots tui (Textual). Toda ação chama as mesmas funções da CLI."""
from __future__ import annotations

import os
import pathlib
import subprocess
import time

from textual import work
from textual.css.query import NoMatches
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (Button, Checkbox, DataTable, Footer, Header, Input, Label,
                             Markdown, RichLog, Select, Static, TabbedContent, TabPane)

from . import api
from . import config as C
from . import gpu
from . import modelos as M
from . import systemd as S


class NovoBot(ModalScreen[dict | None]):
    """Formulário: novo bot a partir de um .gguf do disco."""

    DEFAULT_CSS = """
    NovoBot { align: center middle; }
    NovoBot > Vertical { width: 90; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    NovoBot Input { margin-bottom: 0; }
    NovoBot Horizontal { height: auto; }
    """

    def __init__(self, modelo: pathlib.Path, porta_sugerida: int, embedding: bool):
        super().__init__()
        self.modelo, self.porta_sugerida, self.embedding = modelo, porta_sugerida, embedding

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Novo bot com {self.modelo.name}")
            yield Input(placeholder="nome (a-z 0-9 -)", id="nome")
            yield Input(value=str(self.porta_sugerida), placeholder="porta", id="porta")
            yield Input(value="2048" if self.embedding else "4096", placeholder="contexto (tokens)", id="ctx")
            yield Input(placeholder="hostname público (vazio = só local/rede)", id="hostname")
            yield Input(placeholder="descrição", id="descricao")
            yield Input(placeholder="site / cliente que atende", id="site")
            yield Input(placeholder="alias do modelo na API (opcional)", id="alias")
            yield Checkbox("bot de embedding", value=self.embedding, id="emb")
            yield Static("", id="preview")
            with Horizontal():
                yield Button("Ver flags", id="ver")
                yield Button("Criar e aplicar", variant="primary", id="criar")
                yield Button("Cancelar", id="cancelar")

    def _dados(self) -> dict:
        g = gpu.info()
        livre = (g["total_mib"] - g["usado_mib"]) / 1024 if g else 0.0
        ctx = int(self.query_one("#ctx", Input).value or 4096)
        emb = self.query_one("#emb", Checkbox).value
        alias = self.query_one("#alias", Input).value.strip() or None
        flags, exp = M.perfil_flags(self.modelo, ctx, livre, embedding=emb, alias=alias)
        est, _ = M.estimar_vram(self.modelo, ctx, kv_bytes=1 if ctx >= 8192 else 2)
        host = self.query_one("#hostname", Input).value.strip()
        bloco = {"nome": self.query_one("#nome", Input).value.strip(),
                 "descricao": self.query_one("#descricao", Input).value.strip(),
                 "site": self.query_one("#site", Input).value.strip(),
                 "porta": int(self.query_one("#porta", Input).value or 0),
                 "modelo": str(self.modelo), "vram_estimada": round(est, 1), "extra_args": flags}
        if host:
            bloco["hostname"] = host
        else:
            bloco["tunel"] = False
        return {"bloco": bloco, "explica": exp}

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "cancelar":
            self.dismiss(None)
        elif ev.button.id in ("ver", "criar"):
            try:
                d = self._dados()
            except ValueError as e:      # alias com espaço, porta/ctx não numéricos
                self.query_one("#preview", Static).update(f"[red]{e}[/]"); return
            if ev.button.id == "ver":
                self.query_one("#preview", Static).update(f"extra_args: {d['bloco']['extra_args']}\n{d['explica']}")
            else:
                self.dismiss(d)


class Baixar(ModalScreen[dict | None]):
    DEFAULT_CSS = """
    Baixar { align: center middle; }
    Baixar > Vertical { width: 80; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    Baixar Horizontal { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Baixar .gguf do Hugging Face")
            yield Input(placeholder="repo, ex.: unsloth/Qwen3-1.7B-GGUF", id="repo")
            yield Input(placeholder="arquivo .gguf (vazio = listar os do repo)", id="arquivo")
            with Horizontal():
                yield Button("Baixar", variant="primary", id="ok")
                yield Button("Cancelar", id="cancelar")

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "ok":
            self.dismiss({"repo": self.query_one("#repo", Input).value.strip(),
                          "arquivo": self.query_one("#arquivo", Input).value.strip()})
        else:
            self.dismiss(None)


class FzbotsApp(App):
    TITLE = "fzbots"
    CSS = """
    #tb_bots, #tb_modelos { height: 1fr; }
    #gpu { height: auto; padding: 0 1; color: $text-muted; }
    #saida { height: 9; border-top: solid $accent; }
    #chat_log, #logs_log { height: 1fr; }
    #chat_atual { height: auto; max-height: 8; color: $text-muted; padding: 0 1; }
    Select { width: 40; }
    """
    BINDINGS = [
        ("q", "quit", "Sair"), ("f5", "atualizar", "Atualizar"),
        ("s", "start", "Subir"), ("p", "stop", "Parar"), ("r", "restart", "Reiniciar"),
        ("l", "logs", "Logs"), ("c", "chat", "Chat"), ("a", "apply", "Apply"), ("k", "check", "Check"),
        ("e", "editar", "Editar yml"), ("n", "novo_bot", "Novo bot"), ("d", "baixar", "Baixar"),
    ]

    def __init__(self):
        super().__init__()
        self.cfg = C.load()
        self._logs_proc: subprocess.Popen | None = None
        self._chat_hist: list[dict] = []
        self._repopulando = False

    # ------------------------------------------------------------ layout
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="painel", id="tabs"):
            with TabPane("Painel", id="painel"):
                yield DataTable(id="tb_bots", cursor_type="row", zebra_stripes=True)
                yield Static("", id="gpu")
            with TabPane("Modelos", id="modelos"):
                yield DataTable(id="tb_modelos", cursor_type="row", zebra_stripes=True)
            with TabPane("Chat", id="chat"):
                yield Select([], prompt="bot", id="chat_bot")
                yield RichLog(id="chat_log", wrap=True, markup=True)
                yield Static("", id="chat_atual")
                yield Input(placeholder="sua mensagem (Enter envia)", id="chat_in")
            with TabPane("Logs", id="logs"):
                yield Select([], prompt="bot", id="logs_bot")
                yield RichLog(id="logs_log", wrap=True, max_lines=2000)
            with TabPane("Endpoints", id="endpoints"):
                yield Markdown("", id="ep")
        yield RichLog(id="saida", wrap=True, markup=True, max_lines=500)
        yield Footer()

    def on_mount(self) -> None:
        tb = self.query_one("#tb_bots", DataTable)
        tb.add_columns("bot", "estado", "porta", "modelo", "VRAM est/real", "site", "descrição", "consumidores")
        tm = self.query_one("#tb_modelos", DataTable)
        tm.add_columns("arquivo", "tamanho", "quant", "arq", "ctx máx", "VRAM est", "cabe?", "bots")
        self.action_atualizar()
        self.set_interval(5, self.atualizar_painel)

    def saida(self, msg: str) -> None:
        try:
            self.query_one("#saida", RichLog).write(msg)
        except NoMatches:
            pass

    def _seguro(self, fn, *args) -> None:
        """call_from_thread que ignora o app já encerrado."""
        if not self.is_running:
            return
        try:
            self.call_from_thread(fn, *args)
        except RuntimeError:   # loop fechado
            pass

    # ------------------------------------------------------------ dados
    def action_atualizar(self) -> None:
        try:
            self.cfg = C.load()
        except C.ConfigError as e:
            self.saida(f"[red]bots.yml inválido:[/] {e}")
        self.atualizar_painel()
        self.atualizar_modelos()
        self.atualizar_selects()
        self.atualizar_endpoints()

    @work(thread=True, exclusive=True, group="painel")
    def atualizar_painel(self) -> None:
        cfg = self.cfg
        lista = gpu.procs()
        uso = gpu.uso_por_unit(lista)
        linhas = []
        for b in cfg["bots"]:
            u = C.unit_name(b)
            e = S.estado(u)
            vivo = api.health(b["porta"], timeout=1.5)
            st = e.get("ActiveState", "?")
            estado = ("[green]ativo[/]" if st == "active" and vivo else
                      "[yellow]subindo[/]" if st == "active" else
                      f"[red]{st}[/]" if e.get("LoadState") != "not-found" else "[red]sem unit[/]")
            real = uso.get(u)
            linhas.append((b["nome"], estado, str(b["porta"]), pathlib.Path(b["modelo"]).name,
                           f"{float(b['vram_estimada']):.1f} / {real/1024 if real else 0:.1f} GB",
                           b.get("site", ""), b.get("descricao", ""), ",".join(b.get("consumidores") or [])))
        for p in lista:
            if not p.nosso and p.cmd and "llama-server" in p.cmd[0]:
                linhas.append((f"(externo) {p.unit or p.pid}", "[magenta]fora do yml[/]", p.arg("--port") or "?",
                               pathlib.Path(p.arg("-m") or "?").name, f"– / {p.mib/1024:.1f} GB", "", "", ""))
        g = gpu.info()
        ok, msg = gpu.trava(cfg)
        gtxt = (f"GPU {g['nome']}: {g['usado_mib']} / {g['total_mib']} MiB · " if g else "GPU: nvidia-smi não respondeu · ") \
               + ("[green]" if ok else "[red]") + msg + "[/]"
        self._seguro(self._pinta_painel, linhas, gtxt)

    def _pinta_painel(self, linhas, gtxt) -> None:
        try:
            tb = self.query_one("#tb_bots", DataTable)
        except NoMatches:      # app fechando
            return
        cur = tb.cursor_row
        tb.clear()
        for ln in linhas:
            tb.add_row(*ln, key=ln[0])
        if 0 <= cur < tb.row_count:
            tb.move_cursor(row=cur)
        self.query_one("#gpu", Static).update(gtxt)

    @work(thread=True, exclusive=True, group="modelos")
    def atualizar_modelos(self) -> None:
        g = gpu.info()
        livre = (g["total_mib"] - g["usado_mib"]) / 1024 if g else 0.0
        linhas = []
        for m in M.listar(self.cfg):
            linhas.append((m.nome, f"{m.tamanho_gb:.2f} GB", m.quant, m.arquitetura, str(m.ctx_max or "?"),
                           f"{m.vram_est:.2f} GB", "[green]sim[/]" if m.vram_est <= livre else "[red]não[/]",
                           ",".join(m.bots)))
        self._seguro(self._pinta_modelos, linhas)

    def _pinta_modelos(self, linhas) -> None:
        try:
            tm = self.query_one("#tb_modelos", DataTable)
        except NoMatches:
            return
        cur = tm.cursor_row
        tm.clear()
        for ln in linhas:
            tm.add_row(*ln, key=ln[0])
        if 0 <= cur < tm.row_count:
            tm.move_cursor(row=cur)

    def atualizar_selects(self) -> None:
        """Repopula os Selects sem perder a escolha atual (set_options zera o valor)."""
        chat_sel = self.query_one("#chat_bot", Select)
        logs_sel = self.query_one("#logs_bot", Select)
        cur_chat, cur_logs = chat_sel.value, logs_sel.value
        chat = [(b["nome"], b["nome"]) for b in self.cfg["bots"] if not C.embedding(b)]
        todos = [(b["nome"], b["nome"]) for b in self.cfg["bots"]]
        self._repopulando = True
        try:
            chat_sel.set_options(chat)
            logs_sel.set_options(todos)
            if cur_chat in dict(chat):
                chat_sel.value = cur_chat
            if cur_logs in dict(todos):
                logs_sel.value = cur_logs
        finally:
            self._repopulando = False

    def _escolher(self, select_id: str, nome: str) -> bool:
        """Seleciona `nome` num Select só se for opção válida (senão a TUI cairia)."""
        sel = self.query_one(select_id, Select)
        if nome not in [v for _, v in sel._options]:
            self.saida(f"[yellow]{nome} ainda não está na lista — tecle F5[/]")
            return False
        sel.value = nome
        return True

    def atualizar_endpoints(self) -> None:
        cfg = self.cfg
        md = ["# Endpoints (llama-server direto, sem camadas)\n"]
        cred = C.CRED_FILE.is_file()
        for b in cfg["bots"]:
            u = C.urls(cfg, b)
            md.append(f"## {b['nome']} — {b.get('descricao', '')}\n")
            for k, v in u.items():
                md.append(f"- **{k}**: `{v}` → `/health`, `/v1/models`, "
                          + ("`/v1/embeddings`" if C.embedding(b) else "`/v1/chat/completions`, `/completion`"))
            if C.embedding(b):
                md.append(f"\n```bash\ncurl {u['rede']}/v1/embeddings -H 'Content-Type: application/json' "
                          f"-d '{{\"input\":[\"texto\"]}}'\n```")
            else:
                md.append(f"\n```bash\ncurl {u['rede']}/v1/chat/completions -H 'Content-Type: application/json' "
                          f"-d '{{\"messages\":[{{\"role\":\"user\",\"content\":\"oi\"}}]}}'\n```")
            if "tunel" in u:
                md.append(f"Pela internet: mesmos caminhos em `{u['tunel']}` com os headers "
                          f"`CF-Access-Client-Id` e `CF-Access-Client-Secret` "
                          + (f"(valores em `{C.CRED_FILE}`, modo 600)" if cred else "(arquivo de credenciais não encontrado)")
                          + ", vindo da rede autorizada.")
            md.append("")
        self.query_one("#ep", Markdown).update("\n".join(md))

    # ------------------------------------------------------------ seleção
    def _bot_selecionado(self) -> str | None:
        tb = self.query_one("#tb_bots", DataTable)
        if tb.row_count == 0 or tb.cursor_row < 0:
            return None
        nome = str(tb.get_row_at(tb.cursor_row)[0])
        if nome.startswith("(externo)"):
            self.saida("[yellow]processo de fora do bots.yml — não é operado daqui[/]")
            return None
        return nome

    def _modelo_selecionado(self) -> pathlib.Path | None:
        tm = self.query_one("#tb_modelos", DataTable)
        if tm.row_count == 0 or tm.cursor_row < 0:
            return None
        return pathlib.Path(self.cfg["modelos_dir"]) / str(tm.get_row_at(tm.cursor_row)[0])

    # ------------------------------------------------------------ ações (threads)
    @work(thread=True, group="acao")
    def _rodar(self, rotulo: str, fn, *args) -> None:
        self._seguro(self.saida, f"[b]▶ {rotulo}[/]")
        try:
            rc = fn(*args, out=lambda m: self._seguro(self.saida, m))
            if rc:
                self._seguro(self.saida, f"[red]rc={rc}[/]")
        except (C.ConfigError, S.OperError) as e:
            self._seguro(self.saida, f"[red]ERRO:[/] {e}")
        except Exception as e:  # mostra em vez de derrubar a TUI
            self._seguro(self.saida, f"[red]{type(e).__name__}:[/] {e}")
        self._seguro(self.atualizar_painel)

    def action_start(self) -> None:
        if (n := self._bot_selecionado()):
            self._rodar(f"start {n}", S.start, self.cfg, n)

    def action_stop(self) -> None:
        if (n := self._bot_selecionado()):
            self._rodar(f"stop {n}", S.stop, self.cfg, n)

    def action_restart(self) -> None:
        if (n := self._bot_selecionado()):
            self._rodar(f"restart {n}", S.restart, self.cfg, n)

    def action_apply(self) -> None:
        self._rodar("apply --restart", S.apply, self.cfg, False, True)

    def action_check(self) -> None:
        def _check(cfg, out):
            for nivel, msg in S.check(cfg):
                out(("[red]FALHA:[/] " if nivel == "FALHA" else "[yellow]AVISO:[/] " if nivel == "AVISO" else "") + msg)
            out("check concluído")
        self._rodar("check", _check, self.cfg)

    def action_editar(self) -> None:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
        with self.suspend():
            subprocess.call([editor, str(C.BOTS_YML)])
        self.action_atualizar()
        self.saida("bots.yml recarregado — use [b]a[/] para aplicar")

    def action_logs(self) -> None:
        if (n := self._bot_selecionado()) and self._escolher("#logs_bot", n):
            self.query_one("#tabs", TabbedContent).active = "logs"

    def action_chat(self) -> None:
        if (n := self._bot_selecionado()):
            b = C.bot(self.cfg, n)
            if C.embedding(b):
                self.saida(f"{n} é bot de embedding — sem chat"); return
            if self._escolher("#chat_bot", n):
                self.query_one("#tabs", TabbedContent).active = "chat"
                self.query_one("#chat_in", Input).focus()

    # ------------------------------------------------------------ modelos: novo bot / baixar
    def action_novo_bot(self) -> None:
        m = self._modelo_selecionado()
        if m is None:
            self.query_one("#tabs", TabbedContent).active = "modelos"
            self.saida("selecione um modelo na aba Modelos e tecle [b]n[/]"); return
        porta = max([b["porta"] for b in self.cfg["bots"]] + [8080]) + 1
        emb = M.eh_embedding(m)
        self.push_screen(NovoBot(m, porta, emb), self._criar_bot)

    def _criar_bot(self, res: dict | None) -> None:
        if not res:
            return
        bloco = res["bloco"]
        def _cria(cfg, out):
            out(f"flags: {bloco['extra_args']}")
            out(res["explica"])
            novo = C.adicionar_bot(bloco)
            out(f"bots.yml: bot {bloco['nome']} adicionado (cópia anterior em archived/)")
            self.cfg = novo
            self._seguro(self.atualizar_selects)      # só depois do cfg novo existir
            rc = S.apply(novo, prune=False, restart=False, out=out)
            if rc == 0:
                S.start(novo, bloco["nome"], out=out)
            return rc
        self._rodar(f"novo bot {bloco.get('nome')}", _cria, self.cfg)

    def action_baixar(self) -> None:
        self.push_screen(Baixar(), self._baixar)

    def _baixar(self, res: dict | None) -> None:
        if not res or not res.get("repo"):
            return
        def _dl(cfg, out):
            repo, arq = res["repo"], res.get("arquivo")
            if not arq:
                ggufs = M.hf_listar(repo)
                if len(ggufs) != 1:
                    out(f"{repo}: {len(ggufs)} arquivos .gguf — informe qual:")
                    for f in ggufs:
                        out(f"  {f}")
                    return 1
                arq = ggufs[0]
            ultimo = [0.0]
            def prog(feito, total):
                if time.time() - ultimo[0] > 2 or feito == total:
                    ultimo[0] = time.time()
                    out(f"  {feito/1024**2:.0f} / {total/1024**2 if total else 0:.0f} MiB")
            dest = M.baixar(cfg, repo, arq, progresso=prog)
            out(f"[green]ok:[/] {dest}")
            self._seguro(self.atualizar_modelos)
            return 0
        self._rodar(f"baixar {res['repo']}", _dl, self.cfg)

    # ------------------------------------------------------------ chat
    def on_input_submitted(self, ev: Input.Submitted) -> None:
        if ev.input.id != "chat_in":
            return
        texto = ev.value.strip()
        nome = self.query_one("#chat_bot", Select).value
        if not texto or nome is Select.BLANK:
            return
        ev.input.value = ""
        b = C.bot(self.cfg, str(nome))
        self.query_one("#chat_log", RichLog).write(f"[b cyan]você:[/] {texto}")
        self._chat_hist.append({"role": "user", "content": texto})
        self._chat_stream(b, self.query_one("#chat_atual", Static), self.query_one("#chat_log", RichLog))

    @work(thread=True, exclusive=True, group="chat")
    def _chat_stream(self, b: dict, atual: Static, log: RichLog) -> None:
        partes, n, t0, pensando = [], 0, time.time(), False
        try:
            for tipo, pedaco in api.chat_stream(b["porta"], self._chat_hist):
                n += 1
                if tipo == "raciocinio":
                    if not pensando:
                        self._seguro(atual.update, "(pensando…)"); pensando = True
                    continue
                partes.append(pedaco)
                self._seguro(atual.update, "".join(partes)[-600:])
        except Exception as e:
            self._seguro(log.write, f"[red]erro:[/] {e}")
            return
        dt = time.time() - t0
        resp = "".join(partes)
        self._chat_hist.append({"role": "assistant", "content": resp})
        self._seguro(log.write, f"[b green]{b['nome']}:[/] {resp}\n[dim]{n} tokens em {dt:.1f}s ≈ {n/dt if dt else 0:.0f} tok/s[/]")
        self._seguro(atual.update, "")

    def on_select_changed(self, ev: Select.Changed) -> None:
        if self._repopulando:          # F5 não apaga a conversa
            return
        if ev.select.id == "chat_bot":
            self._chat_hist = []
            self.query_one("#chat_log", RichLog).clear()
        elif ev.select.id == "logs_bot" and ev.value is not Select.BLANK:
            self._seguir_logs(str(ev.value))

    # ------------------------------------------------------------ logs
    def _seguir_logs(self, nome: str) -> None:
        if self._logs_proc:
            self._logs_proc.terminate(); self._logs_proc = None
        log = self.query_one("#logs_log", RichLog)
        log.clear()
        u = C.unit_name(C.bot(self.cfg, nome))
        proc = subprocess.Popen(["journalctl", "-u", u, "-n", "80", "-f", "--no-pager", "-o", "short-iso"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self._logs_proc = proc          # criado aqui (thread principal): nunca fica sem handle
        self._logs_worker(proc, log)

    @work(thread=True, exclusive=True, group="logs")
    def _logs_worker(self, proc: subprocess.Popen, log: RichLog) -> None:
        for linha in proc.stdout:
            if self._logs_proc is not proc:
                break
            self._seguro(log.write, linha.rstrip())
        proc.terminate()

    def on_unmount(self) -> None:
        if self._logs_proc:
            self._logs_proc.terminate()


def main() -> int:
    FzbotsApp().run()
    return 0
