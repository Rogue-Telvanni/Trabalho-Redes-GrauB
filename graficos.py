"""Gera as figuras do relatório."""
import matplotlib

matplotlib.use("Agg")  # salva em arquivo, sem precisar abrir janela

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.transforms import blended_transform_factory

import modulador
import ruido

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRADE = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#7b4fd0"]
MARCADORES = ["o", "s", "^", "D"]

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE, "font.size": 10,
    "text.color": TINTA, "axes.labelcolor": TINTA_2, "axes.edgecolor": GRADE,
    "xtick.color": TINTA_2, "ytick.color": TINTA_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlelocation": "left", "axes.titlesize": 10.5, "axes.titlepad": 18,
})

TB_MS = 1000 / modulador.TAXA_BITS


ERRO = "#d03b3b"        # cor de status "crítico": bit decodificado errado
FAIXA_RAJADA = "#ecebe5"


def _marcar_bits(ax, bits, errados=()):
    """Desenha os limites de cada bit e escreve o valor dele no topo do painel.

    Os índices em `errados` aparecem em vermelho e negrito (bit que o receptor
    decodificou errado).
    """
    transform = blended_transform_factory(ax.transData, ax.transAxes)
    for i, bit in enumerate(bits):
        ax.axvline(i * TB_MS, color=GRADE, lw=0.8, ls="--", zorder=0)
        errado = i in errados
        ax.text((i + 0.5) * TB_MS, 1.02, str(bit), transform=transform,
                ha="center", va="bottom", color=ERRO if errado else TINTA_2,
                fontsize=9.5, fontweight="bold" if errado else "normal")
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
    fig, eixos = plt.subplots(len(sinais) + 1, 1, figsize=(11, 2.2 * (len(sinais) + 1) + 1), sharex=True)
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
        limite = max(1.3, 1.1 * float(np.abs(sinal).max()))  # o 16-QAM passa de 1 V
        ax.set_ylim(-limite, limite)
        ax.set_yticks([-1, 0, 1])
        ax.set_ylabel("Tensão (V)")
        ax.set_title(titulo)
    eixos[-1].set_xlabel("Tempo (ms). Linhas tracejadas: limites de cada bit")
    fig.suptitle(parametros, x=0.01, ha="left", fontsize=10, color=TINTA_2)
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def _posicoes(nomes):
    """(linha, coluna) de cada técnica: banda base na coluna 0, modulações na 1."""
    linhas = [0, 0]
    posicoes = []
    for nome in nomes:
        coluna = 0 if nome in ruido.TECNICAS_BANDA_BASE else 1
        posicoes.append((linhas[coluna], coluna))
        linhas[coluna] += 1
    return posicoes


def ruido_ondas(bits, pares, sigma, caminho):
    """pares: lista de (nome, sinal limpo, sinal com ruído), 2 colunas."""
    fig, eixos = plt.subplots(4, 2, figsize=(12, 10), sharex=True, sharey=True)
    t = modulador.eixo_tempo(len(bits)) * 1000
    posicoes = _posicoes([nome for nome, _, _ in pares])
    for ax in eixos.ravel():
        ax.set_visible(False)
    for (nome, limpo, sujo), (linha, coluna) in zip(pares, posicoes):
        ax = eixos[linha, coluna]
        ax.set_visible(True)
        ax.plot(t, sujo, color=SERIES[1], lw=0.6, alpha=0.75, label="Recebido")
        ax.plot(t, limpo, color=SERIES[0], lw=0.9, label="Transmitido")
        _marcar_bits(ax, bits)
        ax.set_title(nome)
    eixos[0, 0].legend(loc="lower left", ncols=2, frameon=False, fontsize=9)
    for ax in eixos[:, 0]:
        ax.set_ylabel("Tensão (V)")
    for coluna in range(2):
        ultimo = max((l for (l, c) in posicoes if c == coluna), default=0)
        eixos[ultimo, coluna].set_xlabel("Tempo (ms)")
        eixos[ultimo, coluna].xaxis.set_tick_params(labelbottom=True)
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


