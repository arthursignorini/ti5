# Relatório de Análise do Projeto: Latência TCP/Wi-Fi

## 1. Introdução

Este relatório apresenta uma análise detalhada do projeto `ti6-main`, que tem como objetivo comparar o desempenho de latência de cauda (p99) de dois modelos de servidores TCP (Multithread e Multiprocess) em cenários I/O-bound. O projeto visa fornecer uma base para a análise de desempenho em diferentes ambientes de rede, como Wi-Fi e Ethernet.

## 2. Estrutura do Projeto

O projeto `ti6-main` é composto pelos seguintes arquivos e diretórios:

*   `README.md`: Documento que descreve o propósito do projeto, sua estrutura, pré-requisitos e instruções de execução.
*   `projeto/`:
    *   `server_threaded.py`: Implementação de um servidor TCP que utiliza uma nova thread para lidar com cada conexão de cliente.
    *   `server_multiprocess.py`: Implementação de um servidor TCP que utiliza um novo processo para lidar com cada conexão de cliente.
    *   `run_benchmark.sh`: Script shell para automatizar a execução de testes de benchmark utilizando a ferramenta `wrk`.

## 3. Análise Técnica

### 3.1. Implementações de Servidor

Ambos os servidores são implementados em Python e simulam uma operação I/O-bound através de um `time.sleep(0.05)` (50ms) para cada requisição. Eles respondem com um simples "Hello, World!" via HTTP/1.1.

#### 3.1.1. `server_threaded.py` (Servidor Multithread)

Este servidor cria uma nova **thread** para cada conexão de cliente aceita. As principais características são:

*   **Módulo `threading`**: Utiliza o módulo `threading` do Python para gerenciar as threads.
*   **Porta**: Ouve na porta `8080`.
*   **`SO_REUSEADDR`**: Configurado para reutilizar o endereço do socket, permitindo reinícios rápidos do servidor.
*   **Fila de Espera**: `server_socket.listen(5000)` define uma fila de espera alta para conexões pendentes, visando suportar cargas elevadas.
*   **`handle_client`**: Função que recebe a requisição, simula o I/O-bound e envia a resposta. Cada thread executa esta função.
*   **`daemon = True`**: As threads são definidas como *daemon*, o que significa que o programa principal não precisa esperar por elas para terminar.

#### 3.1.2. `server_multiprocess.py` (Servidor Multiprocess)

Este servidor cria um novo **processo** para cada conexão de cliente aceita. As principais características são:

*   **Módulo `multiprocessing`**: Utiliza o módulo `multiprocessing` do Python para gerenciar os processos.
*   **Porta**: Ouve na porta `8081` para evitar conflitos com o servidor multithread.
*   **`SO_REUSEADDR`**: Similar ao multithread, permite a reutilização do endereço do socket.
*   **Fila de Espera**: Também configurado com `server_socket.listen(5000)`.
*   **`handle_client`**: Similar ao multithread, mas executado em um processo separado. Inclui `os._exit(0)` para garantir que o processo filho termine após lidar com a requisição.
*   **Fechamento do Socket no Pai**: O socket do cliente é fechado no processo pai (`client_sock.close()`) imediatamente após a criação do processo filho, para evitar que o pai mantenha referências desnecessárias.
*   **Tratamento de Erros Silencioso**: A exceção no `handle_client` é capturada e ignorada (`pass`), o que pode dificultar a depuração em caso de problemas.

### 3.2. Script de Benchmark (`run_benchmark.sh`)

O script `run_benchmark.sh` é uma ferramenta de automação para executar testes de carga nos servidores utilizando a ferramenta `wrk`. Ele aceita dois argumentos:

*   `URL`: O endereço do servidor a ser testado (ex: `http://localhost:8080`).
*   `TEST_NAME`: Um nome descritivo para o teste, usado para nomear os arquivos de resultado.

As principais funcionalidades do script são:

*   **Cenários de Carga**: Define uma série de conexões simultâneas a serem testadas: 100, 500, 1000 e 5000.
*   **Duração**: Cada teste é executado por 60 segundos.
*   **Threads do `wrk`**: Utiliza 12 threads do `wrk` para gerar a carga.
*   **Coleta de Latência**: O parâmetro `--latency` é crucial para que o `wrk` colete e reporte métricas de latência, incluindo o p99.
*   **Salvamento de Resultados**: Os resultados de cada cenário são salvos em arquivos `.txt` individuais (ex: `result_multithread_local_c100.txt`).

## 4. Prós e Contras / Considerações

### 4.1. Servidor Multithread (`server_threaded.py`)

**Prós:**

*   **Menor Overhead**: A criação e troca de contexto entre threads geralmente têm um custo menor do que entre processos.
*   **Compartilhamento de Memória**: Threads compartilham o mesmo espaço de endereço de memória, facilitando o compartilhamento de dados (embora não seja um fator crítico neste projeto simples).

**Contras:**

