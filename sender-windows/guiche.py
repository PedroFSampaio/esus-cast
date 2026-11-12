"""Captura em memória do painel de TV autorizado do Guichê Policlínica."""

from threading import Lock, Thread
from time import monotonic

from playwright.sync_api import Error, sync_playwright

ORIGEM = "https://chat.saomanuel.sp.gov.br"
PAGINA_TV = ORIGEM + "/?panel=tv"
VALIDADE_SESSAO = 6
VALIDADE_QUADRO = 5


class QuadroGuiche:
    def __init__(self):
        self.lock = Lock()
        self.jpeg = None
        self.expira = 0

    def publicar(self, jpeg, sessao_expira=0):
        with self.lock:
            self.jpeg = jpeg
            self.expira = min(monotonic() + VALIDADE_QUADRO, sessao_expira)

    def obter_jpeg(self):
        with self.lock:
            return self.jpeg if monotonic() < self.expira else None


class CapturaGuiche:
    def __init__(self, pagina, quadros, origem=ORIGEM):
        self.pagina = pagina
        self.quadros = quadros
        self.url_tv = origem + "/?panel=tv"
        self.url_fila = origem + "/api/queue"
        self.sessao_expira = 0
        self.ultima_solicitacao = None
        self.painel = pagina.locator(".tv-display:has(.display-main):not(:has(.display-warning))")
        pagina.on("framenavigated", self.navegou)
        pagina.on("request", self.solicitacao_iniciada)
        pagina.on("requestfinished", self.solicitacao_concluida)
        pagina.on("requestfailed", self.solicitacao_falhou)

    def invalidar_sessao(self):
        self.sessao_expira = 0
        self.quadros.publicar(None)

    def navegou(self, frame):
        if frame == self.pagina.main_frame:
            self.ultima_solicitacao = None
            self.invalidar_sessao()

    def solicitacao_iniciada(self, request):
        if request.method == "GET" and request.url == self.url_fila and request.frame == self.pagina.main_frame:
            self.ultima_solicitacao = request

    def solicitacao_falhou(self, request):
        if request == self.ultima_solicitacao:
            self.invalidar_sessao()

    def solicitacao_concluida(self, request):
        if request != self.ultima_solicitacao:
            return
        try:
            resposta = request.response()
            if self.pagina.url == self.url_tv and resposta and resposta.ok:
                dados = resposta.json()
                if request != self.ultima_solicitacao:
                    return
                if isinstance(dados, dict) and isinstance(dados.get("me"), dict) and dados["me"].get("role") == "tv":
                    self.sessao_expira = monotonic() + VALIDADE_SESSAO
                    return
        except (Error, ValueError):
            pass
        self.invalidar_sessao()

    def autorizada(self):
        return self.pagina.url == self.url_tv and monotonic() < self.sessao_expira and self.painel.is_visible()

    def capturar(self):
        try:
            if self.autorizada():
                jpeg = self.painel.screenshot(type="jpeg", quality=88, timeout=1500)
                if self.autorizada():
                    self.quadros.publicar(jpeg, self.sessao_expira)
                    return True
        except Error:
            pass
        self.quadros.publicar(None)
        return False


def transmitir(servidor, quadros):
    pagina = None
    thread = Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch(channel="msedge", headless=False)
            try:
                contexto = navegador.new_context(
                    viewport={"width": 1280, "height": 720},
                    reduced_motion="reduce",
                    accept_downloads=False,
                    service_workers="block",
                )
                pagina = contexto.new_page()
                captura = CapturaGuiche(pagina, quadros)
                print("No Edge, entre com a conta de TV e aguarde a liberação no Guichê.", flush=True)
                try:
                    pagina.goto(PAGINA_TV, wait_until="commit", timeout=15000)
                except Error:
                    if not pagina.is_closed():
                        print("Não foi possível abrir o Guichê. Recarregue a página no Edge.", flush=True)
                anterior = None
                while not pagina.is_closed():
                    pronto = captura.capturar()
                    if pronto != anterior:
                        print("Painel da TV disponível." if pronto else "Aguardando o painel autorizado do Guichê.", flush=True)
                        anterior = pronto
                    pagina.wait_for_timeout(1000)
            finally:
                quadros.publicar(None)
                navegador.close()
    except Error:
        if pagina is None or not pagina.is_closed():
            raise SystemExit("Falha ao acessar o Edge. Confira a instalação do navegador e tente novamente.") from None
    finally:
        servidor.shutdown()
        thread.join()
