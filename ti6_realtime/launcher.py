"""
launcher.py — Inicia tudo com um único comando:

    python launcher.py

O que este script faz:
  1. Importa os módulos dos servidores
  2. Cria uma fila de métricas compartilhada
  3. Injeta a fila em cada servidor
  4. Sobe server_threaded e server_multiprocess em processos separados
  5. Sobe o metrics_server (WebSocket + HTTP) no processo principal
  6. Ao pressionar Ctrl+C, encerra tudo de forma limpa

Portas:
  8080 — Servidor TCP Multithread
  8081 — Servidor TCP Multiprocess
  8888 — Dashboard HTTP  → abra http://localhost:8888
  8765 — WebSocket (usado pelo dashboard internamente)
"""

import multiprocessing
import threading
import signal
import sys
import time
import os

# Portas configuráveis
PORT_THREAD    = 9090
PORT_PROCESS   = 8081
PORT_HTTP      = 8888
PORT_WS        = 8765


# -------------------------------------------------------------------
# Funções de entrada para cada processo filho
# (não podem ser lambdas — multiprocessing exige picklable)
# -------------------------------------------------------------------

def _run_threaded_server(metrics_q):
    # Importa aqui para que o caminho seja resolvido no processo filho
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import projeto.server_threaded as srv
    srv.set_metrics_queue(metrics_q)
    srv.main()


def _run_multiprocess_server(metrics_q):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import projeto.server_multiprocess as srv
    srv.set_metrics_queue(metrics_q)
    srv.main()


def _run_metrics_server(metrics_q, http_port, ws_port):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import projeto.metrics_server as ms
    ms.metrics_queue = metrics_q   # substitui a fila padrão
    ms.start(http_port=http_port, ws_port=ws_port)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def main():
    print("=" * 55)
    print("  TI6 — TCP Benchmark  |  Iniciando serviços...")
    print("=" * 55)

    # Fila de métricas compartilhada entre processos
    metrics_q = multiprocessing.Queue(maxsize=2000)

    processes = []

    # --- Servidor Multithread ---
    p_thread = multiprocessing.Process(
        target=_run_threaded_server,
        args=(metrics_q,),
        name="srv-multithread",
        daemon=True,
    )
    p_thread.start()
    processes.append(p_thread)
    print(f"  ✓ Multithread  iniciado  (PID {p_thread.pid}) → porta {PORT_THREAD}")

    # --- Servidor Multiprocess ---
    p_proc = multiprocessing.Process(
        target=_run_multiprocess_server,
        args=(metrics_q,),
        name="srv-multiprocess",
        daemon=False,
    )
    p_proc.start()
    processes.append(p_proc)
    print(f"  ✓ Multiprocess iniciado  (PID {p_proc.pid}) → porta {PORT_PROCESS}")

    # Aguarda os servidores TCP subirem
    time.sleep(0.8)

    print(f"  ✓ Dashboard disponível em  http://localhost:{PORT_HTTP}")
    print(f"  ✓ WebSocket na porta       {PORT_WS}")
    print("=" * 55)
    print("  Pressione Ctrl+C para encerrar tudo.")
    print("=" * 55)

    # Handler de SIGINT / SIGTERM
    def _shutdown(signum, frame):
        print("\n[launcher] Encerrando todos os processos...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join(timeout=3)
        print("[launcher] Encerrado.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Roda o metrics_server no processo principal (bloqueia até Ctrl+C)
    _run_metrics_server(metrics_q, PORT_HTTP, PORT_WS)


if __name__ == "__main__":
    # Necessário no Windows e no macOS com spawn
    multiprocessing.freeze_support()
    main()
