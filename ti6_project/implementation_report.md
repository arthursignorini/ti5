# Relatório de Implementação de Métricas nos Servidores TCP

## 1. Introdução

Este relatório detalha as modificações realizadas nos servidores TCP (`server_threaded.py` e `server_multiprocess.py`) para integrar a coleta de métricas de desempenho e recursos, conforme solicitado pelo usuário. O objetivo é permitir a medição de CPU, memória, latência por requisição e throughput diretamente nos servidores, facilitando a análise em cenários de teste distribuídos (máquina cliente e máquina servidor).

## 2. Modificações Implementadas

### 2.1. Módulo de Monitoramento de Sistema (`monitor.py`)

Foi criado um novo módulo `monitor.py` que encapsula a lógica de coleta de métricas de CPU e memória utilizando a biblioteca `psutil`. Este módulo é executado em uma thread separada para não bloquear o servidor principal e coleta amostras de uso de CPU e memória em intervalos regulares. As métricas são armazenadas internamente e podem ser recuperadas quando o monitoramento é interrompido.

**Principais características:**

*   **`SystemMonitor` Classe**: Gerencia a coleta de métricas de CPU e memória.
*   **`psutil`**: Biblioteca utilizada para acessar informações do sistema.
*   **Thread Separada**: A coleta ocorre em segundo plano para minimizar o impacto no desempenho do servidor.
*   **`cpu_percent()`**: Coleta a porcentagem de uso da CPU.
*   **`virtual_memory().percent`**: Coleta a porcentagem de uso da memória RAM.

### 2.2. `server_threaded.py` (Servidor Multithread)

O servidor multithread foi atualizado para:

*   **Integração do `SystemMonitor`**: Uma instância do `SystemMonitor` é iniciada junto com o servidor e parada ao final da execução.
*   **Medição de Latência por Requisição**: O tempo de início e fim de cada requisição é registrado, permitindo o cálculo da latência individual.
*   **Contagem de Requisições e Erros**: O número total de requisições processadas e o número de erros são contabilizados.
*   **Cálculo de Métricas Agregadas**: Ao encerrar o servidor (via `KeyboardInterrupt`):
    *   **Latências**: São calculadas a latência média, p50, p99 e p100 (máxima) em milissegundos usando `numpy`.
    *   **Throughput**: Calculado como requisições por segundo.
    *   **Taxa de Erros**: Calculada como a porcentagem de requisições com erro.
    *   **Uso de CPU e Memória**: As amostras coletadas pelo `SystemMonitor` são incluídas.
*   **Exportação de Resultados**: Todas as métricas são salvas em um arquivo JSON com um timestamp no nome (ex: `multithread_results_YYYYMMDDHHMMSS.json`).

### 2.3. `server_multiprocess.py` (Servidor Multiprocess)

O servidor multiprocess também foi atualizado com as seguintes considerações:

*   **Integração do `SystemMonitor`**: Similar ao servidor multithread, o `SystemMonitor` é iniciado e parado no processo pai.
*   **Contagem de Requisições e Erros**: O processo pai contabiliza o número total de requisições aceitas. A contagem de erros é mais desafiadora em um modelo multiprocess sem um mecanismo de IPC (Inter-Process Communication) explícito para reportar erros dos processos filhos. Para simplificar, a taxa de erros é definida como 0 neste contexto, assumindo que o `wrk` será a principal fonte para identificar erros de requisição.
*   **Latência por Requisição**: A medição de latência individual por requisição é complexa em um modelo `fork`-based, pois cada processo filho tem seu próprio espaço de memória e não compartilha facilmente dados com o pai para agregação em tempo real. Portanto, a latência individual não é coletada diretamente no servidor multiprocess; espera-se que o `wrk` forneça essa métrica de forma mais precisa.
*   **Cálculo de Throughput**: Calculado no processo pai com base no número total de requisições aceitas e na duração total.
*   **Exportação de Resultados**: As métricas de throughput, uso de CPU/memória e contagem total de requisições são salvas em um arquivo JSON (ex: `multiprocess_results_YYYYMMDDHHMMSS.json`).

## 3. Como Utilizar os Servidores Atualizados

Para utilizar os servidores com a coleta de métricas integrada, siga os passos abaixo:

1.  **Instalar `psutil`**: Certifique-se de que a biblioteca `psutil` esteja instalada no ambiente onde os servidores serão executados:
    ```bash
    sudo pip3 install psutil
    ```

2.  **Executar o Servidor Multithread**: Em uma máquina (servidor), execute:
    ```bash
    python3 projeto/server_threaded.py
    ```
    O servidor estará ouvindo na porta `8080`.

3.  **Executar o Servidor Multiprocess**: Em outra máquina (ou no mesmo servidor, em um terminal diferente), execute:
    ```bash
    python3 projeto/server_multiprocess.py
    ```
    O servidor estará ouvindo na porta `8081`.

4.  **Gerar Carga com `wrk`**: Na máquina cliente, utilize o script `run_benchmark.sh` (ou execute o `wrk` diretamente) apontando para o IP da máquina servidor e a porta correspondente. Por exemplo:
    ```bash
    ./projeto/run_benchmark.sh http://<IP_DO_SERVIDOR>:8080 multithread_rede
    ./projeto/run_benchmark.sh http://<IP_DO_SERVIDOR>:8081 multiprocess_rede
    ```

5.  **Coletar Resultados**: Após a execução dos testes (e o encerramento dos servidores com `Ctrl+C`), os arquivos JSON contendo as métricas serão gerados no mesmo diretório dos scripts do servidor.

## 4. Próximos Passos e Recomendações

*   **Análise de Dados**: Os arquivos JSON gerados podem ser facilmente processados por scripts Python para análise e visualização (ex: gráficos de latência, uso de recursos ao longo do tempo).
*   **Mecanismo IPC para Multiprocess**: Para uma coleta mais granular de métricas de latência e erros em `server_multiprocess.py`, seria ideal implementar um mecanismo de IPC (como `multiprocessing.Queue` ou `Pipe`) para que os processos filhos possam reportar suas métricas ao processo pai para agregação.
*   **Persistência de Dados**: Considerar o uso de um banco de dados (SQLite, InfluxDB) para armazenar as métricas de forma mais robusta, especialmente em testes de longa duração.
*   **Visualização em Tempo Real**: Para monitoramento avançado, pode-se integrar um sistema de visualização em tempo real (ex: Grafana com Prometheus) para observar o desempenho do servidor durante os testes.

## 5. Conclusão

As modificações implementadas fornecem uma base para a coleta de métricas essenciais diretamente nos servidores, permitindo uma análise mais completa do desempenho em diferentes cenários de rede e modelos de concorrência. Embora o `wrk` continue sendo a ferramenta principal para a geração de carga e medição de latência de cauda, a integração de monitoramento de CPU e memória nos servidores complementa essa análise, oferecendo uma visão holística do comportamento do sistema sob carga.
