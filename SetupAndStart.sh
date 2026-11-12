#!/usr/bin/env bash
# Sobe o simulador: transmissor -> canal -> receptor (três containers Docker).
#
# Uso:
#   ./SetupAndStart.sh
#   MENSAGEM="OLA MUNDO" CANAL_TIPO=rajadas EBN0_DB=4 ./SetupAndStart.sh
#   VARRER_EBN0_DB=0,2,4,6,8,10,12,14 VARRER_CANAIS=awgn,rajadas ./SetupAndStart.sh
#
# Variáveis (todas opcionais):
#   MENSAGEM        frase em ASCII                (padrão: REDES DE COMPUTADORES - UNISINOS 2026)
#   TECNICAS        "todas" ou lista com vírgula  (ex.: BPSK,Manchester)
#   CANAL_TIPO      ideal | awgn | rajadas        (padrão: awgn)
#   EBN0_DB         Eb/N0 do canal em dB          (padrão: 8)
#   SEMENTE         semente do ruído              (padrão: 42)
#   VARRER_EBN0_DB  lista de Eb/N0 para varrer numa sessão
#   VARRER_CANAIS   lista de cenários para varrer numa sessão
#   P_BOM_RUIM, P_RUIM_BOM, RAJADA_DB   parâmetros das rajadas
set -euo pipefail

cd "$(dirname "$0")"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

erro() { echo "ERRO: $*" >&2; exit 1; }

# 1. Pré-requisitos
command -v docker >/dev/null || erro "docker não encontrado. Instale o Docker Engine."
docker compose version >/dev/null 2>&1 || erro "plugin 'docker compose' não encontrado."
docker info >/dev/null 2>&1 || erro "o daemon do Docker não está rodando (tente: sudo systemctl start docker)."

if grep -qs '"credsStore"' "$HOME/.docker/config.json"; then
    echo "AVISO: ~/.docker/config.json tem \"credsStore\". Se o Docker pedir a senha da chave PGP"
    echo "       durante o build, remova essa linha (veja as instruções no README)."
fi

# 2. Pasta de logs com o usuário atual (o receptor roda com o mesmo UID/GID)
export UID GID="$(id -g)"
mkdir -p logs

# 3. Build da imagem (uma só para os três containers)
echo "==> Construindo a imagem..."
docker compose build

# 4. Sobe tudo e espera o transmissor terminar; depois derruba canal e receptor
echo "==> Transmitindo (canal: ${CANAL_TIPO:-awgn}, Eb/N0: ${EBN0_DB:-8} dB)..."
trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
status=0
docker compose up --abort-on-container-exit --exit-code-from transmissor || status=$?

echo
if [[ $status -eq 0 ]]; then
    ultimo_log=$(ls -t logs/sessao_*.log 2>/dev/null | head -n 1 || true)
    echo "==> Sessão concluída."
    [[ -n "$ultimo_log" ]] && echo "    Log da sessão : $ultimo_log"
    echo "    Dados p/ gráficos: logs/quadros.jsonl e logs/sinais/"
else
    echo "==> O transmissor terminou com erro (código $status). Veja as mensagens acima."
fi
exit $status
