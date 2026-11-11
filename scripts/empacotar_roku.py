"""Gera o ZIP de sideload com o manifest na raiz do arquivo."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


RAIZ = Path(__file__).resolve().parents[1]


def empacotar(origem, destino):
    arquivos = [origem / "manifest", origem / "source/main.brs"]
    for extensao in ("*.xml", "*.brs"):
        arquivos.extend(sorted((origem / "components").rglob(extensao)))
    if origem / "components/Painel.xml" not in arquivos or origem / "components/Painel.brs" not in arquivos:
        raise FileNotFoundError("Componente Painel incompleto.")
    for arquivo in arquivos:
        if not arquivo.is_file():
            raise FileNotFoundError(arquivo)

    destino.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destino, "w", compression=ZIP_DEFLATED) as pacote:
        for arquivo in arquivos:
            pacote.write(arquivo, arquivo.relative_to(origem).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=RAIZ / "dist/esus-cast-roku.zip")
    args = parser.parse_args()
    empacotar(RAIZ / "receiver-roku", args.saida)
    print(args.saida.resolve())


if __name__ == "__main__":
    main()
