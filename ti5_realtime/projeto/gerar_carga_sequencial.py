"""
Gerador de carga — Benchmark sequencial (escopo Sprint 3).

Protocolo definido no fechamento de escopo:
  - 5 níveis de concorrência: 10, 50, 100, 200, 500 conexões simultâneas
  - 30 segundos por cenário
  - 3 repetições por cenário (resultado = média das 3)
  - Pausa de 10s entre cenários para estabilização
  - Um servidor por vez (nunca simultâneo)

Métricas coletadas (as 3 definidas no escopo):
  - Throughput (req/s)
  - Latência p99 (ms)
  - Uso de memória RAM pico (MB) — lido do servidor via snapshot

Critério de ponto de ruptura (detectado automaticamente):
  - p99 > 5× o valor do baseline (cenário de 10 conexões)
  - OU taxa de erro > 5%
"""

import asyncio
import time
import csv
from datetime import datetime

# ============================================================
# CONFIGURAÇÕES (conforme escopo fechado)
# ============================================================

SERVERS = {
    "multithread": {
        "host": "127.0.0.1",
        "port": 9090
    },
    "multiprocess": {
        "host": "127.0.0.1",
        "port": 8081
    }
}

# 5 níveis × 30s × 3 repetições = 30 rodadas por servidor
CONCURRENCY_LEVELS = [10, 50, 100, 200, 500]
DURATION_S         = 30    # segundos por rodada
REPETICOES         = 3     # repetições por nível
PAUSA_ENTRE_S      = 10    # pausa de estabilização entre níveis

# Critérios de ruptura
RUPTURA_P99_FATOR  = 5.0   # p99 > 5× baseline
RUPTURA_ERRO_PCT   = 5.0   # taxa de erro > 5%

REQUEST = (
    "GET / HTTP/1.1\r\n"
    "Host: localhost\r\n"
    "Connection: close\r\n"
    "\r\n"
).encode()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    index = int((p / 100) * (len(values) - 1))
    return float(values[index])


