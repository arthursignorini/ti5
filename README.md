# Projeto de Análise de Latência TCP/Wi-Fi

Este projeto implementa dois modelos de servidores TCP (Multithread e Multiprocess) para comparar o desempenho de latência de cauda (p99) em cenários I/O-bound, conforme especificado no documento de análise.

## Estrutura do Projeto

- `server_threaded.py`: Servidor que utiliza uma thread por conexão.
- `server_multiprocess.py`: Servidor que utiliza um processo por conexão.
- `run_benchmark.sh`: Script de automação para execução dos testes com a ferramenta `wrk`.

## Pré-requisitos

Para rodar os testes, você precisará de:
1. **Python 3.x** instalado.
2. **wrk** (ferramenta de benchmark HTTP).
   - No Ubuntu/Debian: `sudo apt-get install wrk`
   - No macOS: `brew install wrk`

## Como Executar os Servidores

### 1. Servidor Multithread
Abra um terminal e execute:
```bash
python3 server_threaded.py
```
O servidor ficará ouvindo na porta **8080**.

### 2. Servidor Multiprocess
Abra outro terminal (ou encerre o anterior) e execute:
```bash
python3 server_multiprocess.py
```
O servidor ficará ouvindo na porta **8081**.

## Como Executar os Testes (Geração de Carga)

O script `run_benchmark.sh` automatiza os cenários de 100, 500, 1000 e 5000 conexões simultâneas durante 60 segundos cada.

### Testando o Servidor Multithread:
```bash
./run_benchmark.sh http://localhost:8080 multithread_local
```

### Testando o Servidor Multiprocess:
```bash
./run_benchmark.sh http://localhost:8081 multiprocess_local
```

## Monitoramento de Recursos

Enquanto os testes rodam, recomenda-se monitorar o uso de CPU e Memória em outro terminal usando:
- `htop` ou `top`
- `ps aux | grep python` (para ver a quantidade de processos/threads)

## Cenários Wi-Fi vs Ethernet

Para realizar os testes conforme o PDF:
1. **Cabo Ethernet**: Conecte as duas máquinas via cabo e use o IP da máquina servidor no comando do benchmark.
2. **Wi-Fi**: Conecte ambas na mesma rede Wi-Fi e repita os testes.

Os resultados serão salvos em arquivos `.txt` individuais para cada nível de carga, facilitando a coleta de dados para a análise final.
