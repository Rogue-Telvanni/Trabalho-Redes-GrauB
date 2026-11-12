"""Transmissor: mensagem ASCII -> bits -> sinal -> canal.

Envia a mensagem uma vez para cada técnica (e, se pedido, para cada Eb/N0 e
cenário de canal da varredura) e mostra o resumo devolvido pelo receptor.

Variáveis de ambiente:
    MENSAGEM         frase em ASCII a transmitir
    TECNICAS         "todas" ou lista separada por vírgula (ex.: "BPSK,Manchester")
    VARRER_EBN0_DB   opcional, ex.: "0,2,4,6,8,10,12,14" (senão usa o do canal)
    VARRER_CANAIS    opcional, ex.: "awgn,rajadas"     (senão usa o do canal)
    CANAL_HOST / CANAL_PORTA
"""
import os
import time

import mensagem
import protocolo
import ruido

MENSAGEM_PADRAO = "REDES DE COMPUTADORES - UNISINOS 2026"


def _lista(variavel, converter=str):
    valor = os.environ.get(variavel, "").strip()
    return [converter(v.strip()) for v in valor.split(",") if v.strip()] if valor else [None]


def main():
    texto = os.environ.get("MENSAGEM", MENSAGEM_PADRAO)
    pedidas = os.environ.get("TECNICAS", "todas")
    tecnicas = list(ruido.TECNICAS) if pedidas == "todas" else [t.strip() for t in pedidas.split(",")]
    desconhecidas = [t for t in tecnicas if t not in ruido.TECNICAS]
    if desconhecidas:
        raise SystemExit(f"técnicas desconhecidas: {desconhecidas}. Use: {list(ruido.TECNICAS)}")
    destino = (os.environ.get("CANAL_HOST", "localhost"), int(os.environ.get("CANAL_PORTA", 5000)))

    bits = mensagem.ascii_para_bits(texto)
    sessao = time.strftime("%Y%m%d-%H%M%S")
    print(f"sessão {sessao}: '{texto}' ({len(texto)} caracteres, {len(bits)} bits)", flush=True)

    quadro = 0
    for canal_tipo in _lista("VARRER_CANAIS"):
        for ebn0_db in _lista("VARRER_EBN0_DB", float):
            controle = {k: v for k, v in (("canal_tipo", canal_tipo), ("ebn0_db", ebn0_db)) if v is not None}
            for tecnica in tecnicas:
                gerar = ruido.TECNICAS[tecnica][0]
                cabecalho = {
                    "sessao": sessao,
                    "quadro": quadro,
                    "tecnica": tecnica,
                    "amostras_por_bit": ruido.N,
                    "n_bits": len(bits),
                    "controle": controle,
                    # Referência fora de banda: o receptor NÃO usa isto para
                    # decodificar, só para contar e localizar os bits errados.
                    "referencia": {"texto": texto, "bits": "".join(map(str, bits))},
                }
                with protocolo.conectar(*destino) as sock:
                    protocolo.enviar_quadro(sock, cabecalho, gerar(bits))
                    resposta = protocolo.receber_json(sock)
                if "erro" in resposta:
                    print(f"  quadro {quadro:3d} {tecnica:13s} FALHOU: {resposta['erro']}", flush=True)
                else:
                    print(f"  quadro {quadro:3d} {tecnica:13s} {resposta['canal']:24s} "
                          f"{resposta['erros']:4d} bits errados  BER {resposta['ber']:.2e}  "
                          f"'{resposta['texto_recebido']}'", flush=True)
                quadro += 1
    print(f"sessão {sessao} concluída: {quadro} quadros enviados", flush=True)


if __name__ == "__main__":
    main()
