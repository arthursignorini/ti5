"""
Servidor TCP Multiprocess — com coleta de métricas em tempo real.

Carga simulada (escopo definido):
  1. Parsing do request HTTP (extrai método e path)
  2. Leitura de arquivo do disco — data.txt ~1KB (I/O real)
  3. Simulação de consulta externa — time.sleep(0.05) / 50ms
  4. Resposta HTTP dinâmica

Notas de implementação:
  - MAX_WORKERS NÃO limita a concorrência de forma artificial;
    o BoundedSemaphore serve apenas para evitar esgotamento de memória.
    Ajuste conforme o SO de teste.
  - O ponto de ruptura é medido pelo cliente (p99 > 5x baseline ou erro > 5%),
    não por crash do servidor — degradação graciosa é o comportamento esperado.
"""

import socket
import multiprocessing
import threading
import ctypes
import time
import os
import psutil
from collections import deque

HOST = "0.0.0.0"
PORT = 8081
IO_SLEEP_TIME = 0.05

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.txt")

# Limite de processos simultâneos (evita OOM do SO).
# Aumente conforme RAM disponível na máquina de teste.
MAX_WORKERS = min(256, (os.cpu_count() or 4) * 32)

_shared_requests = multiprocessing.Value(ctypes.c_uint64, 0)
_shared_errors   = multiprocessing.Value(ctypes.c_uint64, 0)
_shared_active   = multiprocessing.Value(ctypes.c_int32, 0)

_latency_ipc_queue = multiprocessing.Queue(maxsize=50000)

_latency_buffer = deque(maxlen=10000)
_cpu_history    = deque(maxlen=120)
_mem_history    = deque(maxlen=120)
_start_time     = time.time()

_metrics_queue = None


def set_metrics_queue(q):
    global _metrics_queue
    _metrics_queue = q


def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    index = int((p / 100) * (len(values) - 1))
    return float(values[index])


def _drain_latency_queue():
    while True:
        try:
            val = _latency_ipc_queue.get_nowait()
            _latency_buffer.append(val)
        except Exception:
            break


def _collect_system_metrics():
    processo_pai = psutil.Process()

    while True:
        try:
            cpu_total = processo_pai.cpu_percent(interval=1.0)
            mem_total_mb = processo_pai.memory_info().rss / (1024 * 1024)

            for filho in processo_pai.children(recursive=True):
                try:
                    cpu_total += filho.cpu_percent(interval=None)
                    mem_total_mb += filho.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            cpu_final = cpu_total / max(1, psutil.cpu_count())

            _cpu_history.append(cpu_final)
            _mem_history.append(mem_total_mb)

        except Exception as e:
            print(f"[multiprocess] Erro na coleta: {e}")

        time.sleep(1)


def snapshot():
    _drain_latency_queue()

    count   = _shared_requests.value
    errors  = _shared_errors.value
    active  = _shared_active.value
    elapsed = time.time() - _start_time

    latencies = list(_latency_buffer)
    cpu_hist  = list(_cpu_history)
    mem_hist  = list(_mem_history)

    if latencies:
        avg  = sum(latencies) / len(latencies)
        p50  = percentile(latencies, 50)
        p90  = percentile(latencies, 90)
        p99  = percentile(latencies, 99)
        p100 = max(latencies)
    else:
        avg = p50 = p90 = p99 = p100 = 0.0

    throughput = count / elapsed if elapsed > 0 else 0.0
    error_rate = (errors / count * 100) if count > 0 else 0.0

    return {
        "server":     "multiprocess",
        "port":       PORT,
        "timestamp":  time.time(),
        "requests":   count,
        "errors":     errors,
        "error_rate": round(error_rate, 2),
        "active_conn": active,
        "throughput": round(throughput, 2),
        "latency": {
            "avg":  round(avg,  2),
            "p50":  round(p50,  2),
            "p90":  round(p90,  2),
            "p99":  round(p99,  2),
            "p100": round(p100, 2),
        },
        "cpu":       round(cpu_hist[-1], 1) if cpu_hist else 0.0,
        "memory_mb": round(mem_hist[-1], 1) if mem_hist else 0.0,
        "memory":    round(mem_hist[-1] / psutil.virtual_memory().total * 100 * (1024*1024), 2) if mem_hist else 0.0,
        "cpu_history": [round(v, 1) for v in cpu_hist],
        "mem_history": [round(v, 1) for v in mem_hist],
    }


def _publish_metrics():
    while True:
        time.sleep(1)
        if _metrics_queue is not None:
            try:
                _metrics_queue.put_nowait(("multiprocess", snapshot()))
            except Exception:
                pass


def handle_client(
    client_socket,
    address,
    req_counter,
    err_counter,
    active_counter,
    lat_queue,
    worker_slots
):
    t0 = time.time()

    with active_counter.get_lock():
        active_counter.value += 1

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
        with err_counter.get_lock():
            err_counter.value += 1

    finally:
        try:
            client_socket.close()
        except Exception:
            pass

        elapsed_ms = (time.time() - t0) * 1000

        with req_counter.get_lock():
            req_counter.value += 1

        with active_counter.get_lock():
            active_counter.value -= 1

        try:
            lat_queue.put_nowait(elapsed_ms)
        except Exception:
            pass

        try:
            worker_slots.release()
        except Exception:
            pass


def limpar_processos_finalizados(processos):
    vivos = []
    for p in processos:
        if p.is_alive():
            vivos.append(p)
        else:
            p.join(timeout=0)
    return vivos


def main():
    print(f"[multiprocess] MAX_WORKERS = {MAX_WORKERS}")

    for target in (_collect_system_metrics, _publish_metrics):
        t = threading.Thread(target=target, daemon=True)
        t.start()

    worker_slots = multiprocessing.BoundedSemaphore(MAX_WORKERS)
    processos = []

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5000)

    print(f"[multiprocess] Ouvindo em {HOST}:{PORT}")

    try:
        while True:
            processos = limpar_processos_finalizados(processos)
            client_sock, address = server_socket.accept()

            worker_slots.acquire()

            try:
                p = multiprocessing.Process(
                    target=handle_client,
                    args=(
                        client_sock,
                        address,
                        _shared_requests,
                        _shared_errors,
                        _shared_active,
                        _latency_ipc_queue,
                        worker_slots,
                    )
                )
                p.start()
                processos.append(p)

            except Exception as e:
                print(f"[multiprocess] Erro ao iniciar processo: {e}")
                with _shared_errors.get_lock():
                    _shared_errors.value += 1
                try:
                    worker_slots.release()
                except Exception:
                    pass

            finally:
                try:
                    client_sock.close()
                except Exception:
                    pass

    except KeyboardInterrupt:
        print("\n[multiprocess] Encerrando.")

    finally:
        server_socket.close()
        for p in processos:
            try:
                if p.is_alive():
                    p.terminate()
                p.join(timeout=1)
            except Exception:
                pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
