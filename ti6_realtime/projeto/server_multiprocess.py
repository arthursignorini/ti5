"""
Servidor TCP Multiprocess — com coleta de métricas em tempo real.
Usa multiprocessing.Value/Array para compartilhar contadores entre
o processo pai e os filhos, publicando na fila do metrics_server.
Porta TCP: 8081
"""

import socket
import multiprocessing
import threading
import ctypes
import time
import os
import psutil
import numpy as np
from collections import deque

HOST = '0.0.0.0'
PORT = 8081
IO_SLEEP_TIME = 0.05

# -------------------------------------------------------------------
# Contadores compartilhados entre pai e filhos via memória compartilhada
# -------------------------------------------------------------------
_shared_requests = multiprocessing.Value(ctypes.c_uint64, 0)
_shared_errors   = multiprocessing.Value(ctypes.c_uint64, 0)
_shared_active   = multiprocessing.Value(ctypes.c_int32,  0)

# Latências reportadas pelos filhos → pai via Queue IPC
_latency_ipc_queue = multiprocessing.Queue(maxsize=50000)

# Acumulador local no pai
_latency_buffer = deque(maxlen=10000)
_cpu_history    = deque(maxlen=120)
_mem_history    = deque(maxlen=120)
_start_time     = time.time()

# Fila para o metrics_server (injetada pelo launcher)
_metrics_queue  = None


def set_metrics_queue(q):
    global _metrics_queue
    _metrics_queue = q


# -------------------------------------------------------------------
# Drena a fila IPC de latências no processo pai
# -------------------------------------------------------------------
def _drain_latency_queue():
    while True:
        try:
            val = _latency_ipc_queue.get_nowait()
            _latency_buffer.append(val)
        except Exception:
            break


# -------------------------------------------------------------------
# Coleta periódica de CPU/memória (no processo pai)
# -------------------------------------------------------------------
def _collect_system_metrics():
    processo_pai = psutil.Process()
    while True:
        try:
            # Pega o CPU do pai + todos os filhos ativos
            cpu_total = processo_pai.cpu_percent(interval=1.0)
            mem_total = processo_pai.memory_percent()
            
            for filho in processo_pai.children(recursive=True):
                try:
                    cpu_total += filho.cpu_percent(interval=None)
                    mem_total += filho.memory_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Ajusta a escala da CPU pelo número de núcleos
            cpu_final = cpu_total / psutil.cpu_count()
            
            # No multiprocess.py, não usamos Lock aqui, apenas o append no deque local do pai
            _cpu_history.append(cpu_final)
            _mem_history.append(mem_total)
            
        except Exception as e:
            print(f"Erro na coleta: {e}")
            
        time.sleep(1)


# -------------------------------------------------------------------
# Snapshot de métricas
# -------------------------------------------------------------------
def snapshot():
    _drain_latency_queue()

    count  = _shared_requests.value
    errors = _shared_errors.value
    active = _shared_active.value
    elapsed = time.time() - _start_time
    latencies = list(_latency_buffer)
    cpu_hist  = list(_cpu_history)
    mem_hist  = list(_mem_history)

    if latencies:
        arr  = np.array(latencies)
        p50  = float(np.percentile(arr, 50))
        p90  = float(np.percentile(arr, 90))
        p99  = float(np.percentile(arr, 99))
        p100 = float(np.max(arr))
        avg  = float(np.mean(arr))
    else:
        p50 = p90 = p99 = p100 = avg = 0.0

    throughput = count / elapsed if elapsed > 0 else 0.0

    return {
        "server":      "multiprocess",
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
# Publisher
# -------------------------------------------------------------------
def _publish_metrics():
    while True:
        time.sleep(1)
        if _metrics_queue is not None:
            try:
                _metrics_queue.put_nowait(("multiprocess", snapshot()))
            except Exception:
                pass


# -------------------------------------------------------------------
# Handler do processo filho
# -------------------------------------------------------------------
def handle_client(client_socket, address, req_counter, err_counter, active_counter, lat_queue):
    t0 = time.time()
    with active_counter.get_lock():
        active_counter.value += 1
    try:
        client_socket.recv(4096)
        time.sleep(IO_SLEEP_TIME)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "\r\n"
            "Hello, World!"
        )
        client_socket.sendall(response.encode())
    except Exception:
        with err_counter.get_lock():
            err_counter.value += 1
    finally:
        client_socket.close()
        elapsed_ms = (time.time() - t0) * 1000
        with req_counter.get_lock():
            req_counter.value += 1
        with active_counter.get_lock():
            active_counter.value -= 1
        try:
            lat_queue.put_nowait(elapsed_ms)
        except Exception:
            pass
        os._exit(0)


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
    print(f"[multiprocess] Ouvindo em {HOST}:{PORT}")

    try:
        while True:
            client_sock, address = server_socket.accept()
            p = multiprocessing.Process(
                target=handle_client,
                args=(client_sock, address,
                      _shared_requests, _shared_errors,
                      _shared_active, _latency_ipc_queue),
                daemon=True
            )
            p.start()
            client_sock.close()
    except KeyboardInterrupt:
        print("\n[multiprocess] Encerrando.")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
