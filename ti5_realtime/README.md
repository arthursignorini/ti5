# TI5 — Live Benchmark Dashboard

Dashboard em tempo real para comparar os servidores TCP Multithread e Multiprocess,
com atualização ao vivo via WebSocket enquanto o cliente gera carga com `wrk`.

## Estrutura

```
ti5_realtime/
├── launcher.py              ← Inicia tudo com 1 comando
├── requirements.txt
└── projeto/
    ├── server_threaded.py   ← Servidor TCP Multithread  (porta 8080)
    ├── server_multiprocess.py ← Servidor TCP Multiprocess (porta 8081)
    ├── metrics_server.py    ← WebSocket + HTTP server   (portas 8888 / 8765)
    └── dashboard.html       ← Interface ao vivo (servida automaticamente)
```

## Instalação

```bash
pip install -r requirements.txt
```

## Como usar

### 1. Na máquina servidora — sobe tudo de uma vez:

```bash
python launcher.py
```

Saída esperada:
```
=======================================================
  TI5 — TCP Benchmark  |  Iniciando serviços...
=======================================================
  ✓ Multithread  iniciado  (PID 12345) → porta 8080
  ✓ Multiprocess iniciado  (PID 12346) → porta 8081
  ✓ Dashboard disponível em  http://localhost:8888
  ✓ WebSocket na porta       8765
=======================================================
  Pressione Ctrl+C para encerrar tudo.
=======================================================
```

### 2. Abra o dashboard no navegador:

```
http://<IP_DA_MAQUINA_SERVIDORA>:8888
```

### 3. Na máquina cliente — gere a carga:

```bash
# Teste o servidor Multithread (porta 8080)
wrk -t12 -c100  -d60s --latency http://<IP_SERVIDOR>:8080
wrk -t12 -c500  -d60s --latency http://<IP_SERVIDOR>:8080
wrk -t12 -c1000 -d60s --latency http://<IP_SERVIDOR>:8080
wrk -t12 -c5000 -d60s --latency http://<IP_SERVIDOR>:8080

# Teste o servidor Multiprocess (porta 8081)
wrk -t12 -c100  -d60s --latency http://<IP_SERVIDOR>:8081
wrk -t12 -c500  -d60s --latency http://<IP_SERVIDOR>:8081
wrk -t12 -c1000 -d60s --latency http://<IP_SERVIDOR>:8081
wrk -t12 -c5000 -d60s --latency http://<IP_SERVIDOR>:8081

# Ou use o script de automação:
./run_benchmark.sh http://<IP_SERVIDOR>:8080 multithread_teste
./run_benchmark.sh http://<IP_SERVIDOR>:8081 multiprocess_teste
```

Enquanto o `wrk` roda, o dashboard atualiza os gráficos ao vivo!

## Portas utilizadas

| Porta | Serviço |
|-------|---------|
| 8080  | Servidor TCP Multithread |
| 8081  | Servidor TCP Multiprocess |
| 8888  | Dashboard HTTP (abra no browser) |
| 8765  | WebSocket (usado internamente pelo dashboard) |

## Firewall (se necessário)

Se o cliente estiver em outra máquina, libere as portas no servidor:

```bash
# Ubuntu/Debian
sudo ufw allow 8080/tcp
sudo ufw allow 8081/tcp
sudo ufw allow 8888/tcp
sudo ufw allow 8765/tcp
```

## Fallback para polling HTTP

Se o WebSocket não puder ser estabelecido (firewall, proxy, etc.),
o dashboard cai automaticamente para polling HTTP na porta 8888/metrics,
atualizando a cada 2 segundos. O indicador no canto superior direito
mostra o modo de conexão atual.
