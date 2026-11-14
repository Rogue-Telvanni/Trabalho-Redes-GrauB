"""Transmissor: mensagem ASCII ou dados aleatórios -> sinal -> canal.

Modos:

    python transmissor.py              automático:
                                       1. envia MENSAGEM com cada técnica em cada
                                          cenário (demonstração e figuras de sinal)
                                       2. se DURACAO_S > 0, envia quadros de bits
                                          aleatórios por DURACAO_S segundos, em
                                          rodízio por técnica x cenário x Eb/N0
                                          (dados para as curvas de BER), com no
                                          mínimo MIN_RODADAS rodadas
    python transmissor.py --interativo lê frases do teclado e envia cada uma;
                                       comandos começam com "/" (digite /ajuda)

Variáveis de ambiente:
    MENSAGEM         frase em ASCII do modo automático
    TECNICAS         "todas" ou lista separada por vírgula (ex.: "BPSK,Manchester")
    VARRER_CANAIS    cenários da mensagem (padrão: "ideal,awgn,rajadas")
    VARRER_EBN0_DB   Eb/N0 da mensagem (padrão: "20,8": 20 dB deixa ver a forma
                     de onda sob o ruído, 8 dB mostra erros acontecendo)
    DURACAO_S        segundos enviando dados aleatórios (padrão: 0, desligado)
    BITS_POR_QUADRO  bits aleatórios por quadro de dados (padrão: 100000)
    MIN_RODADAS      mínimo de rodadas (repetições) mesmo que DURACAO_S acabe (padrão: 5)
    DADOS_CANAIS     cenários dos dados (padrão: "awgn,rajadas")
    DADOS_EBN0_DB    Eb/N0 dos dados (padrão: "0,2,4,6,8,10,12,14")
    SEMENTE          semente dos bits aleatórios (padrão: 42)
    CANAL_HOST / CANAL_PORTA
"""
import itertools
import os
import sys
import time

import numpy as np

import canal
import mensagem
import protocolo
import ruido

MENSAGEM_PADRAO = "REDES DE COMPUTADORES - UNISINOS 2026"

AJUDA = """\
Digite uma frase (só ASCII, sem acentos) e tecle Enter para transmitir.
Comandos:
  /tecnica <nome>   técnica usada: todas, NRZ unipolar, NRZ polar, Manchester, ASK, FSK, BPSK
                    (pode listar várias com vírgula: /tecnica BPSK,FSK)
  /canal <tipo>     ideal | awgn | rajadas | padrao (volta ao configurado no container)
  /ebn0 <dB>        Eb/N0 do canal, ex.: /ebn0 4   (/ebn0 padrao volta ao do container)
  /config           mostra a configuração atual
  /ajuda            mostra esta ajuda
  /sair             encerra (Ctrl+D também)"""


def _lista(variavel, padrao, converter=str):
    valor = os.environ.get(variavel, padrao)
    return [converter(v.strip()) for v in valor.split(",") if v.strip()]


class Transmissor:
    def __init__(self, destino):
        self.destino = destino
        self.sessao = time.strftime("%Y%m%d-%H%M%S")
        self.quadro = 0

    def enviar(self, bits, tecnica, controle, tipo, texto=None, rodada=None):
        """Transmite um quadro e devolve o resumo que o receptor mandou de volta.

        tipo: "mensagem" (texto ASCII; o canal guarda o sinal limpo e o ruidoso
        para as figuras) ou "dados" (bits aleatórios para as curvas de BER).
        """
        cabecalho = {
            "sessao": self.sessao,
            "quadro": self.quadro,
            "tipo": tipo,
            "rodada": rodada,
            "tecnica": tecnica,
            "amostras_por_bit": ruido.N,
            "n_bits": len(bits),
            "controle": controle,
            # Referência fora de banda: o receptor NÃO usa isto para
            # decodificar, só para contar e localizar os bits errados.
            "referencia": {"texto": texto, "bits": "".join(map(str, bits))},
        }
        gerar = ruido.TECNICAS[tecnica][0]
        with protocolo.conectar(*self.destino) as sock:
            protocolo.enviar_quadro(sock, cabecalho, gerar(bits))
            resposta = protocolo.receber_json(sock)
        self.quadro += 1
        return resposta

    def enviar_texto(self, texto, tecnica, controle):
        return self.enviar(mensagem.ascii_para_bits(texto), tecnica, controle, "mensagem", texto)


