"""
Servidor de métricas — WebSocket + HTTP estático.
Recebe snapshots dos dois servidores TCP via fila interna,
distribui para todos os clientes WebSocket conectados,
e serve o dashboard.html na raiz.

Porta: 8888
"""

import asyncio
import json
import queue
import threading
import time
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Tenta usar websockets; fallback para polling puro se não instalado
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# -------------------------------------------------------------------
# Fila de métricas compartilhada (thread-safe)
# Put: servidores TCP → Get: broadcaster WebSocket
# -------------------------------------------------------------------
metrics_queue: queue.Queue = queue.Queue(maxsize=1000)

# Estado mais recente de cada servidor
_latest: dict = {
    "multithread":  None,
    "multiprocess": None,
}

# Clientes WebSocket conectados
_ws_clients: set = set()
_ws_lock = threading.Lock()


# -------------------------------------------------------------------
# Thread que lê a fila e atualiza _latest
# -------------------------------------------------------------------
def _queue_reader():
    while True:
        try:
            server_key, data = metrics_queue.get(timeout=2)
            _latest[server_key] = data
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[metrics] Erro na fila: {e}")


# -------------------------------------------------------------------
# Broadcast assíncrono para todos os clientes WebSocket
# -------------------------------------------------------------------
async def _broadcaster():
    while True:
        await asyncio.sleep(1)
        payload = {
            "multithread":  _latest["multithread"],
            "multiprocess": _latest["multiprocess"],
            "server_time":  time.time(),
        }
        msg = json.dumps(payload)
        dead = set()
        with _ws_lock:
            clients = set(_ws_clients)
        for ws in clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        if dead:
            with _ws_lock:
                _ws_clients.difference_update(dead)


# -------------------------------------------------------------------
# Handler de cada conexão WebSocket
# -------------------------------------------------------------------
async def _ws_handler(websocket):
    with _ws_lock:
        _ws_clients.add(websocket)
    print(f"[ws] Cliente conectado: {websocket.remote_address}")
    try:
        # Manda estado atual imediatamente na conexão
        payload = {
            "multithread":  _latest["multithread"],
            "multiprocess": _latest["multiprocess"],
            "server_time":  time.time(),
        }
        await websocket.send(json.dumps(payload))
        await websocket.wait_closed()
    finally:
        with _ws_lock:
            _ws_clients.discard(websocket)
        print(f"[ws] Cliente desconectado: {websocket.remote_address}")


# -------------------------------------------------------------------
# Servidor HTTP simples para servir o dashboard.html
# -------------------------------------------------------------------
DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"


class _HTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silencia logs de acesso

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ("/", "/dashboard.html"):
            if DASHBOARD_PATH.exists():
                content = DASHBOARD_PATH.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "dashboard.html não encontrado")

        elif path == "/metrics":
            # Endpoint de polling HTTP como fallback (caso WebSocket não funcione)
            payload = {
                "multithread":  _latest["multithread"],
                "multiprocess": _latest["multiprocess"],
                "server_time":  time.time(),
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_error(404)


def _run_http(port=8888):
    from http.server import HTTPServer
    server = HTTPServer(("0.0.0.0", port), _HTTPHandler)
    print(f"[http] Dashboard disponível em http://localhost:{port}")
    server.serve_forever()


# -------------------------------------------------------------------
# Loop asyncio: WebSocket + broadcaster
# -------------------------------------------------------------------
async def _async_main(ws_port=8765):
    broadcaster_task = asyncio.create_task(_broadcaster())
    if HAS_WEBSOCKETS:
        async with websockets.serve(_ws_handler, "0.0.0.0", ws_port):
            print(f"[ws] WebSocket ouvindo na porta {ws_port}")
            await broadcaster_task
    else:
        print("[ws] Módulo 'websockets' não instalado — usando polling HTTP.")
        await broadcaster_task


def start(http_port=8888, ws_port=8765):
    """Chamado pelo launcher para iniciar o servidor de métricas."""
    # Thread leitora da fila
    t = threading.Thread(target=_queue_reader, daemon=True)
    t.start()

    # Thread HTTP (serve o dashboard)
    t2 = threading.Thread(target=_run_http, args=(http_port,), daemon=True)
    t2.start()

    # Loop asyncio no thread principal deste módulo
    asyncio.run(_async_main(ws_port))


if __name__ == "__main__":
    start()
