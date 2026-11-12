"""Formato das mensagens trocadas entre os containers, via TCP.

Quadro de sinal (transmissor -> canal -> receptor):
    4 bytes   tamanho do cabeçalho (inteiro sem sinal, big-endian)
    N bytes   cabeçalho JSON (técnica, bits por amostra, controle, ...)
    M bytes   amostras do sinal, float64 little-endian (M = 8 * n_amostras)

Resposta (receptor -> canal -> transmissor):
    4 bytes   tamanho + JSON com o resumo da recepção (erros, BER, texto)

Cada quadro usa uma conexão nova: conecta, envia, espera a resposta, fecha.
"""
import json
import socket
import struct
import time
import traceback

import numpy as np

_TAMANHO = struct.Struct("!I")
_TIPO_AMOSTRA = np.dtype("<f8")


def _ler_exato(sock, n):
    dados = bytearray()
    while len(dados) < n:
        parte = sock.recv(min(n - len(dados), 1 << 16))
        if not parte:
            raise ConnectionError("conexão fechada no meio de uma mensagem")
        dados += parte
    return bytes(dados)


def enviar_json(sock, objeto):
    corpo = json.dumps(objeto, ensure_ascii=False).encode("utf-8")
    sock.sendall(_TAMANHO.pack(len(corpo)) + corpo)


def receber_json(sock):
    (n,) = _TAMANHO.unpack(_ler_exato(sock, _TAMANHO.size))
    return json.loads(_ler_exato(sock, n))


def enviar_quadro(sock, cabecalho, amostras):
    amostras = np.asarray(amostras, dtype=_TIPO_AMOSTRA)
    enviar_json(sock, dict(cabecalho, n_amostras=len(amostras)))
    sock.sendall(amostras.tobytes())


def receber_quadro(sock):
    cabecalho = receber_json(sock)
    corpo = _ler_exato(sock, cabecalho["n_amostras"] * _TIPO_AMOSTRA.itemsize)
    return cabecalho, np.frombuffer(corpo, dtype=_TIPO_AMOSTRA)


def conectar(host, porta, tentativas=30, espera=1.0):
    """Tenta várias vezes: no `docker compose up` o outro container pode ainda estar subindo."""
    for i in range(tentativas):
        try:
            return socket.create_connection((host, porta), timeout=60)
        except OSError:
            if i == tentativas - 1:
                raise
            time.sleep(espera)


def servir(porta, tratar):
    """Aceita conexões para sempre. tratar(cabecalho, amostras) devolve o JSON de resposta."""
    with socket.create_server(("", porta)) as servidor:
        print(f"escutando na porta {porta}", flush=True)
        while True:
            conexao, origem = servidor.accept()
            with conexao:
                try:
                    cabecalho, amostras = receber_quadro(conexao)
                    enviar_json(conexao, tratar(cabecalho, amostras))
                except Exception as erro:  # um quadro ruim não pode derrubar o servidor
                    traceback.print_exc()
                    try:
                        enviar_json(conexao, {"erro": f"{type(erro).__name__}: {erro}"})
                    except OSError:
                        pass
