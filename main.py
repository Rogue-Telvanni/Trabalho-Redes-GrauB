from pathlib import Path

import numpy as np

import codificador
import graficos
import modulador
import ruido

PASTA = Path(__file__).parent / "graficos"
BITS_NO_GRAFICO = 16   # "OU", os 2 primeiros caracteres da mensagem
BITS_NO_TESTE = 50_000  # bits aleatórios para estimar a taxa de erro
SIGMA_ONDAS = 0.5
SIGMA_MENSAGEM = 4.0
SIGMAS = np.arange(1.0, 8.5, 0.5)


def texto_para_bits(texto):
    """UTF-8: letras acentuadas (É, Ç, Ã) ocupam 2 bytes, as demais 1."""
    return np.unpackbits(np.frombuffer(texto.encode("utf-8"), dtype=np.uint8)).astype(int)


def bits_para_texto(bits):
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes().decode("utf-8", errors="replace")


def gerar_graficos_sinais(bits):
    """Figuras das partes 1 e 2, com os mesmos bits em todas as técnicas."""
    graficos.codificacao(bits, [
        ("NRZ unipolar: bit 1 = +1 V, bit 0 = 0 V", codificador.NRZunipolar(bits)),
        ("NRZ polar: bit 1 = +1 V, bit 0 = -1 V", codificador.NRZpolar(bits)),
        ("Manchester (IEEE 802.3): bit 1 = subida (-1 V para +1 V) no meio do bit, "
         "bit 0 = descida (+1 V para -1 V)", codificador.Manchester(bits)),
    ], PASTA / "1_codificacao_banda_base.png")

    f = modulador
    parametros = (f"Taxa de bits: {f.TAXA_BITS} bit/s   |   Amostragem: {f.FREQ_AMOSTRAGEM / 1000:.0f} kHz   |   "
                  f"Amplitude: {f.AMPLITUDE:.0f} V   |   Portadora: {f.FREQ_PORTADORA / 1000:.0f} kHz (ASK, BPSK), "
                  f"{f.FREQ_FSK_0 / 1000:.0f} e {f.FREQ_FSK_1 / 1000:.0f} kHz (FSK)")
    graficos.modulacao(bits, codificador.NRZunipolar(bits), [
        ("ASK: a AMPLITUDE representa o bit (bit 1 = portadora de 1 V, bit 0 = 0 V)", f.ASK(bits)),
        ("FSK: a FREQUÊNCIA representa o bit (bit 1 = 7 kHz, bit 0 = 3 kHz)", f.FSK(bits)),
        ("BPSK: a FASE representa o bit (bit 1 = 0°, bit 0 = 180°)", f.BPSK(bits)),
    ], parametros, PASTA / "2_modulacao_digital.png")


def testar_mensagem(bits, rng):
    print(f"\nMensagem recebida com ruído, sigma = {SIGMA_MENSAGEM} V:")
    for nome, (gerar, recuperar, _) in ruido.TECNICAS.items():
        sinal = ruido.adicionar_ruido(gerar(bits), SIGMA_MENSAGEM, rng)
        recebidos = recuperar(sinal)
        erros = int((recebidos != bits).sum())
        print(f"  {nome:13s} {erros:3d} bits errados  {bits_para_texto(recebidos)}")


def testar_ber(rng):
    """Mede a BER de cada técnica para vários níveis de ruído."""
    bits = rng.integers(0, 2, BITS_NO_TESTE)
    resultado = {}
    for nome, (gerar, recuperar, _) in ruido.TECNICAS.items():
        limpo = gerar(bits)
        resultado[nome] = [
            ruido.taxa_erro(bits, recuperar(ruido.adicionar_ruido(limpo, s, rng)))
            for s in SIGMAS
        ]

    print(f"\nBER simulada ({BITS_NO_TESTE} bits por ponto):")
    print("sigma  " + "".join(f"{n:>14s}" for n in resultado))
    for i, s in enumerate(SIGMAS):
        print(f"{s:5.1f}  " + "".join(f"{resultado[n][i]:14.5f}" for n in resultado))

    sigmas_t = np.linspace(SIGMAS[0], SIGMAS[-1], 200)
    grupo = lambda tecnicas: {
        nome: (SIGMAS, resultado[nome], sigmas_t, [t[2](s) for s in sigmas_t])
        for nome, t in tecnicas.items()
    }
    graficos.curvas_ber([
        ("Codificação de banda base", grupo(ruido.TECNICAS_BANDA_BASE)),
        ("Modulação digital", grupo(ruido.TECNICAS_MODULACAO)),
    ], PASTA / "4_taxa_de_erro.png")


def main():
    mensagem = 'OUTONO É A MELHOR ESTAÇÃO'
    bit_seq = texto_para_bits(mensagem)
    bits_grafico = bit_seq[:BITS_NO_GRAFICO]
    print(f"Mensagem: {mensagem} ({len(bit_seq)} bits)")
    print(f"Bits nos gráficos: {''.join(map(str, bits_grafico))}")

    PASTA.mkdir(exist_ok=True)
    gerar_graficos_sinais(bits_grafico)

    rng = np.random.default_rng(42)  # semente fixa: resultados reproduzíveis
    pares = []
    for nome, (gerar, _, _) in ruido.TECNICAS.items():
        limpo = gerar(bits_grafico)
        pares.append((nome, limpo, ruido.adicionar_ruido(limpo, SIGMA_ONDAS, rng)))
    graficos.ruido_ondas(bits_grafico, pares, SIGMA_ONDAS, PASTA / "3_sinais_com_ruido.png")

    testar_mensagem(bit_seq, rng)
    testar_ber(rng)
    print(f"\nGráficos salvos em: {PASTA}")


if __name__ == "__main__":
    main()
