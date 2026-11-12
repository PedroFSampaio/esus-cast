"""Transmissor HTTP do e-SUS Cast para a Roku."""

import argparse
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from ipaddress import IPv4Address, IPv4Network
import re
import secrets
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs, urlsplit

from PIL import Image, ImageDraw, ImageFont

REDES_PRIVADAS = tuple(map(IPv4Network, ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))


class Painel:
    def __init__(self):
        self.lock = Lock()
        self.numero = 0
        self.inicio = monotonic()
        self.relogio = datetime.now().astimezone()
        self.jpeg = b""

    def obter_jpeg(self):
        with self.lock:
            intervalo = int((monotonic() - self.inicio) // 2)
            numero = intervalo + 1
            if numero != self.numero:
                horario = self.relogio + timedelta(seconds=intervalo * 2)
                self.jpeg = desenhar_painel(numero, horario)
                self.numero = numero
            return self.jpeg


def desenhar_painel(numero, horario):
    imagem = Image.new("RGB", (1280, 720), "#102338")
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((64, 170, 1215, 555), fill="#20435b")
    desenho.rectangle((64, 170, 75, 555), fill="#58dcc6")

    def escrever(x, y, tamanho, texto, cor="#ffffff"):
        fonte = ImageFont.load_default(size=tamanho)
        desenho.text((x, y), texto, font=fonte, fill=cor)

    escrever(64, 48, 44, "e-SUS Cast | Painel de teste")
    escrever(100, 211, 40, "SENHA FICTÍCIA", "#b7ebea")
    escrever(100, 268, 128, f"T-{(numero - 1) % 1000:03d}")
    escrever(100, 452, 49, f"Guichê {(numero - 1) % 3 + 1}")
    relogio = horario.isoformat(timespec="milliseconds")
    escrever(64, 604, 34, f"Quadro {numero}  |  Windows {relogio}")
    saida = BytesIO()
    imagem.save(saida, format="JPEG", quality=88)
    return saida.getvalue()


class ServidorPainel(ThreadingHTTPServer):
    def __init__(self, endereco, ip_roku, token, painel=None):
        self.ips_permitidos = {endereco[0], "127.0.0.1", ip_roku}
        self.token = token
        self.painel = painel if painel is not None else Painel()
        super().__init__(endereco, RequisicaoPainel)

    def get_request(self):
        conexao, endereco = super().get_request()
        conexao.settimeout(5)
        return conexao, endereco

    def handle_error(self, request, client_address):
        print("Falha ao responder uma solicitação HTTP.", flush=True)


class RequisicaoPainel(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # O log padrão inclui a URL completa com o token.
        pass

    def do_GET(self):
        if self.client_address[0] not in self.server.ips_permitidos:
            self.responder(HTTPStatus.FORBIDDEN, b"Origem nao autorizada.\n")
            return

        try:
            url = urlsplit(self.path)
            tokens = parse_qs(url.query, max_num_fields=4).get("token", [])
        except ValueError:
            self.responder(HTTPStatus.BAD_REQUEST, b"Requisicao invalida.\n")
            return

        if url.path != "/frame.jpg":
            self.responder(HTTPStatus.NOT_FOUND, b"Endpoint inexistente.\n")
            return

        if len(tokens) != 1 or not secrets.compare_digest(
            tokens[0].encode("utf-8"), self.server.token.encode("ascii")
        ):
            self.responder(HTTPStatus.FORBIDDEN, b"Token invalido.\n")
            return

        jpeg = self.server.painel.obter_jpeg()
        if jpeg is None:
            self.responder(HTTPStatus.SERVICE_UNAVAILABLE, b"Painel indisponivel.\n")
            return
        self.responder(HTTPStatus.OK, jpeg, "image/jpeg")

    def responder(self, status, corpo, tipo="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(corpo)


def ipv4_local(texto):
    try:
        ip = IPv4Address(texto)
    except ValueError as erro:
        raise argparse.ArgumentTypeError("Informe um IPv4 válido.") from erro
    if not (ip.is_loopback or ip.is_link_local or any(ip in rede for rede in REDES_PRIVADAS)):
        raise argparse.ArgumentTypeError("Use um IPv4 privado, link-local ou de loopback.")
    return str(ip)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", type=ipv4_local, default="127.0.0.1", help="IPv4 do Windows")
    parser.add_argument("--roku", type=ipv4_local, help="IPv4 do único receptor permitido")
    parser.add_argument("--porta", type=int, default=8766)
    parser.add_argument("--token", help="16 dígitos hexadecimais minúsculos para retomar um teste")
    parser.add_argument("--guiche", action="store_true", help="Captura o painel da TV do Guichê Policlínica no Edge")
    args = parser.parse_args()
    if args.ip != "127.0.0.1" and args.roku is None:
        parser.error("Informe --roku para servir em rede.")
    if not 1 <= args.porta <= 65535:
        parser.error("A porta precisa estar entre 1 e 65535.")
    if args.token is not None and re.fullmatch(r"[0-9a-f]{16}", args.token) is None:
        parser.error("Use 16 dígitos hexadecimais minúsculos como token.")

    token = args.token or secrets.token_hex(8)
    try:
        if args.guiche:
            try:
                from guiche import QuadroGuiche, transmitir
            except ModuleNotFoundError:
                parser.exit(1, "Instale o modo Guichê com scripts\\preparar-guiche.cmd.\n")
            painel = QuadroGuiche()
        else:
            painel = Painel()
        with ServidorPainel((args.ip, args.porta), args.roku, token, painel) as servidor:
            fonte = "Guichê Policlínica" if args.guiche else "Painel fictício"
            print(f"{fonte} em http://{args.ip}:{args.porta}/frame.jpg", flush=True)
            print(f"Roku permitida: {args.roku or 'teste local'}", flush=True)
            print(f"Token da sessão: {token}", flush=True)
            print("Pressione Ctrl+C para parar.", flush=True)
            if args.guiche:
                transmitir(servidor, painel)
            else:
                servidor.serve_forever()
    except KeyboardInterrupt:
        print("Servidor encerrado.")
    except OSError as erro:
        parser.exit(1, f"Falha no servidor. Confira o IPv4 e a porta. {erro}\n")


if __name__ == "__main__":
    main()