*   **Global Interpreter Lock (GIL)**: Em Python, o GIL limita a execução de bytecode Python a uma única thread por vez, mesmo em sistemas multi-core. Isso significa que o `server_threaded.py` não se beneficiará de múltiplos núcleos de CPU para tarefas CPU-bound, embora para tarefas I/O-bound (como simulado com `time.sleep`), o GIL libere o controle durante as operações de I/O, permitindo que outras threads executem.
*   **Complexidade de Sincronização**: Em aplicações mais complexas, o compartilhamento de memória pode levar a condições de corrida e deadlocks, exigindo mecanismos de sincronização.

### 4.2. Servidor Multiprocess (`server_multiprocess.py`)

**Prós:**

*   **Paralelismo Verdadeiro**: Cada processo tem seu próprio interpretador Python e espaço de memória, permitindo a execução paralela em múltiplos núcleos de CPU, contornando o GIL.
*   **Isolamento**: Falhas em um processo filho geralmente não afetam outros processos, aumentando a robustez.

**Contras:**

*   **Maior Overhead**: A criação de processos é mais custosa em termos de tempo e recursos (memória) do que a criação de threads.
*   **Comunicação Interprocessos (IPC)**: O compartilhamento de dados entre processos é mais complexo, exigindo mecanismos IPC explícitos (pipes, filas, memória compartilhada).
*   **`os._exit(0)`**: Embora funcional para garantir o término do processo filho, pode ser considerado uma prática menos elegante do que permitir que a função `handle_client` retorne naturalmente, embora em um servidor de socket que faz `fork` por conexão, é uma abordagem comum.
*   **Tratamento de Erros Silencioso**: A supressão de erros pode dificultar a identificação e resolução de problemas.

### 4.3. Script de Benchmark (`run_benchmark.sh`)

**Prós:**

*   **Automação Eficaz**: Automatiza a execução de múltiplos cenários de teste com `wrk`.
*   **Foco em Latência**: O uso do `--latency` no `wrk` é apropriado para o objetivo de medir a latência de cauda (p99).
*   **Resultados Separados**: Salva os resultados em arquivos distintos, facilitando a análise posterior.

**Contras:**

*   **Análise Manual**: A análise dos arquivos de resultado `.txt` ainda é manual, o que pode ser tedioso para um grande volume de dados.
*   **Dependência de `wrk`**: Requer a instalação prévia da ferramenta `wrk`.

## 5. Sugestões de Melhoria e Aprimoramento

Para aprimorar o projeto e a análise, as seguintes sugestões podem ser consideradas:

1.  **Servidores Assíncronos (`asyncio`)**: Para Python, o uso de `asyncio` com `async`/`await` é uma abordagem moderna e eficiente para lidar com operações I/O-bound, pois permite que uma única thread gerencie muitas conexões concorrentes sem a necessidade de múltiplas threads ou processos, liberando o GIL durante as operações de I/O. Isso poderia ser uma terceira implementação para comparação.
2.  **Pool de Threads/Processos**: Em vez de criar uma nova thread/processo para *cada* conexão, implementar um pool de threads ou processos pré-criados. Isso reduziria o overhead de criação e destruição de recursos para cada requisição, melhorando o desempenho sob alta carga.
3.  **Logging Estruturado**: Implementar um sistema de logging mais robusto em ambos os servidores, registrando erros, avisos e informações relevantes. Isso facilitaria a depuração e o monitoramento do comportamento do servidor.
4.  **Análise Automatizada de Resultados**: Estender o `run_benchmark.sh` ou criar um script Python separado para:
    *   **Parsear os resultados do `wrk`**: Extrair automaticamente as métricas de latência (média, p50, p90, p99, p99.9), throughput e erros de cada arquivo `.txt`.
    *   **Gerar Relatórios/Gráficos**: Utilizar bibliotecas como `matplotlib` ou `seaborn` em Python para visualizar os dados de latência e throughput, facilitando a comparação entre os servidores e os cenários de carga. Isso permitiria uma análise mais visual e rápida.
5.  **Variação do `IO_SLEEP_TIME`**: Realizar testes com diferentes valores para `IO_SLEEP_TIME` (ex: 10ms, 100ms, 200ms) para observar como a latência de cauda é afetada em diferentes graus de I/O-bound.
6.  **Tamanho do Payload Variável**: Testar com diferentes tamanhos de resposta HTTP para verificar o impacto na latência e no throughput.
7.  **Monitoramento de Recursos Integrado**: Integrar a coleta de métricas de uso de CPU e memória (usando ferramentas como `psutil` em Python ou comandos `top`/`htop` e parseando a saída) durante os benchmarks para correlacionar o consumo de recursos com o desempenho.

## 6. Conclusão

O projeto `ti6-main` fornece uma base sólida para a experimentação e análise do desempenho de servidores TCP em Python sob diferentes modelos de concorrência (multithread e multiprocess) e cenários de carga I/O-bound. A estrutura é clara e as ferramentas escolhidas (`wrk`) são adequadas para o objetivo de medir latência. As sugestões de aprimoramento visam tornar o processo de benchmark e análise de resultados mais robusto e automatizado, além de explorar outras abordagens de concorrência em Python.
