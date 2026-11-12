"""Plano experimental do trabalho: curvas BER x Eb/N0 em AWGN e com rajadas.

Roda localmente, sem a rede, usando EXATAMENTE as mesmas funções dos
containers (ruido.TECNICAS para gerar/recuperar, canal.aplicar para o ruído).
Assim os milhões de bits do experimento não precisam passar pelo socket.

    python experimentos.py                      # 8 Eb/N0 x 100.000 bits x 5 sementes
    python experimentos.py --bits 20000         # versão rápida para testar

Gera em resultados/:
    config.json        parâmetros, versões e data (reprodutibilidade)
    consistencia.txt   teste de consistência: mensagem em canal ideal e Eb/N0 alto
    ber_bruto.csv      uma linha por (canal, técnica, Eb/N0, semente)
    ber_resumo.csv     média, desvio, IC 95% e BER teórica por ponto
    compromisso.csv    tabela BER x eficiência espectral (também em .md)
    ber_por_tecnica.png    AWGN x rajadas, um painel por técnica
    ber_awgn_tecnicas.png  as seis técnicas juntas em AWGN
"""
import argparse
import csv
import json
import platform
import statistics
import time
from math import sqrt
from pathlib import Path

import matplotlib
import numpy as np

import canal
import graficos  # noqa: F401  (aplica o estilo comum das figuras)
import mensagem
import modulador
import ruido

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CANAIS = ("awgn", "rajadas")
MENSAGEM_CONSISTENCIA = "REDES DE COMPUTADORES - UNISINOS 2026"

# t de Student bicaudal 95% para n-1 graus de liberdade (n = nº de sementes)
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
       8: 2.306, 9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086, 30: 2.042}

# Paleta categórica (ordem fixa) e marcadores: cada série tem cor E marcador.
CORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MARCADORES = ["o", "s", "^", "D", "v", "P"]
TINTA_2, GRADE, SUPERFICIE = "#52514e", "#e1e0d9", "#fcfcfb"


def t95(n):
    gl = n - 1
    return T95.get(gl) or T95[max(k for k in T95 if k <= gl)]


# ---------------------------------------------------------------- eficiência
def largura_de_banda(tecnica):
    """Banda nominal até o primeiro nulo do espectro, em Hz (Rb = taxa de bits).

    NRZ: pulso retangular de duração Tb -> primeiro nulo em Rb.
    Manchester: duas metades de Tb/2 -> primeiro nulo em 2 Rb.
    ASK e BPSK: o espectro NRZ deslocado para a portadora ocupa +-Rb -> 2 Rb.
    FSK: as duas portadoras ficam |f1 - f0| afastadas, cada uma com +-Rb.
    """
    rb = modulador.TAXA_BITS
    return {
        "NRZ unipolar": rb, "NRZ polar": rb, "Manchester": 2 * rb,
        "ASK": 2 * rb, "BPSK": 2 * rb,
        "FSK": abs(modulador.FREQ_FSK_1 - modulador.FREQ_FSK_0) + 2 * rb,
    }[tecnica]


def ebn0_necessario(tecnica, ber_alvo, tipo="awgn"):
    """Inverte a BER teórica por bissecção: menor Eb/N0 (dB) que atinge ber_alvo."""
    baixo, alto = -10.0, 40.0
    for _ in range(60):
        meio = (baixo + alto) / 2
        if canal.ber_teorica(tecnica, tipo, meio) > ber_alvo:
            baixo = meio
        else:
            alto = meio
    return alto


def ebn0_simulado_para(pontos, ber_alvo):
    """Interpola (em log10 da BER) o Eb/N0 em que a curva média cruza ber_alvo."""
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:]):
        if y0 >= ber_alvo > y1 > 0:
            f = (np.log10(y0) - np.log10(ber_alvo)) / (np.log10(y0) - np.log10(y1))
            return x0 + f * (x1 - x0)
    return None


