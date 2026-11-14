"""Canal ruidoso: recebe o sinal do transmissor, soma ruído e repassa ao receptor.

O ruído é controlado por Eb/N0 em dB, e não por sigma, para que todas as
técnicas sejam comparadas com a mesma energia por bit:

    Eb = potência média do sinal * amostras por bit   (energia média de um bit)
    N0 = 2 * sigma^2                                  (ruído branco amostrado)
    sigma = sqrt(Eb / (2 * 10^(Eb/N0 dB / 10)))

Cenários (CANAL_TIPO):
    ideal    nenhum ruído (teste de consistência)
    awgn     ruído gaussiano branco com o mesmo sigma em todo o sinal
    rajadas  AWGN + rajadas: um modelo de Gilbert-Elliott alterna, bit a bit,
             entre o estado BOM (sigma normal) e o RUIM (ruído RAJADA_DB mais
             forte). O Eb/N0 informado vale para o estado bom.

Pode ser usado como módulo (aplicar, ber_teorica) ou como servidor:
    python canal.py

Como servidor, o canal é o único ponto que vê o sinal ANTES e DEPOIS do ruído.
Nos quadros de mensagem ele guarda os dois em PASTA_CAPTURAS (um .npz por
quadro), e o graficos_sessao.py desenha a sobreposição limpo x ruidoso.
"""
import json
import os
from math import sqrt
from pathlib import Path

import numpy as np

import protocolo
from ruido import Q

TIPOS = ("ideal", "awgn", "rajadas")

# Parâmetros padrão das rajadas: em média 1% dos bits iniciam uma rajada, que
# dura em média 1 / 0.1 = 10 bits, com ruído 10 dB (10x em potência) mais forte.
P_BOM_RUIM = 0.01
P_RUIM_BOM = 0.1
RAJADA_DB = 10.0

# BER teórica em AWGN = Q(sqrt(K * Eb/N0)). K = 2 para sinais antipodais
# (NRZ polar, Manchester, BPSK) e K = 1 para on-off e ortogonais (NRZ
# unipolar, ASK, FSK), que precisam de 3 dB a mais para a mesma BER.
K_TEORICO = {
    "NRZ unipolar": 1, "NRZ polar": 2, "Manchester": 2,
    "ASK": 1, "FSK": 1, "BPSK": 2,
}


def sigma_para_ebn0(sinal, amostras_por_bit, ebn0_db):
    """Desvio padrão do ruído que resulta no Eb/N0 pedido, e a Eb medida no sinal."""
    eb = float(np.mean(np.square(sinal))) * amostras_por_bit
    n0 = eb / 10 ** (ebn0_db / 10)
    return sqrt(n0 / 2), eb


def estados_gilbert_elliott(n_bits, p_bom_ruim, p_ruim_bom, rng):
    """Vetor booleano com o estado do canal em cada bit (True = rajada)."""
    sorteios = rng.random(n_bits)
    estados = np.empty(n_bits, dtype=bool)
    ruim = False
    for i, u in enumerate(sorteios):
        ruim = (u >= p_ruim_bom) if ruim else (u < p_bom_ruim)
        estados[i] = ruim
    return estados


def aplicar(sinal, amostras_por_bit, tipo, ebn0_db, rng,
            p_bom_ruim=P_BOM_RUIM, p_ruim_bom=P_RUIM_BOM, rajada_db=RAJADA_DB):
    """Devolve (sinal recebido, dicionário com o que o canal fez)."""
    sinal = np.asarray(sinal, dtype=float)
    info = {"tipo": tipo, "ebn0_db": ebn0_db}
    if tipo == "ideal":
        return sinal.copy(), dict(info, ebn0_db=None, sigma=0.0)
    if tipo not in TIPOS:
        raise ValueError(f"CANAL_TIPO desconhecido: {tipo!r} (use {', '.join(TIPOS)})")

    sigma, eb = sigma_para_ebn0(sinal, amostras_por_bit, ebn0_db)
    n_bits = len(sinal) // amostras_por_bit
    sigma_por_bit = np.full(n_bits, sigma)
    info.update(sigma=sigma, eb=eb)
    if tipo == "rajadas":
        ruim = estados_gilbert_elliott(n_bits, p_bom_ruim, p_ruim_bom, rng)
        sigma_por_bit[ruim] *= 10 ** (rajada_db / 20)
        info.update(p_bom_ruim=p_bom_ruim, p_ruim_bom=p_ruim_bom, rajada_db=rajada_db,
                    bits_em_rajada=int(ruim.sum()),
                    posicoes_rajada=np.flatnonzero(ruim).tolist())
    ruido = rng.standard_normal(len(sinal)) * np.repeat(sigma_por_bit, amostras_por_bit)
    return sinal + ruido, info


