"""Gráficos de uma sessão dos containers, a partir do que ficou em logs/.

    python graficos_sessao.py                          # última sessão com dados
    python graficos_sessao.py --sessao 20261113-101500

Lê:
    logs/quadros.jsonl   resultados de cada quadro, gravados pelo receptor
    logs/canal/*.npz     sinal antes e depois do ruído, guardados pelo canal

Gera em logs/graficos_<sessão>/:
    ber_por_tecnica.png, ber_awgn_tecnicas.png   curvas BER x Eb/N0, no mesmo
                                                 formato do experimentos.py
    ber_bruto.csv, ber_resumo.csv                um quadro por linha / resumo por ponto
    compromisso.csv, compromisso.md              BER x eficiência espectral
    sinal_<canal>_<Eb/N0>.png                    sinal enviado x sinal com ruído,
                                                 as seis técnicas, um cenário por figura
"""
import argparse
import json
from pathlib import Path

import numpy as np

import experimentos
import graficos
import ruido

JANELA_BITS = 16  # dois caracteres por painel, como nas figuras do main.py


def ler_registros(pasta):
    arquivo = pasta / "quadros.jsonl"
    if not arquivo.exists():
        raise SystemExit(f"{arquivo} não existe: rode o SetupAndStart.sh primeiro.")
    with open(arquivo, encoding="utf-8") as arq:
        return [json.loads(linha) for linha in arq if linha.strip()]


def escolher_sessao(registros, pedida):
    if pedida:
        return pedida
    com_dados = [r["sessao"] for r in registros if r.get("tipo") == "dados"]
    if not com_dados:
        raise SystemExit("nenhuma sessão com quadros de dados (rode com DURACAO_S > 0).")
    return max(com_dados)  # o id é a data-hora, então o maior é o mais recente


# ---------------------------------------------------------------- curvas de BER
def curvas(registros, sessao, saida, ebn0_ref):
    dados = [r for r in registros if r.get("tipo") == "dados"]
    if not dados:
        print("sessão sem quadros de dados: curvas de BER não geradas")
        return
    # Mesmo formato de linha do experimentos.py; a "semente" é a rodada do
    # transmissor (cada rodada usa bits e ruído novos).
    brutos = [{
        "canal": r["canal"]["tipo"], "tecnica": r["tecnica"], "ebn0_db": r["canal"]["ebn0_db"],
        "semente": r["rodada"], "quadro": r["quadro"], "n_bits": r["n_bits"],
        "erros": r["erros"], "ber": r["ber"], "ber_teorica": r["ber_teorica"],
        "sigma": r["canal"]["sigma"], "eb": r["canal"]["eb"],
        "bits_em_rajada": r["canal"].get("bits_em_rajada", 0),
    } for r in dados]
    experimentos.salvar_csv(saida / "ber_bruto.csv", brutos)
    resumo = experimentos.resumir(brutos)
    experimentos.salvar_csv(saida / "ber_resumo.csv", resumo)

    ebn0s = sorted({b["ebn0_db"] for b in brutos})
    rodadas = min(r["repeticoes"] for r in resumo)
    n_bits = brutos[0]["n_bits"]
    limite = 1 / min(r["repeticoes"] * r["bits_por_repeticao"] for r in resumo)
    extra = f"Containers: {rodadas} rodadas x {n_bits:,} bits por ponto.".replace(",", ".")
    experimentos.grafico_por_tecnica(resumo, ebn0s, limite, saida / "ber_por_tecnica.png", extra)
    experimentos.grafico_awgn(resumo, ebn0s, limite, saida / "ber_awgn_tecnicas.png", extra)

    if ebn0_ref in ebn0s:
        compromisso = experimentos.tabela_compromisso(resumo, ebn0_ref)
        experimentos.salvar_csv(saida / "compromisso.csv", compromisso)
        print(experimentos.salvar_compromisso_md(saida / "compromisso.md", compromisso, ebn0_ref))
    print(f"curvas: {len(dados)} quadros de dados, {rodadas} rodadas, {len(ebn0s)} valores de Eb/N0")


