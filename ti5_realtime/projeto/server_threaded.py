"""
Servidor TCP Multithread — com coleta de métricas em tempo real.
Publica métricas via fila compartilhada com o metrics_server.
Porta TCP: 9090

Carga simulada (escopo definido):
  1. Parsing do request HTTP (extrai método e path)
  2. Leitura de arquivo do disco — data.txt ~1KB (I/O real)
  3. Simulação de consulta externa — time.sleep(0.05) / 50ms
  4. Resposta HTTP dinâmica
"""

import socket
import threading
import time
import os
import psutil
import numpy as np
from collections import deque

HOST = '0.0.0.0'
PORT = 9090
IO_SLEEP_TIME = 0.05  # 50ms simulando consulta a banco/API

# Caminho do arquivo de dados (~1KB) — I/O real de disco
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.txt")

# -------------------------------------------------------------------
# Estado de métricas — protegido por lock para acesso thread-safe
# -------------------------------------------------------------------
_lock = threading.Lock()
_request_latencies = deque(maxlen=10000)
_request_count = 0
_error_count = 0
_start_time = time.time()
_active_connections = 0

_cpu_history = deque(maxlen=120)
_mem_history = deque(maxlen=120)

_metrics_queue = None


def set_metrics_queue(q):
    """Chamado pelo launcher para injetar a fila de publicação."""
    global _metrics_queue
    _metrics_queue = q


# -------------------------------------------------------------------
# Coleta periódica de CPU/memória em background
# -------------------------------------------------------------------
def _collect_system_metrics():
    processo = psutil.Process()
    processo.cpu_percent(interval=None)  # warm-up

    while True:
        cpu = processo.cpu_percent(interval=None) / psutil.cpu_count()
        mem = processo.memory_info().rss / (1024 * 1024)  # MB (pico de RAM)

        with _lock:
            _cpu_history.append(cpu)
            _mem_history.append(mem)
        time.sleep(1)


# -------------------------------------------------------------------
# Snapshot de métricas atual (chamado a cada segundo pelo publisher)
# -------------------------------------------------------------------
def snapshot():
    with _lock:
        count = _request_count
        errors = _error_count
        elapsed = time.time() - _start_time
        latencies = list(_request_latencies)
        cpu_hist = list(_cpu_history)
        mem_hist = list(_mem_history)
        active = _active_connections

    if latencies:
        arr = np.array(latencies)
        p50  = float(np.percentile(arr, 50))
        p90  = float(np.percentile(arr, 90))
        p99  = float(np.percentile(arr, 99))
        p100 = float(np.max(arr))
        avg  = float(np.mean(arr))
    else:
        p50 = p90 = p99 = p100 = avg = 0.0

    throughput = count / elapsed if elapsed > 0 else 0.0
    error_rate = (errors / count * 100) if count > 0 else 0.0

    return {
        "server":      "multithread",
        "port":        PORT,
        "timestamp":   time.time(),
        "requests":    count,
        "errors":      errors,
        "error_rate":  round(error_rate, 2),
        "active_conn": active,
        "throughput":  round(throughput, 2),
        "latency": {
            "avg":  round(avg,  2),
            "p50":  round(p50,  2),
            "p90":  round(p90,  2),
            "p99":  round(p99,  2),
            "p100": round(p100, 2),
        },
        "cpu":    round(cpu_hist[-1], 1) if cpu_hist else 0.0,
        "memory_mb": round(mem_hist[-1], 1) if mem_hist else 0.0,
        # mantidos para compatibilidade com dashboard
        "memory": round(mem_hist[-1] / psutil.virtual_memory().total * 100 * (1024*1024), 2) if mem_hist else 0.0,
        "cpu_history": [round(v, 1) for v in cpu_hist],
        "mem_history": [round(v, 1) for v in mem_hist],
    }


# -------------------------------------------------------------------
# Publisher: envia snapshot pela fila a cada segundo
# -------------------------------------------------------------------
def _publish_metrics():
    while True:
        time.sleep(1)
        if _metrics_queue is not None:
            try:
                _metrics_queue.put_nowait(("multithread", snapshot()))
            except Exception:
                pass


# -------------------------------------------------------------------
# Handler de cada conexão TCP
# 4 etapas definidas no escopo:
#   1. Parsing do request HTTP
#   2. Leitura do arquivo data.txt (~1KB) do disco
#   3. time.sleep(0.05) — simula consulta a banco/API
#   4. Resposta HTTP dinâmica
# -------------------------------------------------------------------
def handle_client(client_socket, address):
    global _request_count, _error_count, _active_connections
    t0 = time.time()

    with _lock:
        _active_connections += 1

    try:
        # Etapa 1 — Parsing do request HTTP
        raw = client_socket.recv(4096).decode(errors="ignore")
        method = path = ""
        if raw:
            first_line = raw.split("\r\n")[0]
            parts = first_line.split(" ")
            if len(parts) >= 2:
                method, path = parts[0], parts[1]

        # Etapa 2 — Leitura de arquivo do disco (I/O real, ~1KB)
        with open(DATA_FILE, "r") as f:
            _ = f.read()

        # Etapa 3 — Simula consulta externa (banco de dados / API)
        time.sleep(IO_SLEEP_TIME)

        # Etapa 4 — Resposta HTTP dinâmica
        body = f"OK method={method} path={path}"
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n"
            "\r\n"
            f"{body}"
        )
        client_socket.sendall(response.encode())

    except Exception:
        with _lock:
            _error_count += 1
    finally:
        client_socket.close()
        elapsed_ms = (time.time() - t0) * 1000
        with _lock:
            _request_latencies.append(elapsed_ms)
            _request_count += 1
            _active_connections -= 1


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def main():
    for target in (_collect_system_metrics, _publish_metrics):
        t = threading.Thread(target=target, daemon=True)
        t.start()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5000)
    print(f"[multithread] Ouvindo em {HOST}:{PORT}")

    try:
        while True:
            client_sock, address = server_socket.accept()
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, address),
                daemon=True
            )
            t.start()
    except KeyboardInterrupt:
        print("\n[multithread] Encerrando.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