def ber_teorica(tecnica, tipo, ebn0_db, p_bom_ruim=P_BOM_RUIM, p_ruim_bom=P_RUIM_BOM,
                rajada_db=RAJADA_DB):
    """BER esperada. Nas rajadas é a média ponderada pelo tempo em cada estado."""
    if tipo == "ideal":
        return 0.0
    k = K_TEORICO[tecnica]
    ebn0 = 10 ** (ebn0_db / 10)
    bom = Q(sqrt(k * ebn0))
    if tipo == "awgn":
        return bom
    ruim = Q(sqrt(k * ebn0 / 10 ** (rajada_db / 10)))
    fracao_ruim = p_bom_ruim / (p_bom_ruim + p_ruim_bom)
    return (1 - fracao_ruim) * bom + fracao_ruim * ruim


def capturar(pasta, cabecalho, limpo, recebido, info):
    """Guarda o sinal antes e depois do ruído, com o que é preciso para desenhá-los."""
    np.savez_compressed(
        pasta / f"{cabecalho['sessao']}_q{cabecalho['quadro']:04d}.npz",
        limpo=np.asarray(limpo, dtype=np.float32),
        ruidoso=np.asarray(recebido, dtype=np.float32),
        bits=np.frombuffer(cabecalho["referencia"]["bits"].encode("ascii"), np.uint8) - ord("0"),
        amostras_por_bit=cabecalho["amostras_por_bit"],
        tecnica=cabecalho["tecnica"],
        texto=cabecalho["referencia"]["texto"] or "",
        info=json.dumps(info),
    )


def main():
    porta = int(os.environ.get("CANAL_PORTA", 5000))
    destino = (os.environ.get("RECEPTOR_HOST", "localhost"), int(os.environ.get("RECEPTOR_PORTA", 5001)))
    padrao = {
        "canal_tipo": os.environ.get("CANAL_TIPO", "awgn"),
        "ebn0_db": float(os.environ.get("EBN0_DB", 8)),
        "p_bom_ruim": float(os.environ.get("P_BOM_RUIM", P_BOM_RUIM)),
        "p_ruim_bom": float(os.environ.get("P_RUIM_BOM", P_RUIM_BOM)),
        "rajada_db": float(os.environ.get("RAJADA_DB", RAJADA_DB)),
    }
    semente = int(os.environ.get("SEMENTE", 42))
    capturas = os.environ.get("PASTA_CAPTURAS")
    if capturas:
        capturas = Path(capturas)
        capturas.mkdir(parents=True, exist_ok=True)
    print(f"canal padrão: {padrao}, semente {semente}, repassando para {destino}, "
          f"capturas em {capturas or '(desligado)'}", flush=True)

    def tratar(cabecalho, amostras):
        # O transmissor pode pedir outro Eb/N0 ou cenário para este quadro (varredura).
        config = padrao | (cabecalho.get("controle") or {})
        # Semente própria por quadro: repetir a sessão reproduz exatamente o mesmo ruído.
        rng = np.random.default_rng([semente, cabecalho["quadro"]])
        recebido, info = aplicar(amostras, cabecalho["amostras_por_bit"], config["canal_tipo"],
                                 config["ebn0_db"], rng, config["p_bom_ruim"],
                                 config["p_ruim_bom"], config["rajada_db"])
        info["semente"] = [semente, cabecalho["quadro"]]
        if cabecalho.get("tipo", "mensagem") == "mensagem":
            ebn0 = "-" if info["ebn0_db"] is None else f"{info['ebn0_db']} dB"
            print(f"quadro {cabecalho['quadro']:3d} {cabecalho['tecnica']:13s} canal {info['tipo']:7s} "
                  f"Eb/N0 {ebn0:>8s} sigma {info['sigma']:.3f} V", flush=True)
            if capturas:
                capturar(capturas, cabecalho, amostras, recebido, info)
        with protocolo.conectar(*destino) as sock:
            protocolo.enviar_quadro(sock, dict(cabecalho, canal=info), recebido)
            return protocolo.receber_json(sock)

    protocolo.servir(porta, tratar)


if __name__ == "__main__":
    main()
