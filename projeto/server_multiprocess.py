import socket
import multiprocessing
import time
import os

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 8081  # Porta diferente para evitar conflito se rodar simultaneamente
IO_SLEEP_TIME = 0.05  # 50ms simulando I/O-bound

def handle_client(client_socket, address):
    try:
        # Recebe a requisição
        request = client_socket.recv(1024).decode('utf-8')
        
        # Simula operação I/O-bound (50ms)
        time.sleep(IO_SLEEP_TIME)
        
        # Resposta HTTP padrão
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 13\r\n\r\nHello, World!"
        client_socket.sendall(response.encode('utf-8'))
    except Exception as e:
        pass # Silencioso em multiprocess para evitar poluição de log
    finally:
        client_socket.close()
        # Em multiprocessamento via fork, o processo filho deve terminar
        os._exit(0)

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5000)
    
    print(f"Servidor Multiprocess rodando em {HOST}:{PORT}")
    
    try:
        while True:
            client_sock, address = server_socket.accept()
            # Cria um novo processo para cada conexão (modelo fork)
            process = multiprocessing.Process(target=handle_client, args=(client_sock, address))
            process.daemon = True
            process.start()
            # Fecha o socket no processo pai
            client_sock.close()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
