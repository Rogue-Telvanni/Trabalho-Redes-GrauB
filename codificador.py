"""Codificação de banda base (códigos de linha).

Banda base: o próprio nível de tensão carrega o bit. Não existe portadora, o
sinal ocupa as frequências próximas de zero.

Convenções adotadas (V = 1 volt):
    NRZ unipolar  bit 1 -> +V        bit 0 -> 0
    NRZ polar     bit 1 -> +V        bit 0 -> -V
    Manchester    bit 1 -> -V e +V   (transição de SUBIDA no meio do bit)
                  bit 0 -> +V e -V   (transição de DESCIDA no meio do bit)
                  Esta é a convenção do IEEE 802.3 (Ethernet).

Cada função devolve um vetor com `amostras_por_bit` amostras para cada bit.
"""
import numpy as np

V = 1.0
AMOSTRAS_POR_BIT = 100


def NRZunipolar(bit_seq, amostras_por_bit=AMOSTRAS_POR_BIT, v=V):
    """Bit 1 liga o nível, bit 0 desliga.

    Simples, mas tem componente DC (a média do sinal é v/2 com bits
    equilibrados) e, em sequência longa de bits iguais, o sinal fica parado:
    o receptor não vê nenhuma borda para acertar o relógio.
    """
    return np.repeat(np.asarray(bit_seq) * v, amostras_por_bit)


def NRZpolar(bit_seq, amostras_por_bit=AMOSTRAS_POR_BIT, v=V):
    """Bit 1 vira +v, bit 0 vira -v.

    Com bits equilibrados a média é zero, e os dois níveis ficam mais
    distantes (2v em vez de v), o que dá mais resistência a ruído. O problema
    de sincronismo continua: bits iguais em sequência não geram transição.
    """
    return np.repeat((2 * np.asarray(bit_seq) - 1) * v, amostras_por_bit)


def Manchester(bit_seq, amostras_por_bit=AMOSTRAS_POR_BIT, v=V):
    """Cada bit é dividido em duas metades de níveis opostos.

    O bit fica na DIREÇÃO da transição do meio. Como essa transição existe em
    todo bit, o receptor sempre tem uma borda para sincronizar o relógio, e a
    média de cada bit é zero (sem componente DC). O custo é a banda: o sinal
    pode mudar duas vezes por bit, o dobro do NRZ.
    """
    if amostras_por_bit % 2:
        raise ValueError("amostras_por_bit precisa ser par (duas metades iguais)")
    polar = 2 * np.asarray(bit_seq) - 1
    metades = np.column_stack((-polar, polar)).ravel()
    return np.repeat(metades * v, amostras_por_bit // 2)


def _por_bit(sinal, amostras_por_bit):
    """Reorganiza o sinal em uma matriz com uma linha por bit."""
    return np.reshape(sinal, (-1, amostras_por_bit))


# Decodificadores: tiram a média de cada intervalo, o que cancela boa parte do
# ruído porque ele oscila em torno de zero. Só são usados no teste com ruído.

def decodificar_NRZunipolar(sinal, amostras_por_bit=AMOSTRAS_POR_BIT, v=V):
    """O limiar fica no meio dos dois níveis: v/2."""
    return (_por_bit(sinal, amostras_por_bit).mean(axis=1) > v / 2).astype(int)


def decodificar_NRZpolar(sinal, amostras_por_bit=AMOSTRAS_POR_BIT):
    """O limiar é zero: basta olhar o sinal da média."""
    return (_por_bit(sinal, amostras_por_bit).mean(axis=1) > 0).astype(int)


def decodificar_Manchester(sinal, amostras_por_bit=AMOSTRAS_POR_BIT):
    """Compara as metades: segunda maior que a primeira significa subida (1)."""
    linhas = _por_bit(sinal, amostras_por_bit)
    meio = amostras_por_bit // 2
    return (linhas[:, meio:].mean(axis=1) > linhas[:, :meio].mean(axis=1)).astype(int)