# ---------------------------------------------------------------- execução
def consistencia(saida):
    """Mensagem ASCII em canal ideal e com Eb/N0 = 30 dB: tem de voltar idêntica."""
    bits = mensagem.ascii_para_bits(MENSAGEM_CONSISTENCIA)
    linhas = [f"Mensagem: '{MENSAGEM_CONSISTENCIA}' ({len(bits)} bits)", ""]
    tudo_ok = True
    for tipo, ebn0 in (("ideal", None), ("awgn", 30.0)):
        for i, (nome, (gerar, recuperar, _)) in enumerate(ruido.TECNICAS.items()):
            rng = np.random.default_rng([999, i])
            recebido, info = canal.aplicar(gerar(bits), ruido.N, tipo, ebn0, rng)
            bits_rx = recuperar(recebido)
            erros = int((bits_rx != bits).sum())
            texto = mensagem.bits_para_ascii_visivel(bits_rx)
            ok = erros == 0 and texto == MENSAGEM_CONSISTENCIA
            tudo_ok &= ok
            canal_txt = "ideal" if tipo == "ideal" else f"AWGN {ebn0:g} dB"
            linhas.append(f"{'OK  ' if ok else 'FALHA'} {canal_txt:12s} {nome:13s} "
                          f"{erros} bits errados  '{texto}'")
    linhas += ["", "Resultado: " + ("mensagem recuperada sem erros em todos os casos."
                                    if tudo_ok else "HÁ DIVERGÊNCIAS, ver linhas FALHA.")]
    (saida / "consistencia.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas))
    return tudo_ok


def varredura(ebn0s, n_bits, sementes):
    brutos = []
    total = len(sementes) * len(ruido.TECNICAS) * len(CANAIS) * len(ebn0s)
    feito, inicio = 0, time.time()
    for s in sementes:
        bits = np.random.default_rng([s, 0]).integers(0, 2, n_bits)
        for t_i, (nome, (gerar, recuperar, _)) in enumerate(ruido.TECNICAS.items()):
            limpo = gerar(bits)
            for c_i, tipo in enumerate(CANAIS):
                for e_i, ebn0 in enumerate(ebn0s):
                    rng = np.random.default_rng([s, 1 + t_i, c_i, e_i])
                    recebido, info = canal.aplicar(limpo, ruido.N, tipo, ebn0, rng)
                    erros = int((recuperar(recebido) != bits).sum())
                    brutos.append({
                        "canal": tipo, "tecnica": nome, "ebn0_db": ebn0, "semente": s,
                        "n_bits": n_bits, "erros": erros, "ber": erros / n_bits,
                        "ber_teorica": canal.ber_teorica(nome, tipo, ebn0),
                        "sigma": info["sigma"], "eb": info["eb"],
                        "bits_em_rajada": info.get("bits_em_rajada", 0),
                    })
                    feito += 1
            print(f"\r  {feito}/{total} pontos  ({time.time() - inicio:.0f} s)", end="", flush=True)
    print()
    return brutos


def resumir(brutos):
    grupos = {}
    for r in brutos:
        grupos.setdefault((r["canal"], r["tecnica"], r["ebn0_db"]), []).append(r)
    resumo = []
    for (tipo, nome, ebn0), rs in grupos.items():
        bers = [r["ber"] for r in rs]
        media = statistics.fmean(bers)
        desvio = statistics.stdev(bers) if len(bers) > 1 else 0.0
        ic = t95(len(bers)) * desvio / sqrt(len(bers)) if len(bers) > 1 else 0.0
        resumo.append({
            "canal": tipo, "tecnica": nome, "ebn0_db": ebn0, "repeticoes": len(bers),
            "bits_por_repeticao": rs[0]["n_bits"], "erros_total": sum(r["erros"] for r in rs),
            "ber_media": media, "ber_desvio": desvio, "ber_ic95": ic,
            "ber_min": min(bers), "ber_max": max(bers), "ber_teorica": rs[0]["ber_teorica"],
        })
    return resumo


def tabela_compromisso(resumo, ebn0_ref):
    linhas = []
    for nome in ruido.TECNICAS:
        b = largura_de_banda(nome)
        curva = {c: sorted((r["ebn0_db"], r["ber_media"]) for r in resumo
                           if r["tecnica"] == nome and r["canal"] == c) for c in CANAIS}
        no_ref = {c: next((y for x, y in curva[c] if x == ebn0_ref), None) for c in CANAIS}
        sim = ebn0_simulado_para(curva["awgn"], 1e-3)
        linhas.append({
            "tecnica": nome, "bits_por_simbolo": 1, "banda_hz": b,
            "eficiencia_bit_s_hz": modulador.TAXA_BITS / b,
            "ebn0_teorico_ber_1e-3_db": round(ebn0_necessario(nome, 1e-3), 2),
            "ebn0_simulado_ber_1e-3_db": None if sim is None else round(sim, 2),
            "ebn0_teorico_ber_1e-5_db": round(ebn0_necessario(nome, 1e-5), 2),
            f"ber_awgn_{ebn0_ref:g}db": no_ref["awgn"],
            f"ber_rajadas_{ebn0_ref:g}db": no_ref["rajadas"],
        })
    return linhas


# ---------------------------------------------------------------- arquivos
def salvar_csv(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as arq:
        escritor = csv.DictWriter(arq, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def salvar_compromisso_md(caminho, linhas, ebn0_ref):
    def fmt(v):
        return "-" if v is None else (f"{v:.2e}" if isinstance(v, float) and v < 0.01 else f"{v:.3g}")
    cab = ["Técnica", "Banda (Hz)", "η (bit/s/Hz)", "Eb/N0 p/ BER 1e-3 teórico (dB)",
           "simulado (dB)", "Eb/N0 p/ BER 1e-5 (dB)", f"BER AWGN {ebn0_ref:g} dB",
           f"BER rajadas {ebn0_ref:g} dB"]
    corpo = [[r["tecnica"], f"{r['banda_hz']:.0f}", f"{r['eficiencia_bit_s_hz']:.3f}",
              fmt(r["ebn0_teorico_ber_1e-3_db"]), fmt(r["ebn0_simulado_ber_1e-3_db"]),
              fmt(r["ebn0_teorico_ber_1e-5_db"]), fmt(r[f"ber_awgn_{ebn0_ref:g}db"]),
              fmt(r[f"ber_rajadas_{ebn0_ref:g}db"])] for r in linhas]
    texto = "| " + " | ".join(cab) + " |\n|" + "---|" * len(cab) + "\n"
    texto += "".join("| " + " | ".join(l) + " |\n" for l in corpo)
    texto += (f"\nBanda nominal até o primeiro nulo, taxa de bits {modulador.TAXA_BITS} bit/s. "
              "Todas as técnicas levam 1 bit por símbolo.\n")
    caminho.write_text(texto, encoding="utf-8")
    return texto


# ---------------------------------------------------------------- gráficos
def _serie(resumo, nome, tipo):
    rs = sorted((r for r in resumo if r["tecnica"] == nome and r["canal"] == tipo),
                key=lambda r: r["ebn0_db"])
    x = np.array([r["ebn0_db"] for r in rs])
    y = np.array([r["ber_media"] for r in rs])
    ic = np.array([r["ber_ic95"] for r in rs])
    return x, y, ic


def _desenhar(ax, x, y, ic, cor, marcador, rotulo):
    """Pontos com BER média > 0 e barras do IC 95% (cortadas acima de zero no log)."""
    vis = y > 0
    baixo = np.minimum(ic[vis], y[vis] * 0.95)  # o log não mostra valores <= 0
    ax.errorbar(x[vis], y[vis], yerr=[baixo, ic[vis]], fmt=marcador, color=cor, ms=7,
                mec=SUPERFICIE, mew=1, elinewidth=1.2, capsize=3, ls="none", label=rotulo)


def _eixos(ax, limite):
    ax.set_yscale("log")
    ax.set_ylim(max(limite / 3, 1e-7), 0.6)
    ax.grid(True, which="major", color=GRADE, lw=0.8)
    ax.set_axisbelow(True)
    ax.axhline(limite, color=TINTA_2, lw=0.8, ls=":")


def _rotulo_limite(ax, ebn0s, limite):
    # Embaixo da linha, à esquerda: Eb/N0 baixo nunca tem BER tão pequena.
    ax.text(min(ebn0s), limite * 0.85, "limite de medição (1 erro no total)", fontsize=8,
            color=TINTA_2, ha="left", va="top")


def grafico_por_tecnica(resumo, ebn0s, limite, caminho, legenda_extra):
    fig, eixos = plt.subplots(2, 3, figsize=(13, 8), sharex=True, sharey=True)
    xt = np.linspace(min(ebn0s), max(ebn0s), 200)
    for ax, nome in zip(eixos.ravel(), ruido.TECNICAS):
        for i, tipo in enumerate(CANAIS):
            rotulo = "AWGN" if tipo == "awgn" else "Rajadas"
            ax.plot(xt, [canal.ber_teorica(nome, tipo, v) for v in xt], color=CORES[i],
                    lw=1.5, ls="--", alpha=0.9)
            _desenhar(ax, *_serie(resumo, nome, tipo), CORES[i], MARCADORES[i], rotulo)
        _eixos(ax, limite)
        ax.set_title(nome, pad=8)
    for ax in eixos[-1]:
        ax.set_xlabel("Eb/N0 (dB)")
    for ax in eixos[:, 0]:
        ax.set_ylabel("BER")
    eixos[0, 0].legend(frameon=False, loc="upper right")
    for ax in eixos.ravel():
        _rotulo_limite(ax, ebn0s, limite)
    fig.suptitle("BER x Eb/N0: AWGN e rajadas. Marcadores: média simulada com IC 95%. "
                 f"Tracejado: teoria. {legenda_extra}", x=0.01, ha="left", fontsize=10, color=TINTA_2)
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


def grafico_awgn(resumo, ebn0s, limite, caminho, legenda_extra):
    fig, ax = plt.subplots(figsize=(9, 6))
    xt = np.linspace(min(ebn0s), max(ebn0s), 200)
    for tecnica in ("BPSK", "ASK"):
        ax.plot(xt, [canal.ber_teorica(tecnica, "awgn", v) for v in xt], color=TINTA_2, lw=1.2, ls="--")
    # Canto superior direito: nunca tem dados (BER alta só ocorre com Eb/N0 baixo).
    ax.text(0.98, 0.97, "Tracejado: teoria\n"
            "curva inferior, antipodal (NRZ polar, Manchester, BPSK): Q(√(2Eb/N0))\n"
            "curva superior, on-off/ortogonal (NRZ unipolar, ASK, FSK): Q(√(Eb/N0))",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=TINTA_2,
            linespacing=1.5)
    for i, nome in enumerate(ruido.TECNICAS):
        _desenhar(ax, *_serie(resumo, nome, "awgn"), CORES[i], MARCADORES[i], nome)
    _eixos(ax, limite)
    _rotulo_limite(ax, ebn0s, limite)
    ax.set_xlabel("Eb/N0 (dB)")
    ax.set_ylabel("BER")
    ax.legend(frameon=False, loc="center left", ncols=2)
    ax.set_title(f"Seis técnicas em AWGN: dois grupos separados por 3 dB. {legenda_extra}", pad=8)
    fig.tight_layout()
    fig.savefig(caminho, dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bits", type=int, default=100_000, help="bits por ponto e repetição")
    p.add_argument("--sementes", type=int, default=5, help="número de repetições")
    p.add_argument("--ebn0", default="0,2,4,6,8,10,12,14", help="valores de Eb/N0 em dB")
    p.add_argument("--ebn0-referencia", type=float, default=8.0, help="Eb/N0 da tabela de compromisso")
    p.add_argument("--saida", default="resultados", help="pasta de saída")
    args = p.parse_args()

    ebn0s = [float(v) for v in args.ebn0.split(",")]
    sementes = list(range(args.sementes))
    saida = Path(__file__).parent / args.saida
    saida.mkdir(exist_ok=True)

    config = {
        "data": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bits_por_repeticao": args.bits, "sementes": sementes, "ebn0_db": ebn0s,
        "canais": list(CANAIS), "tecnicas": list(ruido.TECNICAS),
        "amostras_por_bit": ruido.N, "taxa_bits": modulador.TAXA_BITS,
        "freq_amostragem": modulador.FREQ_AMOSTRAGEM, "freq_portadora": modulador.FREQ_PORTADORA,
        "freq_fsk": [modulador.FREQ_FSK_0, modulador.FREQ_FSK_1], "amplitude": modulador.AMPLITUDE,
        "rajadas": {"p_bom_ruim": canal.P_BOM_RUIM, "p_ruim_bom": canal.P_RUIM_BOM,
                    "rajada_db": canal.RAJADA_DB},
        "semente_ruido": "default_rng([semente, 1 + índice técnica, índice canal, índice Eb/N0])",
        "semente_bits": "default_rng([semente, 0])",
        "python": platform.python_version(), "numpy": np.__version__,
        "matplotlib": matplotlib.__version__,
    }
    (saida / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print("== Teste de consistência")
    consistencia(saida)

    print(f"\n== Varredura: {len(ebn0s)} Eb/N0 x {args.bits} bits x {len(sementes)} sementes "
          f"x {len(ruido.TECNICAS)} técnicas x {len(CANAIS)} canais")
    brutos = varredura(ebn0s, args.bits, sementes)
    salvar_csv(saida / "ber_bruto.csv", brutos)
    resumo = resumir(brutos)
    salvar_csv(saida / "ber_resumo.csv", resumo)

    compromisso = tabela_compromisso(resumo, args.ebn0_referencia)
    salvar_csv(saida / "compromisso.csv", compromisso)
    print("\n== Compromisso BER x eficiência espectral")
    print(salvar_compromisso_md(saida / "compromisso.md", compromisso, args.ebn0_referencia))

    limite = 1 / (args.bits * len(sementes))
    extra = f"{args.bits:,} bits x {len(sementes)} sementes por ponto.".replace(",", ".")
    grafico_por_tecnica(resumo, ebn0s, limite, saida / "ber_por_tecnica.png", extra)
    grafico_awgn(resumo, ebn0s, limite, saida / "ber_awgn_tecnicas.png", extra)
    print(f"Resultados em: {saida}")


if __name__ == "__main__":
    main()
