"""Transmissor: mensagem ASCII -> bits -> sinal -> canal.

Dois modos:

    python transmissor.py              automático: envia MENSAGEM com cada técnica
                                       em cada cenário de canal e termina
    python transmissor.py --interativo lê frases do teclado e envia cada uma;
                                       comandos começam com "/" (digite /ajuda)

Variáveis de ambiente:
    MENSAGEM         frase em ASCII do modo automático
    TECNICAS         "todas" ou lista separada por vírgula (ex.: "BPSK,Manchester")
    VARRER_CANAIS    cenários do modo automático (padrão: "ideal,awgn,rajadas")
    VARRER_EBN0_DB   opcional, ex.: "0,2,4,6,8" (senão usa o Eb/N0 do canal)
    CANAL_HOST / CANAL_PORTA
"""
import os
import sys
import time

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


class Transmissor:
    def __init__(self, destino):
        self.destino = destino
        self.sessao = time.strftime("%Y%m%d-%H%M%S")
        self.quadro = 0

    def enviar(self, texto, tecnica, controle):
        """Transmite um quadro e devolve o resumo que o receptor mandou de volta."""
        bits = mensagem.ascii_para_bits(texto)
        cabecalho = {
            "sessao": self.sessao,
            "quadro": self.quadro,
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


def modo_automatico(tx, tecnicas):
    texto = os.environ.get("MENSAGEM", MENSAGEM_PADRAO)
    canais = [c.strip() for c in os.environ.get("VARRER_CANAIS", "ideal,awgn,rajadas").split(",") if c.strip()]
    ebn0s = [float(v) for v in os.environ.get("VARRER_EBN0_DB", "").split(",") if v.strip()] or [None]
    print(f"sessão {tx.sessao}: '{texto}' ({len(texto)} caracteres, {len(texto) * 8} bits)")
    print(f"enviando {len(tecnicas)} técnicas x {len(canais)} cenários x {len(ebn0s)} Eb/N0\n", flush=True)
    for canal_tipo in canais:
        for ebn0_db in ebn0s:
            controle = {"canal_tipo": canal_tipo}
            if ebn0_db is not None:
                controle["ebn0_db"] = ebn0_db
            for tecnica in tecnicas:
                imprimir(tx.quadro, tecnica, tx.enviar(texto, tecnica, controle))
    print(f"\nsessão {tx.sessao} concluída: {tx.quadro} quadros enviados", flush=True)


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
            imprimir(tx.quadro, tecnica, tx.enviar(linha, tecnica, dict(controle)), detalhado=True)
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
    else:
        modo_automatico(tx, tecnicas)


if __name__ == "__main__":
    main()
