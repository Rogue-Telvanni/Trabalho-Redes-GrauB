"""Receptor: sinal ruidoso -> bits -> mensagem, com registro de cada quadro.

Para cada quadro recebido grava, em PASTA_LOGS:
    sessao_<id>.log    log legível da sessão (mensagem enviada x recebida; os
                       quadros de dados aleatórios ganham uma linha curta cada)
    quadros.jsonl      um JSON por linha com configuração e resultados, para os gráficos

As formas de onda (sinal limpo e com ruído) são guardadas pelo canal, que é
quem tem os dois sinais.
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


def _gravar(pasta, sessao, registro, texto_log):
    with open(pasta / "quadros.jsonl", "a", encoding="utf-8") as arq:
        arq.write(json.dumps(registro, ensure_ascii=False) + "\n")
    with open(pasta / f"sessao_{sessao}.log", "a", encoding="utf-8") as arq:
        arq.write(texto_log)


def main():
    porta = int(os.environ.get("RECEPTOR_PORTA", 5001))
    pasta = Path(os.environ.get("PASTA_LOGS", "logs"))
    pasta.mkdir(parents=True, exist_ok=True)

    def tratar(cabecalho, amostras):
        tecnica, info = cabecalho["tecnica"], cabecalho["canal"]
        recuperar = ruido.TECNICAS[tecnica][1]
        bits = recuperar(amostras)

        referencia = np.frombuffer(cabecalho["referencia"]["bits"].encode("ascii"), np.uint8) - ord("0")
        errados = np.flatnonzero(bits != referencia).tolist()
        ber = len(errados) / len(referencia)
        teorica = canal.ber_teorica(tecnica, info["tipo"], info["ebn0_db"],
                                    info.get("p_bom_ruim", canal.P_BOM_RUIM),
                                    info.get("p_ruim_bom", canal.P_RUIM_BOM),
                                    info.get("rajada_db", canal.RAJADA_DB))
        agora = time.strftime("%Y-%m-%d %H:%M:%S")
        sessao, quadro = cabecalho["sessao"], cabecalho["quadro"]
        tipo = cabecalho.get("tipo", "mensagem")

        registro = {
            "horario": agora, "sessao": sessao, "quadro": quadro, "tipo": tipo,
            "rodada": cabecalho.get("rodada"), "tecnica": tecnica,
            "amostras_por_bit": cabecalho["amostras_por_bit"], "n_bits": len(referencia),
            "canal": {k: v for k, v in info.items() if k != "posicoes_rajada"},
            "erros": len(errados), "ber": ber, "ber_teorica": teorica,
        }

        if tipo == "dados":
            # Bits aleatórios: só a contagem importa (as posições de milhares de
            # erros por quadro deixariam o log enorme sem ajudar nos gráficos).
            _gravar(pasta, sessao, registro,
                    f"[{agora}] quadro {quadro} dados rodada {cabecalho.get('rodada')}  "
                    f"{tecnica:13s} {descrever_canal(info):24s} "
                    f"{len(errados):5d}/{len(referencia)} bits errados  BER {ber:.3e}  "
                    f"(teórica {teorica:.3e})\n")
            return {"erros": len(errados), "ber": ber, "canal": descrever_canal(info)}

        enviado = cabecalho["referencia"]["texto"]
        recebido = mensagem.bits_para_ascii_visivel(bits)
        diferenca = mensagem.marcar_caracteres(errados, len(enviado))
        registro.update({
            "posicoes_erros": errados, "posicoes_rajada": info.get("posicoes_rajada", []),
            "texto_enviado": enviado, "texto_recebido": recebido,
            "mensagem_correta": len(errados) == 0,
        })
        linhas = [
            f"[{agora}] quadro {quadro}  técnica {tecnica}",
            f"  canal     : {descrever_canal(info)}, sigma {info['sigma']:.3f} V, semente {info.get('semente')}",
            f"  enviado   : {enviado}",
            f"  recebido  : {recebido}",
            f"  diferença : {diferenca}",
            f"  bits errados: {len(errados)}/{len(referencia)}  BER {ber:.3e}  (teórica {teorica:.3e})",
        ]
        if errados:
            linhas.append(f"  posições dos bits errados: {errados}")
        if info.get("bits_em_rajada"):
            linhas.append(f"  bits dentro de rajadas: {info['bits_em_rajada']}")
        texto_log = "\n".join(linhas) + "\n\n"
        _gravar(pasta, sessao, registro, texto_log)
        print(texto_log, end="", flush=True)

        return {"erros": len(errados), "ber": ber, "texto_recebido": recebido,
                "canal": descrever_canal(info), "posicoes_erros": errados,
                "diferenca": diferenca}

    protocolo.servir(porta, tratar)


if __name__ == "__main__":
    main()
