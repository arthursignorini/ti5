import psutil
import time
import threading

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

if __name__ == "__main__":
    monitor = SystemMonitor(interval=1)
    monitor.start()
    print("Coletando métricas por 10 segundos...")
    time.sleep(10)
    monitor.stop()
    metrics = monitor.get_metrics()
    print("Uso de CPU:", metrics["cpu_usages"])
    print("Uso de Memória:", metrics["memory_usages"])
