"""Modulação digital de uma portadora senoidal: s(t) = A * sen(2*pi*f*t + fase).

Modular é fazer os bits alterarem um parâmetro da senoide, deslocando a
informação para perto da frequência da portadora. É isso que permite usar um
canal passa-faixa, como o rádio, que não transmite sinais de banda base.

    ASK   os bits alteram a AMPLITUDE
    FSK   os bits alteram a FREQUÊNCIA
    BPSK  os bits alteram a FASE
    16-QAM  os bits alteram AMPLITUDE e FASE ao mesmo tempo (4 bits por símbolo)

Todas as frequências são múltiplos inteiros da taxa de bits. Assim cada bit
contém um número inteiro de ciclos: a senoide não dá saltos nas fronteiras e
as portadoras do FSK ficam ortogonais (a correlação entre elas no bit é zero).
"""
import numpy as np

TAXA_BITS = 1_000       # bit/s  -> cada bit dura 1 ms
FREQ_AMOSTRAGEM = 100_000  # Hz  -> 100 amostras por bit
FREQ_PORTADORA = 5_000  # Hz     -> ASK e BPSK, 5 ciclos por bit
FREQ_FSK_0 = 3_000      # Hz     -> bit 0 no FSK
FREQ_FSK_1 = 7_000      # Hz     -> bit 1 no FSK (ambas centradas em 5 kHz)
AMPLITUDE = 1.0         # V

AMOSTRAS_POR_BIT = FREQ_AMOSTRAGEM // TAXA_BITS

# 16-QAM: cada símbolo leva 4 bits, então dura 4 bits (4 ms) e a taxa de bits
# continua 1000 bit/s. Cada portadora (seno = I, cosseno = Q) assume um de 4
# níveis: -V, -V/3, +V/3, +V, em que V = AMPLITUDE.
BITS_POR_SIMBOLO_QAM = 4
AMOSTRAS_POR_SIMBOLO_QAM = BITS_POR_SIMBOLO_QAM * AMOSTRAS_POR_BIT
NIVEL_QAM = AMPLITUDE / 3  # distância entre o centro e o nível mais próximo (d)


def eixo_tempo(n_bits):
    """Instantes de amostragem, em segundos, para n_bits."""
    return np.arange(n_bits * AMOSTRAS_POR_BIT) / FREQ_AMOSTRAGEM


def _portadora(frequencia, t):
    return AMPLITUDE * np.sin(2 * np.pi * frequencia * t)


def ASK(bit_seq):
    """Bit 1 transmite a portadora, bit 0 transmite silêncio.

    É a modulação mais simples, mas toda a informação está na amplitude,
    justamente o parâmetro que ruído e atenuação mais afetam.
    """
    bits = np.repeat(np.asarray(bit_seq), AMOSTRAS_POR_BIT)
    return bits * _portadora(FREQ_PORTADORA, eixo_tempo(len(bit_seq)))


def FSK(bit_seq):
    """Bit 1 usa a frequência f1, bit 0 usa f0, com amplitude constante.

    Amplitude constante torna o FSK mais robusto a variações de ganho. O custo
    é ocupar mais banda, pois o sinal precisa de espaço para as duas frequências.
    """
    bits = np.repeat(np.asarray(bit_seq), AMOSTRAS_POR_BIT)
    t = eixo_tempo(len(bit_seq))
    return np.where(bits == 1, _portadora(FREQ_FSK_1, t), _portadora(FREQ_FSK_0, t))


def BPSK(bit_seq):
    """Bit 1 usa fase 0, bit 0 usa fase 180 graus (a senoide invertida).

    As duas formas de onda são exatamente opostas (s0 = -s1), a maior distância
    possível para uma dada amplitude. Por isso é a mais resistente a ruído das
    três. O custo: o receptor precisa de uma referência de fase da portadora.
    """
    polar = 2 * np.repeat(np.asarray(bit_seq), AMOSTRAS_POR_BIT) - 1
    return polar * _portadora(FREQ_PORTADORA, eixo_tempo(len(bit_seq)))


