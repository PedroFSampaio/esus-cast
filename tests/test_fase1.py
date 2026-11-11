from argparse import ArgumentTypeError
from contextlib import closing
from http.client import HTTPConnection
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
from zipfile import ZipFile

from PIL import Image


RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "sender-windows"), str(RAIZ / "scripts")]

from empacotar_roku import empacotar
from sender import ServidorPainel, ipv4_local


TOKEN = "0123456789abcdef"


class TesteServidor(unittest.TestCase):
    def setUp(self):
        servidor = ServidorPainel(("127.0.0.1", 0), None, TOKEN)
        self.servidor = servidor
        thread = Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(servidor.shutdown)

    def get(self, caminho):
        with closing(HTTPConnection("127.0.0.1", self.servidor.server_port, timeout=2)) as conexao:
            conexao.request("GET", caminho)
            resposta = conexao.getresponse()
            return resposta.status, dict(resposta.getheaders()), resposta.read()

    def test_jpeg_e_atualizacao(self):
        self.servidor.painel.inicio = 10
        with patch("sender.monotonic", side_effect=[10, 11, 12]):
            primeiro = self.get(f"/frame.jpg?token={TOKEN}&v=1")
            repetido = self.get(f"/frame.jpg?token={TOKEN}&v=2")
            atualizado = self.get(f"/frame.jpg?token={TOKEN}&v=3")
        status, headers, jpeg = primeiro
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/jpeg")
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertEqual(int(headers["Content-Length"]), len(jpeg))
        with Image.open(BytesIO(jpeg)) as imagem:
            imagem.load()
            self.assertEqual((imagem.format, imagem.size), ("JPEG", (1280, 720)))
        self.assertEqual(repetido[2], jpeg)
        self.assertEqual(atualizado[0], 200)
        self.assertNotEqual(atualizado[2], jpeg)
        self.assertEqual(self.servidor.painel.numero, 2)

    def test_token_invalido_ausente_ou_duplicado(self):
        for consulta in ("", "?token=incorreto", "?token=%C3%A1", f"?token={TOKEN}&token={TOKEN}"):
            with self.subTest(consulta=consulta):
                self.assertEqual(self.get("/frame.jpg" + consulta)[0], 403)
        self.assertEqual(self.servidor.painel.numero, 0)

    def test_origem_invalida_com_token_correto(self):
        # Remove temporariamente a origem do cliente de loopback.
        with patch.object(self.servidor, "ips_permitidos", {"192.168.1.8"}):
            self.assertEqual(self.get(f"/frame.jpg?token={TOKEN}")[0], 403)

    def test_caminho_desconhecido_e_consulta_invalida(self):
        self.assertEqual(self.get(f"/outro?token={TOKEN}")[0], 404)
        self.assertEqual(self.get("/frame.jpg?a=1&b=2&c=3&d=4&e=5")[0], 400)


class TesteValidacao(unittest.TestCase):
    def test_ipv4_local(self):
        for ip in ("10.1.1.1", "172.16.2.1", "172.31.2.1", "192.168.1.1", "169.254.1.1", "127.0.0.1"):
            self.assertEqual(ipv4_local(ip), ip)
        for ip in ("0.0.0.0", "8.8.8.8", "172.32.1.1", "192.168.001.1", "::1", "exemplo.org"):
            with self.subTest(ip=ip), self.assertRaises(ArgumentTypeError):
                ipv4_local(ip)

    def test_pacote_roku(self):
        with TemporaryDirectory() as temp:
            destino = Path(temp) / "roku.zip"
            empacotar(RAIZ / "receiver-roku", destino)
            with ZipFile(destino) as pacote:
                self.assertIsNone(pacote.testzip())
                self.assertEqual(set(pacote.namelist()), {
                    "manifest", "source/main.brs", "components/Painel.brs", "components/Painel.xml",
                })
                cena = ElementTree.fromstring(pacote.read("components/Painel.xml"))
                self.assertEqual(cena.attrib, {"name": "Painel", "extends": "Scene"})
                for script in cena.findall("script"):
                    self.assertIn(script.attrib["uri"].removeprefix("pkg:/"), pacote.namelist())
                self.assertIn(b'CreateScene("Painel")', pacote.read("source/main.brs"))
