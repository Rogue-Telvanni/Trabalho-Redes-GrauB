"""Teste com ruído gaussiano branco (AWGN), igual para todas as técnicas.

Todas usam amplitude de pico de 1 V e recebem ruído do mesmo desvio padrão
(sigma), ou seja, é como se passassem pelo mesmo canal.
"""
from math import erfc, sqrt

import codificador
import modulador

N = modulador.AMOSTRAS_POR_BIT

# nome -> (função que gera o sinal, função que recupera os bits, BER teórica)
#
# BER teórica = Q(d / (2 * ruído)), em que d é a distância entre os valores
# que o receptor compara para o bit 0 e para o bit 1. Ela serve para validar a
# simulação: as duas curvas têm de coincidir.


def Q(x):
    """Probabilidade de uma gaussiana padrão ultrapassar x."""
    return 0.5 * erfc(x / sqrt(2))


def ber_qam16(a):
    """BER do 16-QAM com código Gray, em função de a = d / (ruído de cada eixo).

    Cada eixo é um 4-PAM com níveis -3d, -d, +d, +3d e limiares em -2d, 0, +2d.
    Contando, nível por nível, a chance de cruzar cada limiar e quais dos 2
    bits mudam, a média dos dois bits resulta em:
        BER = 3/4 Q(a) + 1/2 Q(3a) - 1/4 Q(5a)
    (para Eb/N0 alto sobra praticamente 3/4 Q(a)).
    """
    return 0.75 * Q(a) + 0.5 * Q(3 * a) - 0.25 * Q(5 * a)


def ber_qam16_ebn0(ebn0):
    """BER do 16-QAM em AWGN, com Eb/N0 linear: a = sqrt(0,8 Eb/N0).

    Com a potência média 5 d^2, a energia por bit é 500 d^2 (100 amostras por
    bit) e o ruído de cada eixo vale 2 sigma^2 / 400, o que dá a^2 = 0,8 Eb/N0.
    """
    return ber_qam16(sqrt(0.8 * ebn0))


TECNICAS_BANDA_BASE = {
    "NRZ unipolar": (codificador.NRZunipolar, codificador.decodificar_NRZunipolar,
                     lambda s: Q(0.5 * sqrt(N) / s)),
    "NRZ polar": (codificador.NRZpolar, codificador.decodificar_NRZpolar,
                  lambda s: Q(sqrt(N) / s)),
    "Manchester": (codificador.Manchester, codificador.decodificar_Manchester,
                   lambda s: Q(sqrt(N) / s)),
}

TECNICAS_MODULACAO = {
    "ASK": (modulador.ASK, modulador.demodular_ASK,
            lambda s: Q(sqrt(N) / (2 * sqrt(2) * s))),
    "FSK": (modulador.FSK, modulador.demodular_FSK,
            lambda s: Q(sqrt(N) / (2 * s))),
    "BPSK": (modulador.BPSK, modulador.demodular_BPSK,
             lambda s: Q(sqrt(N) / (sqrt(2) * s))),
    # a = d / ruído do eixo, com ruído do eixo = sigma * sqrt(2 / (4 N))
    "16-QAM": (modulador.QAM16, modulador.demodular_QAM16,
               lambda s: ber_qam16(modulador.NIVEL_QAM * sqrt(2 * N) / s)),
}

TECNICAS = TECNICAS_BANDA_BASE | TECNICAS_MODULACAO


def adicionar_ruido(sinal, sigma, rng):
    return sinal + rng.normal(0, sigma, sinal.shape)


def taxa_erro(bits, bits_recebidos):
    """BER: fração dos bits recebidos errados."""
    return float((bits != bits_recebidos).mean())
