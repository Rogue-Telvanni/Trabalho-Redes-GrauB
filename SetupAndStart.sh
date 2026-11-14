#!/usr/bin/env bash
# Sobe o simulador: transmissor -> canal -> receptor (três containers Docker).
#
# Uso:
#   ./SetupAndStart.sh               automático: envia MENSAGEM com cada técnica
#                                    nos cenários ideal, awgn e rajadas; depois
#                                    envia dados aleatórios por DURACAO_S segundos
#                                    e gera os gráficos da sessão
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
#   VARRER_CANAIS   cenários da mensagem          (padrão: ideal,awgn,rajadas)
#   VARRER_EBN0_DB  Eb/N0 da mensagem             (padrão: 20,8)
#   DURACAO_S       segundos enviando dados aleatórios (padrão: 30; 0 desliga)
#   BITS_POR_QUADRO bits aleatórios por quadro    (padrão: 20000)
#   DADOS_CANAIS    cenários dos dados            (padrão: awgn,rajadas)
#   DADOS_EBN0_DB   Eb/N0 dos dados               (padrão: 0,2,4,6,8,10,12,14)
#   P_BOM_RUIM, P_RUIM_BOM, RAJADA_DB   parâmetros das rajadas
#
# Saídas: logs/sessao_<data-hora>.log, logs/quadros.jsonl, logs/canal/ (sinais
# antes e depois do ruído) e logs/graficos_<data-hora>/ (gráficos da sessão).
set -euo pipefail

cd "$(dirname "$0")"

modo="${1:-automatico}"
case "$modo" in
    -h|--help) sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
    echo "==> Transmitindo (mensagem + ${DURACAO_S:-30} s de dados)..."
    docker compose up --abort-on-container-exit --exit-code-from transmissor || status=$?
    if [[ $status -eq 0 && "${DURACAO_S:-30}" != "0" ]]; then
        echo
        echo "==> Gerando os gráficos da sessão..."
        docker compose run --rm --no-deps -T receptor python graficos_sessao.py || status=$?
    fi
fi

echo
if [[ $status -eq 0 ]]; then
    ultimo_log=$(ls -t logs/sessao_*.log 2>/dev/null | head -n 1 || true)
    echo "==> Sessão concluída."
    [[ -n "$ultimo_log" ]] && echo "    Log da sessão    : $ultimo_log"
    ultimos_graficos=$(ls -td logs/graficos_*/ 2>/dev/null | head -n 1 || true)
    [[ "$modo" == "automatico" && -n "$ultimos_graficos" ]] && echo "    Gráficos         : $ultimos_graficos"
    echo "    Dados brutos     : logs/quadros.jsonl e logs/canal/"
else
    echo "==> O transmissor terminou com erro (código $status). Veja as mensagens acima."
fi
exit $status
