"""Gera as figuras do relatório."""
import matplotlib

matplotlib.use("Agg")  # salva em arquivo, sem precisar abrir janela

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.transforms import blended_transform_factory

import modulador

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRADE = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
MARCADORES = ["o", "s", "^"]

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE, "font.size": 10,
    "text.color": TINTA, "axes.labelcolor": TINTA_2, "axes.edgecolor": GRADE,
    "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlelocation": "left", "axes.titlesize": 10.5, "axes.titlepad": 18,
})

TB_MS = 1000 / modulador.TAXA_BITS


def _marcar_bits(ax, bits):
    """Desenha os limites de cada bit e escreve o valor dele no topo do painel."""
    transform = blended_transform_factory(ax.transData, ax.transAxes)
    for i, bit in enumerate(bits):
        ax.axvline(i * TB_MS, color=GRADE, lw=0.8, ls="--", zorder=0)
        ax.text((i + 0.5) * TB_MS, 1.02, str(bit), transform=transform,
                ha="center", va="bottom", color=TINTA_2, fontsize=9.5)
    ax.axvline(len(bits) * TB_MS, color=GRADE, lw=0.8, ls="--", zorder=0)
    ax.set_xlim(0, len(bits) * TB_MS)


def _degraus(ax, sinal, cor=SERIES[0]):
    """Desenha um sinal constante por trechos, até o fim do último bit."""
    t = np.arange(len(sinal) + 1) / modulador.FREQ_AMOSTRAGEM * 1000
    ax.plot(t, np.append(sinal, sinal[-1]), color=cor, lw=2, drawstyle="steps-post")


def codificacao(bits, sinais, caminho):
    """sinais: lista de (título, vetor)."""
    fig, eixos = plt.subplots(len(sinais), 1, figsize=(11, 7), sharex=True)
    for ax, (titulo, sinal) in zip(eixos, sinais):
        _degraus(ax, sinal)
        _marcar_bits(ax, bits)
        ax.axhline(0, color=GRADE, lw=0.8, zorder=0)
        ax.set_ylim(-1.3, 1.3)
        ax.set_yticks([-1, 0, 1])
        ax.set_ylabel("Tensão (V)")
        ax.set_title(titulo)
    eixos[-1].set_xlabel("Tempo (ms). Linhas tracejadas: limites de cada bit")
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def modulacao(bits, referencia, sinais, parametros, caminho):
    """referencia: sinal digital; sinais: lista de (título, vetor)."""
    fig, eixos = plt.subplots(len(sinais) + 1, 1, figsize=(11, 8.5), sharex=True)
    _degraus(eixos[0], referencia, TINTA_2)
    _marcar_bits(eixos[0], bits)
    eixos[0].set_ylim(-0.2, 1.3)
    eixos[0].set_yticks([0, 1])
    eixos[0].set_ylabel("Bit")
    eixos[0].set_title("Sequência binária transmitida")
    t = modulador.eixo_tempo(len(bits)) * 1000
    for ax, (titulo, sinal) in zip(eixos[1:], sinais):
        ax.plot(t, sinal, color=SERIES[0], lw=1.1)
        _marcar_bits(ax, bits)
        ax.set_ylim(-1.3, 1.3)
        ax.set_yticks([-1, 0, 1])
        ax.set_ylabel("Tensão (V)")
        ax.set_title(titulo)
    eixos[-1].set_xlabel("Tempo (ms). Linhas tracejadas: limites de cada bit")
    fig.suptitle(parametros, x=0.01, ha="left", fontsize=10, color=TINTA_2)
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def ruido_ondas(bits, pares, sigma, caminho):
    """pares: lista de (nome, sinal limpo, sinal com ruído), 2 colunas."""
    fig, eixos = plt.subplots(3, 2, figsize=(12, 7.5), sharex=True, sharey=True)
    t = modulador.eixo_tempo(len(bits)) * 1000
    for ax, (nome, limpo, sujo) in zip(eixos.T.ravel(), pares):
        ax.plot(t, sujo, color=SERIES[1], lw=0.6, alpha=0.75, label="Recebido")
        ax.plot(t, limpo, color=SERIES[0], lw=0.9, label="Transmitido")
        _marcar_bits(ax, bits)
        ax.set_title(nome)
    eixos[0, 0].legend(loc="lower left", ncols=2, frameon=False, fontsize=9)
    for ax in eixos[:, 0]:
        ax.set_ylabel("Tensão (V)")
    for ax in eixos[-1]:
        ax.set_xlabel("Tempo (ms)")
    fig.suptitle(f"Sinais com ruído gaussiano, sigma = {sigma} V", x=0.01, ha="left",
                 fontsize=10.5, color=TINTA_2)
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def curvas_ber(grupos, caminho):
    """grupos: lista de (título, {nome: (sigmas, ber_simulada, sigmas_t, ber_teorica)})."""
    fig, eixos = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, (titulo, curvas) in zip(eixos, grupos):
        for i, (nome, (s, ber, s_t, ber_t)) in enumerate(curvas.items()):
            ax.semilogy(s_t, ber_t, color=SERIES[i], lw=2)
            visiveis = np.asarray(ber) > 0
            ax.semilogy(np.asarray(s)[visiveis], np.asarray(ber)[visiveis],
                        MARCADORES[i], color=SERIES[i], ms=8, mec=SUPERFICIE, mew=1,
                        ls="none", label=nome)
        ax.set_title(titulo, pad=8)
        ax.set_xlabel("Desvio padrão do ruído, sigma (V)")
        ax.grid(True, which="major", color="#e1e0d9", lw=0.8)
        ax.set_axisbelow(True)
        ax.legend(frameon=False, loc="lower right")
        ax.set_ylim(1e-5, 1)
    eixos[0].set_ylabel("Taxa de erro de bit (BER)")
    fig.suptitle("Marcadores: simulação. Linhas: valor teórico.", x=0.01, ha="left",
                 fontsize=10, color=TINTA_2)
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)
