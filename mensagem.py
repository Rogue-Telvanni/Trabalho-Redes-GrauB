"""Conversão entre texto e bits (8 bits por caractere, bit mais significativo primeiro)."""
import numpy as np


def texto_para_bits(texto):
    """UTF-8: letras acentuadas (É, Ç, Ã) ocupam 2 bytes, as demais 1."""
    return np.unpackbits(np.frombuffer(texto.encode("utf-8"), dtype=np.uint8)).astype(int)


def bits_para_texto(bits):
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes().decode("utf-8", errors="replace")


def ascii_para_bits(texto):
    """Como texto_para_bits, mas recusa caracteres fora da tabela ASCII (0 a 127)."""
    try:
        dados = texto.encode("ascii")
    except UnicodeEncodeError as erro:
        raise ValueError(f"a mensagem precisa ser ASCII puro (sem acentos): {erro}") from None
    return np.unpackbits(np.frombuffer(dados, dtype=np.uint8)).astype(int)


def bits_para_ascii_visivel(bits):
    """Um caractere por byte recebido, para alinhar com a mensagem enviada no log.

    Bits errados podem gerar bytes que não são letras imprimíveis (controle ou
    acima de 127); esses aparecem como '·'.
    """
    dados = np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()
    return "".join(chr(b) if 32 <= b <= 126 else "·" for b in dados)


def marcar_caracteres(posicoes_bits_errados, n_caracteres):
    """Linha com '^' embaixo de cada caractere que teve pelo menos um bit errado."""
    errados = {p // 8 for p in posicoes_bits_errados}
    return "".join("^" if i in errados else " " for i in range(n_caracteres))
