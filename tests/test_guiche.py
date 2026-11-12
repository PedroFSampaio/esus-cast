from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sender-windows"))

try:
    from guiche import CapturaGuiche, ORIGEM, PAGINA_TV, QuadroGuiche
    from playwright.sync_api import Error, sync_playwright
except ModuleNotFoundError as erro:
    if erro.name != "playwright":
        raise
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "Instale as dependências opcionais do modo Guichê.")
class TesteGuiche(unittest.TestCase):
    def test_quadro_expira_com_a_sessao(self):
        quadro = QuadroGuiche()
        with patch("guiche.monotonic", side_effect=[10, 11, 12]):
            quadro.publicar(b"jpeg de teste", sessao_expira=12)
            self.assertEqual(quadro.obter_jpeg(), b"jpeg de teste")
            self.assertIsNone(quadro.obter_jpeg())

    def test_edge_so_captura_painel_autorizado(self):
        html = """<div class="tv-display" style="width:480px;height:270px;background:#123">
                    <div class="display-main" style="color:white">Senha fictícia T-001</div>
                  </div>"""
        with sync_playwright() as playwright:
            try:
                navegador = playwright.chromium.launch(channel="msedge", headless=True)
            except Error as erro:
                if "distribution 'msedge' is not found" in str(erro):
                    self.skipTest("Microsoft Edge não instalado.")
                raise
            try:
                pagina = navegador.new_page(service_workers="block")
                quadros = QuadroGuiche()
                captura = CapturaGuiche(pagina, quadros)
                status, perfil = 401, None

                def simular(route):
                    if route.request.url == PAGINA_TV:
                        route.fulfill(body=html, content_type="text/html")
                    elif route.request.url == ORIGEM + "/api/queue":
                        route.fulfill(status=status, json={"me": {"role": perfil}})
                    else:
                        route.abort()

                def consultar_fila():
                    with pagina.expect_event("requestfinished", predicate=lambda r: r.url == ORIGEM + "/api/queue"):
                        pagina.evaluate("fetch('/api/queue').then(r => r.json())")

                pagina.route("**/*", simular)
                pagina.goto(PAGINA_TV)
                consultar_fila()
                self.assertFalse(captura.capturar())
                self.assertIsNone(quadros.obter_jpeg())

                status, perfil = 200, "admin"
                consultar_fila()
                self.assertFalse(captura.capturar())

                perfil = "tv"
                consultar_fila()
                self.assertTrue(captura.capturar())
                with Image.open(BytesIO(quadros.obter_jpeg())) as imagem:
                    self.assertEqual((imagem.format, imagem.size), ("JPEG", (480, 270)))

                pagina.evaluate("document.querySelector('.display-main').classList.add('display-warning')")
                self.assertFalse(captura.capturar())
                self.assertIsNone(quadros.obter_jpeg())
                pagina.evaluate("document.querySelector('.display-main').classList.remove('display-warning')")
                self.assertTrue(captura.capturar())

                status, perfil = 401, None
                consultar_fila()
                self.assertIsNone(quadros.obter_jpeg())
                self.assertFalse(captura.capturar())
            finally:
                navegador.close()
