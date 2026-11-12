#!/usr/bin/env bash
# Sobe o simulador: transmissor -> canal -> receptor (três containers Docker).
#
# Uso:
#   ./SetupAndStart.sh               automático: envia MENSAGEM com cada técnica
#                                    nos cenários ideal, awgn e rajadas, e desliga
#   ./SetupAndStart.sh interativo    deixa canal e receptor ligados e abre o
#                                    transmissor no terminal: cada linha digitada
#                                    é transmitida (/ajuda mostra os comandos)
#
#   MENSAGEM="OLA MUNDO" EBN0_DB=4 ./SetupAndStart.sh
#   VARRER_EBN0_DB=0,4,8,12 VARRER_CANAIS=awgn ./SetupAndStart.sh
#
# Variáveis (todas opcionais):
#   MENSAGEM        frase em ASCII                (padrão: REDES DE COMPUTADORES - UNISINOS 2026)
#   TECNICAS        "todas" ou lista com vírgula  (ex.: BPSK,Manchester)
#   CANAL_TIPO      cenário padrão do canal: ideal | awgn | rajadas (padrão: awgn)
#   EBN0_DB         Eb/N0 padrão do canal em dB   (padrão: 8)
#   SEMENTE         semente do ruído              (padrão: 42)
#   VARRER_CANAIS   cenários do modo automático   (padrão: ideal,awgn,rajadas)
#   VARRER_EBN0_DB  lista de Eb/N0 do modo automático (padrão: o EBN0_DB do canal)
#   P_BOM_RUIM, P_RUIM_BOM, RAJADA_DB   parâmetros das rajadas
#
# Logs: logs/sessao_<data-hora>.log, logs/quadros.jsonl e logs/sinais/.
set -euo pipefail

cd "$(dirname "$0")"

modo="${1:-automatico}"
case "$modo" in
    -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    automatico|interativo) ;;
    *) echo "modo desconhecido: $modo (use: automatico | interativo | --help)" >&2; exit 2 ;;
esac

erro() { echo "ERRO: $*" >&2; exit 1; }

# 1. Pré-requisitos
command -v docker >/dev/null || erro "docker não encontrado. Instale o Docker Engine."
docker compose version >/dev/null 2>&1 || erro "plugin 'docker compose' não encontrado."
docker info >/dev/null 2>&1 || erro "o daemon do Docker não está rodando (tente: sudo systemctl start docker)."

if grep -qs '"credsStore"' "$HOME/.docker/config.json"; then
    echo "AVISO: ~/.docker/config.json tem \"credsStore\". Se o Docker pedir a senha da chave PGP"
    echo "       durante o build, remova essa linha."
fi

# 2. Pasta de logs com o usuário atual (os containers rodam com o mesmo UID/GID)
export UID GID="$(id -g)"
mkdir -p logs

# 3. Build da imagem (uma só para os três containers)
echo "==> Construindo a imagem..."
docker compose build --quiet

# Ao sair (fim normal, erro ou Ctrl+C), desliga tudo.
trap 'echo "==> Desligando os containers..."; docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT

status=0
if [[ "$modo" == "interativo" ]]; then
    echo "==> Ligando canal (padrão: ${CANAL_TIPO:-awgn}, Eb/N0 ${EBN0_DB:-8} dB) e receptor..."
    docker compose up -d canal receptor
    echo "    Para ver o log detalhado do receptor, em outro terminal:"
    echo "    docker compose logs -f receptor"
    echo
    docker compose run --rm transmissor python transmissor.py --interativo || status=$?
else
    echo "==> Transmitindo..."
    docker compose up --abort-on-container-exit --exit-code-from transmissor || status=$?
fi

echo
if [[ $status -eq 0 ]]; then
    ultimo_log=$(ls -t logs/sessao_*.log 2>/dev/null | head -n 1 || true)
    echo "==> Sessão concluída."
    [[ -n "$ultimo_log" ]] && echo "    Log da sessão    : $ultimo_log"
    echo "    Dados p/ gráficos: logs/quadros.jsonl e logs/sinais/"
else
    echo "==> O transmissor terminou com erro (código $status). Veja as mensagens acima."
fi
exit $status
