"""unittest da validação do bots.yml (stdlib). Rode: PYTHONPATH=. python3 -m unittest -v tests.test_config"""
import copy
import pathlib
import tempfile
import unittest

import yaml

from fzbots import config as C

BASE = {
    "gpu_vram_gb": 6,
    "bots": [
        {"nome": "a", "hostname": "a.exemplo.com", "porta": 8081, "modelo": "/m/a.gguf", "vram_estimada": 1},
        {"nome": "b", "porta": 8082, "modelo": "/m/b.gguf", "vram_estimada": 1, "tunel": False},
    ],
}


def cfg(**alter):
    c = copy.deepcopy(BASE)
    for k, v in C.PADRAO.items():
        c.setdefault(k, v)
    for k, v in alter.items():
        c[k] = v
    return c


class Validacao(unittest.TestCase):
    def ok(self, c):
        C.validate(c)

    def erro(self, c, trecho):
        with self.assertRaises(C.ConfigError) as cm:
            C.validate(c)
        self.assertIn(trecho, str(cm.exception))

    def test_base_valido(self):
        self.ok(cfg())

    def test_chave_desconhecida_no_bot(self):
        c = cfg(); c["bots"][1]["tunnel"] = False
        self.erro(c, "chave desconhecida")

    def test_chave_desconhecida_no_topo(self):
        self.erro(cfg(foo=1), "chave desconhecida no topo")

    def test_tunel_string(self):
        c = cfg(); c["bots"][1]["tunel"] = "false"
        self.erro(c, "true ou false")

    def test_publico_sem_hostname(self):
        c = cfg(); del c["bots"][0]["hostname"]
        self.erro(c, "sem hostname")

    def test_porta_repetida(self):
        c = cfg(); c["bots"][1]["porta"] = 8081
        self.erro(c, "porta repetida")

    def test_hostname_repetido(self):
        c = cfg(); c["bots"][1].pop("tunel"); c["bots"][1]["hostname"] = "a.exemplo.com"
        self.erro(c, "hostname repetido")

    def test_nome_invalido(self):
        c = cfg(); c["bots"][0]["nome"] = "../x"
        self.erro(c, "nome inválido")

    def test_modelo_com_espaco(self):
        c = cfg(); c["bots"][0]["modelo"] = "/m/a b.gguf"
        self.erro(c, "espaço")

    def test_host_port_em_extra_args(self):
        c = cfg(); c["bots"][0]["extra_args"] = "-ngl 99 --host 0.0.0.0"
        self.erro(c, "--host")

    def test_render_unit_bind_e_ordem(self):
        c = cfg(); c["bots"][0]["extra_args"] = "-ngl 99 -c 4096"
        u = C.render_unit(c, c["bots"][0])
        self.assertIn(f"-m /m/a.gguf -ngl 99 -c 4096 --host {C.BIND} --port 8081\n", u)
        self.assertIn("Description=fzbots bot 'a' (a.gguf)", u)

    def test_ingress_so_publicos(self):
        ing = C.render_ingress(cfg())
        self.assertEqual(ing, [{"hostname": "a.exemplo.com", "service": "http://127.0.0.1:8081"},
                               {"service": "http_status:404"}])

    def test_embedding_detectado(self):
        self.assertTrue(C.embedding({"extra_args": "-c 2048 --embedding"}))
        self.assertFalse(C.embedding({"extra_args": "-c 2048"}))

    def test_adicionar_bot_preserva_comentarios_e_valida(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "bots.yml"
            p.write_text("# comentário no topo\ngpu_vram_gb: 6\nbots:\n  - nome: a   # c1\n    hostname: a.exemplo.com\n"
                         "    porta: 8081\n    modelo: /m/a.gguf\n    vram_estimada: 1\n")
            arq_ant = C.ARCHIVED
            novo = C.adicionar_bot({"nome": "b", "porta": 8082, "modelo": "/m/b.gguf", "vram_estimada": 0.5,
                                    "extra_args": "-c 2048 --embedding", "tunel": False,
                                    "consumidores": ["x"]}, path=p)
            texto = p.read_text()
            self.assertIn("# comentário no topo", texto)
            self.assertIn("# c1", texto)
            self.assertEqual([b["nome"] for b in novo["bots"]], ["a", "b"])
            self.assertEqual(yaml.safe_load(texto)["bots"][1]["consumidores"], ["x"])
            with self.assertRaises(C.ConfigError):
                C.adicionar_bot({"nome": "a", "porta": 9, "modelo": "/m/c.gguf", "vram_estimada": 1, "tunel": False}, path=p)
            self.assertEqual(len(yaml.safe_load(p.read_text())["bots"]), 2, "restaurou o yml após falha")


if __name__ == "__main__":
    unittest.main()
