"""
Servidor TCP Multithread — com coleta de métricas em tempo real.
Publica métricas via fila compartilhada com o metrics_server.
Porta TCP: 9090
"""

import socket
import threading
import time
import psutil
import numpy as np
from collections import deque

HOST = '0.0.0.0'
PORT = 9090
IO_SLEEP_TIME = 0.05  # 50ms I/O-bound simulado

# -------------------------------------------------------------------
# Estado de métricas — protegido por lock para acesso thread-safe
# -------------------------------------------------------------------
_lock = threading.Lock()
_request_latencies = deque(maxlen=10000)  # últimas 10k latências (ms)
_request_count = 0
_error_count = 0
_start_time = time.time()
_active_connections = 0

# Amostras de CPU/memória (1 por segundo)
_cpu_history = deque(maxlen=120)
_mem_history = deque(maxlen=120)

# Referência externa: o metrics_server injeta essa fila após o import
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
    # Warm-up para o cpu_percent
    processo.cpu_percent(interval=None)
    
    while True:
        # Mede o consumo apenas deste processo
        cpu = processo.cpu_percent(interval=None) / psutil.cpu_count()
        mem = processo.memory_percent()
        
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

    return {
        "server":      "multithread",
        "port":        PORT,
        "timestamp":   time.time(),
        "requests":    count,
        "errors":      errors,
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
        "memory": round(mem_hist[-1], 1) if mem_hist else 0.0,
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
# -------------------------------------------------------------------
def handle_client(client_socket, address):
    global _request_count, _error_count, _active_connections
    t0 = time.time()

    with _lock:
        _active_connections += 1

    try:
        client_socket.recv(4096)          # lê a requisição HTTP
        time.sleep(IO_SLEEP_TIME)         # simula I/O-bound
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "\r\n"
            "Hello, World!"
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
    # Inicia coleta de sistema e publicação de métricas em background
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
