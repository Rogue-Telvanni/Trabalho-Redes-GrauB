"""Validação do código. Rode com: python testes.py"""
import numpy as np

import codificador as c
import main
import modulador as m
import ruido


def teste_conversao_texto():
    bits = main.texto_para_bits("OUTONO É A MELHOR ESTAÇÃO")
    assert len(bits) == 224
    assert main.bits_para_texto(bits) == "OUTONO É A MELHOR ESTAÇÃO"
    assert "".join(map(str, bits[:8])) == "01001111"  # 'O' = 0x4F


def teste_niveis_conhecidos():
    bits = [1, 0, 1, 1]
    assert c.NRZunipolar(bits, 2).tolist() == [1, 1, 0, 0, 1, 1, 1, 1]
    assert c.NRZpolar(bits, 2).tolist() == [1, 1, -1, -1, 1, 1, 1, 1]
    assert c.Manchester(bits, 2).tolist() == [-1, 1, 1, -1, -1, 1, -1, 1]


def teste_manchester_tem_transicao_em_todo_bit():
    bits = np.random.default_rng(1).integers(0, 2, 1000)
    sinal = c.Manchester(bits, 100)
    assert np.all(sinal[49::100] != sinal[50::100])
    assert sinal.mean() == 0


def teste_recuperacao_sem_ruido():
    bits = np.random.default_rng(2).integers(0, 2, 2000)
    for nome, (gerar, recuperar, _) in ruido.TECNICAS.items():
        assert np.array_equal(recuperar(gerar(bits)), bits), nome


def frequencia_dominante(sinal):
    espectro = np.abs(np.fft.rfft(sinal))
    return np.fft.rfftfreq(len(sinal), 1 / m.FREQ_AMOSTRAGEM)[espectro.argmax()]


def teste_parametro_de_cada_modulacao():
    uns, zeros = [1] * 20, [0] * 20
    assert np.allclose(m.ASK(zeros), 0)                            # ASK: amplitude
    assert np.isclose(m.ASK(uns).max(), m.AMPLITUDE, atol=0.01)
    assert frequencia_dominante(m.FSK(uns)) == m.FREQ_FSK_1        # FSK: frequência
    assert frequencia_dominante(m.FSK(zeros)) == m.FREQ_FSK_0
    assert np.allclose(m.BPSK(zeros), -m.BPSK(uns))                # BPSK: fase de 180°


def teste_ber_simulada_igual_a_teorica():
    """Num ponto de BER mensurável, a simulação tem de bater com a teoria."""
    rng = np.random.default_rng(3)
    bits = rng.integers(0, 2, 200_000)
    for nome, (gerar, recuperar, teorica) in ruido.TECNICAS.items():
        sigma = 4.0
        simulada = ruido.taxa_erro(bits, recuperar(ruido.adicionar_ruido(gerar(bits), sigma, rng)))
        esperada = teorica(sigma)
        print(f"  {nome:13s} simulada {simulada:.5f}   teórica {esperada:.5f}")
        assert abs(simulada - esperada) / esperada < 0.10, nome


if __name__ == "__main__":
    for nome, teste in list(globals().items()):
        if nome.startswith("teste_"):
            print(nome)
            teste()
    print("\nTodos os testes passaram.")
