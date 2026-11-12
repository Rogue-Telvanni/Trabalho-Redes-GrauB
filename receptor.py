"""Receptor: sinal ruidoso -> bits -> mensagem, com registro de cada quadro.

Para cada quadro recebido grava, em PASTA_LOGS:
    sessao_<id>.log    log legível da sessão (mensagem enviada x recebida)
    quadros.jsonl      um JSON por linha com configuração e resultados, para os gráficos
    sinais/<id>_q<n>.npz  amostras recebidas e bits decididos (formas de onda)
"""
import json
import os
import time
from pathlib import Path

import numpy as np

import canal
import mensagem
import protocolo
import ruido


def descrever_canal(info):
    if info["tipo"] == "ideal":
        return "ideal (sem ruído)"
    return f"{info['tipo']}, Eb/N0 {info['ebn0_db']:g} dB"


def main():
    porta = int(os.environ.get("RECEPTOR_PORTA", 5001))
    pasta = Path(os.environ.get("PASTA_LOGS", "logs"))
    (pasta / "sinais").mkdir(parents=True, exist_ok=True)

    def tratar(cabecalho, amostras):
        tecnica, info = cabecalho["tecnica"], cabecalho["canal"]
        recuperar = ruido.TECNICAS[tecnica][1]
        bits = recuperar(amostras)

        referencia = np.array([int(b) for b in cabecalho["referencia"]["bits"]])
        errados = np.flatnonzero(bits != referencia).tolist()
        ber = len(errados) / len(referencia)
        enviado = cabecalho["referencia"]["texto"]
        recebido = mensagem.bits_para_ascii_visivel(bits)
        teorica = canal.ber_teorica(tecnica, info["tipo"], info["ebn0_db"],
                                    info.get("p_bom_ruim", canal.P_BOM_RUIM),
                                    info.get("p_ruim_bom", canal.P_RUIM_BOM),
                                    info.get("rajada_db", canal.RAJADA_DB))
        agora = time.strftime("%Y-%m-%d %H:%M:%S")
        sessao, quadro = cabecalho["sessao"], cabecalho["quadro"]

        registro = {
            "horario": agora, "sessao": sessao, "quadro": quadro, "tecnica": tecnica,
            "amostras_por_bit": cabecalho["amostras_por_bit"], "n_bits": len(referencia),
            "canal": {k: v for k, v in info.items() if k != "posicoes_rajada"},
            "erros": len(errados), "ber": ber, "ber_teorica": teorica,
            "posicoes_erros": errados, "posicoes_rajada": info.get("posicoes_rajada", []),
            "texto_enviado": enviado, "texto_recebido": recebido,
            "mensagem_correta": len(errados) == 0,
        }
        with open(pasta / "quadros.jsonl", "a", encoding="utf-8") as arq:
            arq.write(json.dumps(registro, ensure_ascii=False) + "\n")
        np.savez_compressed(pasta / "sinais" / f"{sessao}_q{quadro:03d}.npz",
                            recebido=amostras.astype(np.float32), bits_decididos=bits,
                            bits_referencia=referencia, amostras_por_bit=cabecalho["amostras_por_bit"])

        linhas = [
            f"[{agora}] quadro {quadro}  técnica {tecnica}",
            f"  canal     : {descrever_canal(info)}, sigma {info['sigma']:.3f} V, semente {info.get('semente')}",
            f"  enviado   : {enviado}",
            f"  recebido  : {recebido}",
            f"  diferença : {mensagem.marcar_caracteres(errados, len(enviado))}",
            f"  bits errados: {len(errados)}/{len(referencia)}  BER {ber:.3e}  (teórica {teorica:.3e})",
        ]
        if errados:
            linhas.append(f"  posições dos bits errados: {errados}")
        if info.get("bits_em_rajada"):
            linhas.append(f"  bits dentro de rajadas: {info['bits_em_rajada']}")
        texto_log = "\n".join(linhas) + "\n\n"
        with open(pasta / f"sessao_{sessao}.log", "a", encoding="utf-8") as arq:
            arq.write(texto_log)
        print(texto_log, end="", flush=True)

        return {"erros": len(errados), "ber": ber, "texto_recebido": recebido,
                "canal": descrever_canal(info)}

    protocolo.servir(porta, tratar)


if __name__ == "__main__":
    main()