def imprimir(quadro, tecnica, resposta, detalhado=False):
    if "erro" in resposta:
        print(f"  quadro {quadro:3d} {tecnica:13s} FALHOU: {resposta['erro']}", flush=True)
        return
    print(f"  quadro {quadro:3d} {tecnica:13s} {resposta['canal']:24s} "
          f"{resposta['erros']:4d} bits errados  BER {resposta['ber']:.2e}", flush=True)
    if detalhado or resposta["erros"]:
        print(f"      recebido : {resposta['texto_recebido']}")
        if resposta["erros"]:
            print(f"      diferença: {resposta['diferenca']}")


def interpretar_tecnicas(valor):
    if valor.strip().lower() == "todas":
        return list(ruido.TECNICAS)
    nomes = {n.lower(): n for n in ruido.TECNICAS}
    escolhidas = [nomes.get(t.strip().lower()) for t in valor.split(",")]
    if None in escolhidas or not escolhidas:
        raise ValueError(f"técnica desconhecida. Use: todas, {', '.join(ruido.TECNICAS)}")
    return escolhidas


def enviar_mensagem(tx, tecnicas):
    """Parte 1: a mesma frase em cada técnica e cenário."""
    texto = os.environ.get("MENSAGEM", MENSAGEM_PADRAO)
    canais = _lista("VARRER_CANAIS", "ideal,awgn,rajadas")
    ebn0s = _lista("VARRER_EBN0_DB", "20,8", float)
    # O canal ideal ignora o Eb/N0, então só precisa de uma passada.
    combinacoes = [(c, e) for c in canais for e in (ebn0s if c != "ideal" else [None])]
    print(f"sessão {tx.sessao}: '{texto}' ({len(texto)} caracteres, {len(texto) * 8} bits)")
    print(f"mensagem: {len(tecnicas)} técnicas x {len(combinacoes)} combinações de canal\n", flush=True)
    for canal_tipo, ebn0_db in combinacoes:
        controle = {"canal_tipo": canal_tipo}
        if ebn0_db is not None:
            controle["ebn0_db"] = ebn0_db
        for tecnica in tecnicas:
            imprimir(tx.quadro, tecnica, tx.enviar_texto(texto, tecnica, controle))


def _milhar(n):
    """1000000 -> '1.000.000' (separador de milhar brasileiro)."""
    return f"{n:,}".replace(",", ".")


def enviar_dados(tx, tecnicas, duracao_s):
    """Parte 2: bits aleatórios por duracao_s segundos, em rodadas completas.

    Uma rodada passa uma vez por cada combinação técnica x cenário x Eb/N0, e
    cada rodada usa bits novos: as rodadas são as repetições do experimento.
    O tempo só é conferido entre rodadas, para que todos os pontos tenham o
    mesmo número de repetições. O envio só para quando passou duracao_s E
    foram feitas pelo menos MIN_RODADAS rodadas (o PDF pede 5 repetições).
    """
    n_bits = int(os.environ.get("BITS_POR_QUADRO", 100_000))
    min_rodadas = int(os.environ.get("MIN_RODADAS", 5))
    canais = _lista("DADOS_CANAIS", "awgn,rajadas")
    ebn0s = _lista("DADOS_EBN0_DB", "0,2,4,6,8,10,12,14", float)
    semente = int(os.environ.get("SEMENTE", 42))
    combinacoes = list(itertools.product(canais, ebn0s, tecnicas))
    print(f"\ndados: {duracao_s:g} s de quadros com {n_bits} bits aleatórios, rodadas de "
          f"{len(combinacoes)} quadros ({len(tecnicas)} técnicas x {len(canais)} cenários x "
          f"{len(ebn0s)} Eb/N0), no mínimo {min_rodadas} rodadas", flush=True)
    inicio = time.time()
    rodada = 0
    while rodada < max(min_rodadas, 1) or time.time() - inicio < duracao_s:
        bits = np.random.default_rng([semente, rodada]).integers(0, 2, n_bits)
        falhas = 0
        for canal_tipo, ebn0_db, tecnica in combinacoes:
            resposta = tx.enviar(bits, tecnica, {"canal_tipo": canal_tipo, "ebn0_db": ebn0_db},
                                 "dados", rodada=rodada)
            falhas += "erro" in resposta
        rodada += 1
        decorrido = time.time() - inicio
        print(f"  rodada {rodada:2d} concluída  ({decorrido:5.1f} s, "
              f"{_milhar(rodada * n_bits)} bits por ponto)"
              f"{'  FALHAS: ' + str(falhas) if falhas else ''}", flush=True)
    print(f"dados: {rodada} rodadas em {time.time() - inicio:.1f} s, "
          f"{_milhar(rodada * n_bits)} bits por ponto", flush=True)


