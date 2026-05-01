#!/bin/bash

# Script para automatizar os testes usando wrk
# Uso: ./run_benchmark.sh <url_do_servidor> <nome_do_teste>

URL=$1
TEST_NAME=$2

if [ -z "$URL" ] || [ -z "$TEST_NAME" ]; then
    echo "Uso: $0 <url> <nome_do_teste>"
    echo "Exemplo: $0 http://localhost:8080 multithread_ethernet"
    exit 1
fi

# Cenários de carga definidos no PDF
CONEXOES=(100 500 1000 5000)
DURACAO="60s"
THREADS=12 # Número de threads do wrk para gerar carga

echo "Iniciando Benchmark: $TEST_NAME"
echo "--------------------------------------"

for C in "${CONEXOES[@]}"
do
    echo "Testando com $C conexões simultâneas..."
    # Executa o wrk e salva o resultado em um arquivo
    # O parâmetro --latency é crucial para obter o p99
    wrk -t$THREADS -c$C -d$DURACAO --latency $URL > "result_${TEST_NAME}_c${C}.txt"
    echo "Resultado salvo em result_${TEST_NAME}_c${C}.txt"
    echo "--------------------------------------"
done

echo "Benchmark concluído!"
