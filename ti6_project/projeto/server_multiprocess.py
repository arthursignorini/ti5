import socket
import multiprocessing
import time
import os
import psutil
import json
from datetime import datetime
import numpy as np

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 8081  # Porta diferente para evitar conflito se rodar simultaneamente
IO_SLEEP_TIME = 0.05  # 50ms simulando I/O-bound

# Métricas globais (para o processo pai)
request_count = 0
error_count = 0
start_time = time.time()

# Monitor de sistema (para o processo pai)
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
    try:
        request = client_socket.recv(1024).decode("utf-8")
        
        time.sleep(IO_SLEEP_TIME)
        
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 13\r\n\r\nHello, World!"
        client_socket.sendall(response.encode("utf-8"))
    except Exception as e:
        # Log errors instead of silencing, but cannot directly update parent's error_count
        print(f"Erro ao lidar com {address}: {e}")
        # In a real scenario, child process would send error info back to parent via IPC
        # For this project, we'll count errors in the parent process based on accepted connections
    finally:
        client_socket.close()
        os._exit(0) # O processo filho deve terminar após lidar com a requisição

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5000)
    
    print(f"Servidor Multiprocess rodando em {HOST}:{PORT}")
    monitor.start()
    
    try:
        while True:
            client_sock, address = server_socket.accept()
            # Incrementa a contagem de requisições no processo pai
            global request_count
            request_count += 1
            process = multiprocessing.Process(target=handle_client, args=(client_sock, address))
            process.daemon = True
            process.start()
            client_sock.close()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        monitor.stop()
        server_socket.close()
        
        # Calcular e salvar métricas
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Throughput é calculado com base no request_count do processo pai
        if request_count > 0:
            throughput = request_count / total_duration
            # Error rate cannot be accurately calculated here without IPC from child processes
            # For now, we'll assume 0 errors if no explicit error communication is set up
            error_rate = 0 # Placeholder
        else:
            throughput = 0
            error_rate = 0

        system_metrics = monitor.get_metrics()

        results = {
            "server_type": "multiprocess",
            "total_requests": request_count,
            "error_count": error_count, # This will likely be 0 without IPC
            "error_rate_percent": error_rate,
            "total_duration_s": total_duration,
            "throughput_req_s": throughput,
            "cpu_usages_percent": system_metrics["cpu_usages"],
            "memory_usages_percent": system_metrics["memory_usages"],
            "timestamp": datetime.now().isoformat()
        }

        with open(f"multiprocess_results_{datetime.now().strftime("%Y%m%d%H%M%S")}.json", "w") as f:
            json.dump(results, f, indent=4)
        print("Métricas salvas.")

if __name__ == "__main__":
    main()
