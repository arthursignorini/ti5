import socket
import threading
import time
import psutil
import json
from datetime import datetime
import numpy as np

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 8080
IO_SLEEP_TIME = 0.05  # 50ms simulando I/O-bound

# Métricas globais
request_times = []
request_count = 0
error_count = 0
start_time = time.time()

# Monitor de sistema
class SystemMonitor:
    def __init__(self, interval=1):
        self.interval = interval
        self.cpu_usages = []
        self.memory_usages = []
        self._running = False
        self._thread = None

    def _collect_metrics(self):
        while self._running:
            cpu_percent = psutil.cpu_percent(interval=None) # Non-blocking
            memory_info = psutil.virtual_memory()
            self.cpu_usages.append(cpu_percent)
            self.memory_usages.append(memory_info.percent)
            time.sleep(self.interval)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._collect_metrics)
            self._thread.daemon = True
            self._thread.start()
            print("Monitoramento de sistema iniciado.")

    def stop(self):
        if self._running:
            self._running = False
            if self._thread:
                self._thread.join() # Wait for the thread to finish
            print("Monitoramento de sistema parado.")

    def get_metrics(self):
        return {
            "cpu_usages": self.cpu_usages,
            "memory_usages": self.memory_usages
        }

    def clear_metrics(self):
        self.cpu_usages = []
        self.memory_usages = []

monitor = SystemMonitor(interval=1)

def handle_client(client_socket, address):
    global request_count, error_count
    start_request_time = time.time()
    try:
        request = client_socket.recv(1024).decode('utf-8')
        
        time.sleep(IO_SLEEP_TIME)
        
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 13\r\n\r\nHello, World!"
        client_socket.sendall(response.encode('utf-8'))
    except Exception as e:
        print(f"Erro ao lidar com {address}: {e}")
        error_count += 1
    finally:
        client_socket.close()
        end_request_time = time.time()
        request_times.append(end_request_time - start_request_time)
        request_count += 1

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5000)
    
    print(f"Servidor Multithread rodando em {HOST}:{PORT}")
    monitor.start()
    
    try:
        while True:
            client_sock, address = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_sock, address))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        monitor.stop()
        server_socket.close()
        
        # Calcular e salvar métricas
        end_time = time.time()
        total_duration = end_time - start_time
        
        if request_count > 0:
            latencies_ms = np.array(request_times) * 1000
            avg_latency = np.mean(latencies_ms)
            p50_latency = np.percentile(latencies_ms, 50)
            p99_latency = np.percentile(latencies_ms, 99)
            p100_latency = np.max(latencies_ms)
            throughput = request_count / total_duration
            error_rate = (error_count / request_count) * 100
        else:
            avg_latency = 0
            p50_latency = 0
            p99_latency = 0
            p100_latency = 0
            throughput = 0
            error_rate = 0

        system_metrics = monitor.get_metrics()

        results = {
            "server_type": "multithread",
            "total_requests": request_count,
            "error_count": error_count,
            "error_rate_percent": error_rate,
            "total_duration_s": total_duration,
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p99_latency_ms": p99_latency,
            "p100_latency_ms": p100_latency,
            "throughput_req_s": throughput,
            "cpu_usages_percent": system_metrics["cpu_usages"],
            "memory_usages_percent": system_metrics["memory_usages"],
            "timestamp": datetime.now().isoformat()
        }

        with open(f"multithread_results_{datetime.now().strftime('%Y%m%d%H%M%S')}.json", "w") as f:
            json.dump(results, f, indent=4)
        print("Métricas salvas.")

if __name__ == "__main__":
    main()