def modo_interativo(tx, tecnicas):
    try:
        import readline  # noqa: F401  (setas e histórico no input)
    except ImportError:
        pass
    controle = {}

    def config():
        canal_tipo = controle.get("canal_tipo", "padrão do container")
        ebn0 = f"{controle['ebn0_db']:g} dB" if "ebn0_db" in controle else "padrão do container"
        return f"técnicas: {', '.join(tecnicas)} | canal: {canal_tipo} | Eb/N0: {ebn0}"

    print(f"Transmissor interativo, sessão {tx.sessao}. Digite /ajuda para os comandos.")
    print(config(), flush=True)
    while True:
        try:
            linha = input("\ntx> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not linha:
            continue
        if linha.startswith("/"):
            comando, _, argumento = linha[1:].partition(" ")
            comando, argumento = comando.lower(), argumento.strip()
            try:
                if comando in ("sair", "exit", "quit"):
                    break
                elif comando == "ajuda":
                    print(AJUDA)
                elif comando == "config":
                    print(config())
                elif comando == "tecnica":
                    tecnicas = interpretar_tecnicas(argumento)
                    print(config())
                elif comando == "canal":
                    if argumento == "padrao":
                        controle.pop("canal_tipo", None)
                    elif argumento in canal.TIPOS:
                        controle["canal_tipo"] = argumento
                    else:
                        raise ValueError(f"use: {', '.join(canal.TIPOS)} ou padrao")
                    print(config())
                elif comando == "ebn0":
                    if argumento == "padrao":
                        controle.pop("ebn0_db", None)
                    else:
                        try:
                            controle["ebn0_db"] = float(argumento.replace(",", "."))
                        except ValueError:
                            raise ValueError("use um número em dB, ex.: /ebn0 4") from None
                    print(config())
                else:
                    print(f"comando desconhecido: /{comando}. Digite /ajuda.")
            except ValueError as erro:
                print(f"erro: {erro}")
            continue
        try:
            mensagem.ascii_para_bits(linha)
        except ValueError as erro:
            print(f"erro: {erro}")
            continue
        print(f"      enviado  : {linha}")
        for tecnica in tecnicas:
            imprimir(tx.quadro, tecnica, tx.enviar_texto(linha, tecnica, dict(controle)), detalhado=True)
    print(f"sessão {tx.sessao} encerrada: {tx.quadro} quadros enviados", flush=True)


def main():
    destino = (os.environ.get("CANAL_HOST", "localhost"), int(os.environ.get("CANAL_PORTA", 5000)))
    try:
        tecnicas = interpretar_tecnicas(os.environ.get("TECNICAS", "todas"))
    except ValueError as erro:
        raise SystemExit(str(erro))
    tx = Transmissor(destino)
    if "--interativo" in sys.argv[1:]:
        modo_interativo(tx, tecnicas)
        return
    enviar_mensagem(tx, tecnicas)
    duracao = float(os.environ.get("DURACAO_S", 0))
    if duracao > 0:
        enviar_dados(tx, tecnicas, duracao)
    print(f"\nsessão {tx.sessao} concluída: {tx.quadro} quadros enviados", flush=True)


if __name__ == "__main__":
    main()