# ---------------------------------------------------------------- sobreposição
def _janela(n_bits, errados, rajada):
    """Trecho de JANELA_BITS bits a mostrar: onde houve erro, senão onde houve
    rajada, senão o começo. Sempre alinhado a um caractere (8 bits)."""
    if len(errados):
        inicio = errados[0] // 8 * 8
    elif rajada.any():
        inicio = np.flatnonzero(rajada)[0] // 8 * 8
    else:
        inicio = 0
    inicio = min(inicio, max(0, n_bits - JANELA_BITS))
    return inicio, min(n_bits, inicio + JANELA_BITS)


def sobreposicoes(pasta_logs, registros, sessao, saida):
    arquivos = sorted((pasta_logs / "canal").glob(f"{sessao}_q*.npz"))
    if not arquivos:
        print("sessão sem capturas do canal: figuras de sinal não geradas")
        return
    erros_por_quadro = {r["quadro"]: r.get("posicoes_erros", [])
                        for r in registros if r["sessao"] == sessao}
    grupos = {}
    for arquivo in arquivos:
        d = np.load(arquivo)
        info = json.loads(str(d["info"]))
        if info["sigma"] == 0:  # canal ideal: entrada e saída são iguais
            continue
        quadro = int(arquivo.stem.split("_q")[1])
        grupos.setdefault((info["tipo"], info["ebn0_db"]), {})[str(d["tecnica"])] = (quadro, d, info)

    for (tipo, ebn0), por_tecnica in sorted(grupos.items()):
        paineis = []
        for nome in ruido.TECNICAS:
            if nome not in por_tecnica:
                continue
            quadro, d, info = por_tecnica[nome]
            bits, apb, texto = d["bits"], int(d["amostras_por_bit"]), str(d["texto"])
            errados = np.array(erros_por_quadro.get(quadro, []), dtype=int)
            rajada = np.zeros(len(bits), dtype=bool)
            rajada[info.get("posicoes_rajada", [])] = True
            ini, fim = _janela(len(bits), errados, rajada)
            paineis.append({
                "nome": nome,
                "subtitulo": f"σ {info['sigma']:.2f} V | trecho '{texto[ini // 8:fim // 8]}' | "
                             f"{len(errados)} {'bit errado' if len(errados) == 1 else 'bits errados'} "
                             "na mensagem",
                "bits": bits[ini:fim],
                "limpo": d["limpo"][ini * apb:fim * apb],
                "ruidoso": d["ruidoso"][ini * apb:fim * apb],
                "rajada": rajada[ini:fim],
                "errados": [e - ini for e in errados if ini <= e < fim],
            })
        mensagem = str(next(iter(por_tecnica.values()))[1]["texto"])
        titulo = (f"Sessão {sessao}: canal {tipo}, Eb/N0 {ebn0:g} dB. Mensagem '{mensagem}'.\n"
                  f"Cada painel mostra {JANELA_BITS} bits: a partir do primeiro caractere com erro, "
                  "senão da primeira rajada, senão do início da mensagem.")
        caminho = saida / f"sinal_{tipo}_{ebn0:g}dB.png"
        graficos.sobreposicao_canal(paineis, titulo, caminho)
        print(f"sinal: {caminho.name}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--logs", default="logs", help="pasta de logs (padrão: logs)")
    p.add_argument("--sessao", help="id da sessão (padrão: a mais recente com dados)")
    p.add_argument("--saida", help="pasta de saída (padrão: logs/graficos_<sessão>)")
    p.add_argument("--ebn0-referencia", type=float, default=8.0, help="Eb/N0 da tabela de compromisso")
    args = p.parse_args()

    pasta_logs = Path(args.logs)
    todos = ler_registros(pasta_logs)
    sessao = escolher_sessao(todos, args.sessao)
    registros = [r for r in todos if r["sessao"] == sessao]
    if not registros:
        raise SystemExit(f"sessão {sessao} não encontrada em {pasta_logs / 'quadros.jsonl'}")
    saida = Path(args.saida) if args.saida else pasta_logs / f"graficos_{sessao}"
    saida.mkdir(parents=True, exist_ok=True)

    print(f"== Gráficos da sessão {sessao}")
    curvas(registros, sessao, saida, args.ebn0_referencia)
    sobreposicoes(pasta_logs, registros, sessao, saida)
    print(f"Gráficos em: {saida}")


if __name__ == "__main__":
    main()
