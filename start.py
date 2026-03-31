#!/usr/bin/env python3
"""
Inicializador amigável para execução local e publicação em servidor.
"""

import argparse
import socket
import webbrowser

import uvicorn
from colorama import Fore, Style, init

from app.core.config import settings

init(autoreset=True)


def parse_args():
    """Lê argumentos de linha de comando."""
    parser = argparse.ArgumentParser(description="Inicia o servidor FastAPI do projeto")
    parser.add_argument("--host", default=settings.HOST, help="Host de bind do servidor")
    parser.add_argument("--port", type=int, default=settings.PORT, help="Porta de bind do servidor")
    parser.add_argument(
        "--reload",
        action="store_true",
        default=settings.DEBUG,
        help="Ativa recarga automática para desenvolvimento",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Abre a página principal automaticamente quando o host for local",
    )
    return parser.parse_args()


def get_lan_ip() -> str:
    """Tenta descobrir o IP local da máquina para acesso via celular na mesma rede."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def print_urls(host: str, port: int):
    """Exibe URLs úteis para acesso local e via celular."""
    local_host = "127.0.0.1" if host == "0.0.0.0" else host
    base_url = f"http://{local_host}:{port}"

    print()
    print(f"{Fore.GREEN}{'=' * 72}")
    print(f"{Fore.GREEN}SIOPA - Servidor pronto para web e mobile")
    print(f"{Fore.GREEN}{'=' * 72}")
    print(f"{Fore.CYAN}Local:      {Style.BRIGHT}{base_url}")

    if host == "0.0.0.0":
        lan_ip = get_lan_ip()
        print(f"{Fore.CYAN}Rede local: {Style.BRIGHT}http://{lan_ip}:{port}")
        print(f"{Fore.YELLOW}Acesse esse endereço pelo celular na mesma rede Wi‑Fi.")

    print()
    print(f"- Página principal: {base_url}/")
    print(f"- Interface de anotação: {base_url}/static/annotation.html")
    print(f"- Swagger: {base_url}/docs")
    print(f"- ReDoc: {base_url}/redoc")
    print(f"- Health: {base_url}/health")
    print()


def maybe_open_browser(host: str, port: int):
    """Abre o navegador apenas para hosts locais."""
    if host in {"127.0.0.1", "localhost"}:
        webbrowser.open(f"http://{host}:{port}/")


def main():
    """Ponto de entrada do script."""
    args = parse_args()
    print_urls(args.host, args.port)

    if args.open_browser:
        maybe_open_browser(args.host, args.port)

    uvicorn.run(
        "main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=settings.LOG_LEVEL.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
        server_header=False,
    )


if __name__ == "__main__":
    main()
