import threading
import requests
import time
import math

# --- CONFIGURAÇÃO ---
URL_THREAD  = "http://localhost:9090" 
URL_PROCESS = "http://localhost:8081"

def enviar_rajada(url, conexoes ):
    threads = []
    
    # Função interna para tratar erros de conexão individualmente
    def fazer_request():
        try:
            # Timeout de 2s para não travar o script se o servidor demorar
            requests.get(url, timeout=2)
        except Exception:
            # Ignora erros de conexão (como o WinError 10054) e continua o teste
            pass

    for _ in range(conexoes):
        t = threading.Thread(target=fazer_request)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()

def stress_test():
    print("=== Iniciando Stress Test Dinâmico ===")
    
    # Configurações das rajadas
    rajadas = 10
    conexoes_iniciais = 50
    intervalo_inicial = 2.0 # segundos
    
    for i in range(1, rajadas + 1):
        # Aumenta conexões e diminui intervalo exponencialmente
        conexoes = conexoes_iniciais * i
        intervalo = intervalo_inicial / math.sqrt(i)
        
        print(f"Rajada {i}: Enviando {conexoes} conexões simultâneas (Intervalo: {intervalo:.2f}s)")
        
        # Dispara para ambos os servidores em paralelo
        t1 = threading.Thread(target=enviar_rajada, args=(URL_THREAD, conexoes))
        t2 = threading.Thread(target=enviar_rajada, args=(URL_PROCESS, conexoes))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Espera o intervalo calculado antes da próxima rajada
        time.sleep(intervalo)

    print("=== Stress Test Finalizado ===")

if __name__ == "__main__":
    stress_test()