def sobreposicao_canal(paineis, titulo, caminho):
    """Sinal na entrada do canal (limpo) sobre o sinal na saída (com ruído).

    paineis: até 7 dicionários com nome, subtitulo, bits, limpo, ruidoso,
    rajada (booleano por bit) e errados (índices dos bits decodificados errados).
    Banda base na coluna 1, modulações na coluna 2.
    """
    fig, eixos = plt.subplots(4, 2, figsize=(13, 11.5), sharex=True)
    for ax in eixos.ravel():
        ax.set_visible(False)
    posicoes = _posicoes([p["nome"] for p in paineis])
    for p, (linha, coluna) in zip(paineis, posicoes):
        ax = eixos[linha, coluna]
        ax.set_visible(True)
        t = np.arange(len(p["limpo"])) / modulador.FREQ_AMOSTRAGEM * 1000
        for i in np.flatnonzero(p["rajada"]):
            ax.axvspan(i * TB_MS, (i + 1) * TB_MS, color=FAIXA_RAJADA, lw=0, zorder=0)
        ax.plot(t, p["ruidoso"], color=SERIES[1], lw=0.6, alpha=0.8, label="Saída do canal (com ruído)")
        ax.plot(t, p["limpo"], color=SERIES[0], lw=1.4, label="Entrada do canal (sinal enviado)")
        _marcar_bits(ax, p["bits"], set(p["errados"]))
        ax.axhline(0, color=GRADE, lw=0.8, zorder=0)
        ax.set_title(f"{p['nome']}   {p['subtitulo']}", fontsize=10)
        ax.set_ylabel("Tensão (V)")
    for coluna in range(2):
        ultimo = max((l for (l, c) in posicoes if c == coluna), default=0)
        eixos[ultimo, coluna].set_xlabel("Tempo (ms). Linhas tracejadas: limites de cada bit")
        eixos[ultimo, coluna].xaxis.set_tick_params(labelbottom=True)
    alcas, rotulos = eixos[0, 0].get_legend_handles_labels()
    from matplotlib.patches import Patch
    alcas += [Patch(color=FAIXA_RAJADA), plt.Line2D([], [], ls="none", marker="$1$", color=ERRO)]
    rotulos += ["Bit dentro de rajada", "Bit decodificado errado"]
    fig.legend(alcas, rotulos, loc="lower center", ncols=4, frameon=False, fontsize=9)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=10.5, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def constelacao(paineis, titulo, caminho):
    """Diagrama de constelação do 16-QAM: um painel por cenário de canal.

    paineis: dicionários com titulo, i, q (coordenadas medidas pelo receptor,
    em volts), errado (booleano por símbolo) e, opcionalmente, rotulos: lista
    de (i, q, texto) com os 4 bits de cada ponto ideal.
    """
    d = modulador.NIVEL_QAM
    niveis = np.array([-3, -1, 1, 3]) * d
    limite = 1.8
    fig, eixos = plt.subplots(1, len(paineis), figsize=(4.3 * len(paineis), 5.8),
                              sharex=True, sharey=True)
    for ax, p in zip(np.atleast_1d(eixos), paineis):
        for limiar in (-2 * d, 0, 2 * d):  # fronteiras entre os pontos vizinhos
            ax.axvline(limiar, color=GRADE, lw=0.9, ls="--", zorder=0)
            ax.axhline(limiar, color=GRADE, lw=0.9, ls="--", zorder=0)
        i, q, errado = np.asarray(p["i"]), np.asarray(p["q"]), np.asarray(p["errado"])
        ax.plot(i[~errado], q[~errado], "o", color=SERIES[0], ms=3, alpha=0.45, mew=0, zorder=2)
        ax.plot(i[errado], q[errado], "x", color=ERRO, ms=5, mew=1.2, zorder=3)
        gi, gq = np.meshgrid(niveis, niveis)
        ax.plot(gi.ravel(), gq.ravel(), "o", mfc="none", mec=TINTA, ms=9, mew=1.1, zorder=4)
        for x, y, texto in p.get("rotulos", []):
            ax.text(x, y + 0.11, texto, ha="center", va="bottom", fontsize=7.5, color=TINTA_2, zorder=5)
        ax.set_xlim(-limite, limite)
        ax.set_ylim(-limite, limite)
        ax.set_aspect("equal")
        ax.set_xticks(niveis, ["-1", "-1/3", "+1/3", "+1"])
        ax.set_yticks(niveis, ["-1", "-1/3", "+1/3", "+1"])
        ax.set_title(p["titulo"], pad=8, fontsize=10)
        ax.set_xlabel("I: amplitude do seno (V)")
    np.atleast_1d(eixos)[0].set_ylabel("Q: amplitude do cosseno (V)")
    alcas = [
        plt.Line2D([], [], ls="none", marker="o", color=SERIES[0], ms=5, mew=0),
        plt.Line2D([], [], ls="none", marker="x", color=ERRO, ms=6, mew=1.2),
        plt.Line2D([], [], ls="none", marker="o", mfc="none", mec=TINTA, ms=9, mew=1.1),
        plt.Line2D([], [], ls="--", color=GRADE, lw=0.9),
    ]
    rotulos = ["Símbolo recebido, decodificado certo", "Símbolo recebido, decodificado errado",
               "Ponto ideal da constelação", "Limiar de decisão"]
    fig.legend(alcas, rotulos, loc="lower center", ncols=4, frameon=False, fontsize=9)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=10.5, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.09, 1, 0.97))
    fig.savefig(caminho, dpi=160)
    plt.close(fig)
