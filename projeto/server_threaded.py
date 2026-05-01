import socket
import threading
import time

# Configurações do servidor
HOST = '0.0.0.0'
PORT = 8080
IO_SLEEP_TIME = 0.05  # 50ms simulando I/O-bound

def handle_client(client_socket, address):
    try:
        # Recebe a requisição (limitado para simplificar)
        request = client_socket.recv(1024).decode('utf-8')
        
        # Simula operação I/O-bound (50ms)
        time.sleep(IO_SLEEP_TIME)
        
        # Resposta HTTP padrão conforme o PDF
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 13\r\n\r\nHello, World!"
        client_socket.sendall(response.encode('utf-8'))
    except Exception as e:
        print(f"Erro ao lidar com {address}: {e}")
    finally:
        client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5000)  # Fila de espera alta para suportar carga
    
    print(f"Servidor Multithread rodando em {HOST}:{PORT}")
    
    try:
        while True:
            client_sock, address = server_socket.accept()
            # Cria uma nova thread para cada conexão
            client_thread = threading.Thread(target=handle_client, args=(client_sock, address))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