def _nivel_gray(b1, b2):
    """Dois bits -> nível de 4-PAM com código Gray: 00=-3d, 01=-d, 11=+d, 10=+3d.

    No Gray, níveis vizinhos diferem em um bit só. O erro mais provável do
    ruído é cair no nível vizinho, então ele custa só 1 bit errado.
    """
    indice = 2 * b1 + (b1 ^ b2)
    return (2 * indice - 3) * NIVEL_QAM


def QAM16(bit_seq):
    """16-QAM: 4 bits por símbolo, 2 portadoras em quadratura (seno e cosseno).

    Os 2 primeiros bits do símbolo escolhem a amplitude do seno (I) e os 2
    últimos a do cosseno (Q): 4 x 4 = 16 pontos na constelação. É a modulação
    de ordem superior do trabalho: o símbolo dura 4 bits, então ocupa um quarto
    da banda de um BPSK, mas os pontos ficam mais próximos e o ruído os
    confunde com mais facilidade.
    """
    bits = np.asarray(bit_seq, dtype=int)
    if len(bits) % BITS_POR_SIMBOLO_QAM:
        raise ValueError(f"16-QAM precisa de múltiplo de {BITS_POR_SIMBOLO_QAM} bits")
    b = bits.reshape(-1, BITS_POR_SIMBOLO_QAM)
    i = np.repeat(_nivel_gray(b[:, 0], b[:, 1]), AMOSTRAS_POR_SIMBOLO_QAM)
    q = np.repeat(_nivel_gray(b[:, 2], b[:, 3]), AMOSTRAS_POR_SIMBOLO_QAM)
    t = eixo_tempo(len(bits))
    return i * np.sin(2 * np.pi * FREQ_PORTADORA * t) + q * np.cos(2 * np.pi * FREQ_PORTADORA * t)


def _correlacao(sinal, frequencia):
    """Mede, bit a bit, o quanto o sinal se parece com a portadora.

    Multiplicar pela referência e somar concentra a energia da portadora e faz
    o ruído se cancelar. O fator 2/N normaliza: portadora igual resulta em A.
    """
    referencia = _portadora(frequencia, eixo_tempo(1)) / AMPLITUDE
    linhas = np.reshape(sinal, (-1, AMOSTRAS_POR_BIT))
    return linhas @ referencia * 2 / AMOSTRAS_POR_BIT


def demodular_ASK(sinal):
    """A correlação vale A (portadora presente) ou 0: limiar em A/2."""
    return (_correlacao(sinal, FREQ_PORTADORA) > AMPLITUDE / 2).astype(int)


def demodular_FSK(sinal):
    """Decide pela frequência com a qual o sinal mais se parece."""
    return (_correlacao(sinal, FREQ_FSK_1) > _correlacao(sinal, FREQ_FSK_0)).astype(int)


def demodular_BPSK(sinal):
    """A correlação vale +A ou -A: o limiar é zero."""
    return (_correlacao(sinal, FREQ_PORTADORA) > 0).astype(int)


def simbolos_QAM16(sinal):
    """Coordenadas (I, Q) em volts que o receptor mede em cada símbolo.

    Correlaciona o símbolo com o seno e com o cosseno da portadora. Sem ruído
    caem exatamente nos 16 pontos da constelação; com ruído, ao redor deles.
    """
    n = AMOSTRAS_POR_SIMBOLO_QAM
    linhas = np.reshape(sinal, (-1, n))
    t = np.arange(n) / FREQ_AMOSTRAGEM
    i = linhas @ np.sin(2 * np.pi * FREQ_PORTADORA * t) * 2 / n
    q = linhas @ np.cos(2 * np.pi * FREQ_PORTADORA * t) * 2 / n
    return i, q


def _bits_do_nivel(nivel):
    """Decide o nível de 4-PAM mais próximo (limiares em -2d, 0, +2d) e devolve seus 2 bits."""
    indice = np.clip(np.floor((nivel / NIVEL_QAM + 3) / 2 + 0.5), 0, 3).astype(int)
    b1 = (indice >= 2).astype(int)
    return b1, b1 ^ (indice & 1)


def demodular_QAM16(sinal):
    """Mede I e Q de cada símbolo e decide, em cada eixo, o nível mais próximo."""
    i, q = simbolos_QAM16(sinal)
    b1, b2 = _bits_do_nivel(i)
    b3, b4 = _bits_do_nivel(q)
    return np.column_stack((b1, b2, b3, b4)).ravel()
