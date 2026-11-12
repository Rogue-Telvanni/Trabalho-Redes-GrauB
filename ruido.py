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
}

TECNICAS = TECNICAS_BANDA_BASE | TECNICAS_MODULACAO


def adicionar_ruido(sinal, sigma, rng):
    return sinal + rng.normal(0, sigma, sinal.shape)


def taxa_erro(bits, bits_recebidos):
    """BER: fração dos bits recebidos errados."""
    return float((bits != bits_recebidos).mean())