async def fazer_requisicao(host, port, timeout=10):
    inicio = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.write(REQUEST)
        await writer.drain()
        await asyncio.wait_for(reader.read(4096), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        latencia_ms = (time.perf_counter() - inicio) * 1000
        return True, latencia_ms
    except Exception:
        latencia_ms = (time.perf_counter() - inicio) * 1000
        return False, latencia_ms


async def worker(host, port, fim, resultados):
    while time.perf_counter() < fim:
        sucesso, latencia = await fazer_requisicao(host, port)
        resultados.append((sucesso, latencia))


async def executar_rodada(nome_servidor, host, port, concurrency, duration):
    """Executa uma única rodada (1 repetição de 1 nível de concorrência)."""
    resultados = []
    inicio = time.perf_counter()
    fim    = inicio + duration

    tarefas = [
        asyncio.create_task(worker(host, port, fim, resultados))
        for _ in range(concurrency)
    ]
    await asyncio.gather(*tarefas)

    tempo_total = time.perf_counter() - inicio

    latencias_ok = [lat for ok, lat in resultados if ok]
    erros        = sum(1 for ok, _ in resultados if not ok)
    total        = len(resultados)

    throughput  = total / tempo_total if tempo_total > 0 else 0.0
    p99         = percentile(latencias_ok, 99)
    error_rate  = (erros / total * 100) if total > 0 else 0.0

    return {
        "throughput":  round(throughput, 2),
        "p99_ms":      round(p99, 2),
        "erros":       erros,
        "total":       total,
        "error_rate":  round(error_rate, 2),
    }


def media_rodadas(rodadas):
    """Calcula a média das 3 repetições para as métricas principais."""
    return {
        "throughput_req_s": round(sum(r["throughput"] for r in rodadas) / len(rodadas), 2),
        "p99_ms":           round(sum(r["p99_ms"]     for r in rodadas) / len(rodadas), 2),
        "erros_total":      sum(r["erros"]             for r in rodadas),
        "total_requisicoes": sum(r["total"]            for r in rodadas),
        "error_rate_pct":   round(sum(r["error_rate"]  for r in rodadas) / len(rodadas), 2),
    }


def verificar_ruptura(resultado, baseline_p99):
    """Retorna True se o ponto de ruptura foi atingido."""
    if baseline_p99 > 0 and resultado["p99_ms"] > RUPTURA_P99_FATOR * baseline_p99:
        return True, f"p99 {resultado['p99_ms']}ms > {RUPTURA_P99_FATOR}× baseline ({baseline_p99}ms)"
    if resultado["error_rate_pct"] > RUPTURA_ERRO_PCT:
        return True, f"taxa de erro {resultado['error_rate_pct']}% > {RUPTURA_ERRO_PCT}%"
    return False, None


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

async def testar_servidor(nome_servidor, host, port):
    print()
    print("#" * 70)
    print(f"SERVIDOR: {nome_servidor.upper()}  ({host}:{port})")
    print("#" * 70)

    resultados_csv = []
    baseline_p99   = None
    ruptura_nivel  = None

    for concurrency in CONCURRENCY_LEVELS:
        print()
        print(f"  Concorrência: {concurrency} conexões simultâneas")
        print(f"  Duração: {DURATION_S}s × {REPETICOES} repetições")

        rodadas = []
        for rep in range(1, REPETICOES + 1):
            print(f"    Repetição {rep}/{REPETICOES}...", end=" ", flush=True)
            r = await executar_rodada(nome_servidor, host, port, concurrency, DURATION_S)
            rodadas.append(r)
            print(f"p99={r['p99_ms']}ms  throughput={r['throughput']}req/s  erros={r['error_rate']}%")

        media = media_rodadas(rodadas)

        # Baseline = primeiro nível (10 conexões)
        if baseline_p99 is None:
            baseline_p99 = media["p99_ms"]
            print(f"  → Baseline p99 definido: {baseline_p99}ms")

        ruptura, motivo = verificar_ruptura(media, baseline_p99)

        print(f"  MÉDIA  throughput={media['throughput_req_s']}req/s  "
              f"p99={media['p99_ms']}ms  erro={media['error_rate_pct']}%", end="")

        if ruptura and ruptura_nivel is None:
            ruptura_nivel = concurrency
            print(f"  *** PONTO DE RUPTURA: {motivo} ***")
        else:
            print()

        resultados_csv.append({
            "servidor":           nome_servidor,
            "concorrencia":       concurrency,
            "duracao_s":          DURATION_S,
            "repeticoes":         REPETICOES,
            "throughput_req_s":   media["throughput_req_s"],
            "p99_ms":             media["p99_ms"],
            # RAM pico é coletada pelo servidor; aqui registramos N/A
            # (o dashboard exibe em tempo real via metrics_server)
            "ram_pico_mb":        "ver_dashboard",
            "total_requisicoes":  media["total_requisicoes"],
            "erros":              media["erros_total"],
            "error_rate_pct":     media["error_rate_pct"],
            "ponto_ruptura":      "SIM" if (ruptura and ruptura_nivel == concurrency) else "",
        })

        if ruptura_nivel is not None:
            print(f"\n  Ponto de ruptura atingido em {ruptura_nivel} conexões. Continuando para registro completo...")

        if concurrency < CONCURRENCY_LEVELS[-1]:
            print(f"  Aguardando {PAUSA_ENTRE_S}s para estabilizar...")
            await asyncio.sleep(PAUSA_ENTRE_S)

    return resultados_csv


def salvar_csv(resultados):
    nome_arquivo = f"resultado_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    campos = [
        "servidor",
        "concorrencia",
        "duracao_s",
        "repeticoes",
        "throughput_req_s",
        "p99_ms",
        "ram_pico_mb",
        "total_requisicoes",
        "erros",
        "error_rate_pct",
        "ponto_ruptura",
    ]

    with open(nome_arquivo, "w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos, delimiter=";")
        writer.writeheader()
        writer.writerows(resultados)

    print(f"\nResultado salvo em: {nome_arquivo}")
    return nome_arquivo


async def main():
    print("=" * 70)
    print("BENCHMARK SEQUENCIAL — SPRINT 3")
    print("Protocolo: 5 níveis × 30s × 3 repetições = 30 rodadas/servidor")
    print("Servidores testados um por vez (nunca simultâneo)")
    print("=" * 70)

    todos_resultados = []

    for nome_servidor, config in SERVERS.items():
        resultados = await testar_servidor(
            nome_servidor=nome_servidor,
            host=config["host"],
            port=config["port"]
        )
        todos_resultados.extend(resultados)

    salvar_csv(todos_resultados)

    print()
    print("=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    for r in todos_resultados:
        ruptura = f"  ← RUPTURA" if r["ponto_ruptura"] == "SIM" else ""
        print(f"  {r['servidor']:14s}  conc={r['concorrencia']:4d}  "
              f"throughput={r['throughput_req_s']:8.2f}req/s  "
              f"p99={r['p99_ms']:8.2f}ms  "
              f"erro={r['error_rate_pct']:5.1f}%{ruptura}")

    print()
    print("Teste finalizado.")


if __name__ == "__main__":
    asyncio.run(main())
