import csv
import sys
import json
import time
import random
import base64
import argparse
import statistics
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta, timezone


DEFAULT_CLIENT_ID = "esw441-n2-benchmark"
DEFAULT_USER_ID = "00000000-0000-7000-8000-000000000442"
DEFAULT_CLIENT_SECRET = "esw441-n2-benchmark-somente-dev"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mede a latência da rota de saldo consolidado.")
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    parser.add_argument("--client-secret", default=DEFAULT_CLIENT_SECRET)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--requests", type=int, default=1000, help="Quantidade de leituras medidas (N).")
    parser.add_argument("--warmup", type=int, default=0, help="Leituras descartadas antes da medição.")
    parser.add_argument("--write-every", type=int, default=0, help="Cadastra um lançamento a cada K leituras.")
    parser.add_argument("--start-date", default=None, help="Filtro start_date (AAAA-MM-DD).")
    parser.add_argument("--end-date", default=None, help="Filtro end_date (AAAA-MM-DD).")
    parser.add_argument("--projection-until", default=None, help="Filtro projection_until (AAAA-MM-DD).")
    parser.add_argument("--label", default="medicao", help="Rótulo do cenário, gravado no CSV.")
    parser.add_argument(
        "--mode",
        default="repeat",
        choices=["repeat", "miss"],
        help="repeat: sempre a mesma consulta (com cache, 1 MISS e N-1 HIT). miss: consulta inédita a cada leitura."
    )
    parser.add_argument("--csv", default=None, help="Arquivo CSV onde acrescentar o resultado.")
    parser.add_argument("--timeout", type=float, default=30.0)

    return parser.parse_args()


def request_json(
        url: str,
        method: str,
        timeout: float,
        headers: Dict[str, str],
        body: Optional[bytes] = None
) -> Dict[str, Any]:
    request = urllib.request.Request(url=url, data=body, method=method, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} falhou com HTTP {exc.code}: {detail}") from exc

    return json.loads(payload) if payload else {}


def issue_token(arguments: argparse.Namespace) -> str:
    basic = base64.b64encode(f"{arguments.client_id}:{arguments.client_secret}".encode()).decode()
    token = request_json(
        method="POST",
        timeout=arguments.timeout,
        url=f"{arguments.base_url}/v1/oauth/token",
        body=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}
    )

    return str(token["access_token"])


def balance_url(arguments: argparse.Namespace, projection_until: Optional[str] = None) -> str:
    query = {
        key: value for key, value in (
            ("start_date", arguments.start_date),
            ("end_date", arguments.end_date),
            ("projection_until", projection_until or arguments.projection_until)
        ) if value
    }
    suffix = f"?{urllib.parse.urlencode(query)}" if query else ""

    return f"{arguments.base_url}/v1/users/{arguments.user_id}/transactions/balance{suffix}"


def create_transaction(arguments: argparse.Namespace, headers: Dict[str, str], sequence: int) -> None:
    request_json(
        method="POST",
        timeout=arguments.timeout,
        headers={**headers, "Content-Type": "application/json"},
        url=f"{arguments.base_url}/v1/users/{arguments.user_id}/transactions",
        body=json.dumps(
            {
                "amount": 10.00,
                "type": "EXPENSE",
                "status": "SETTLED",
                "category": "Benchmark",
                "description": f"Escrita de invalidação #{sequence}",
                "transaction_date": date.today().isoformat()
            }
        ).encode()
    )


def percentile(samples: List[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))

    return ordered[index]


def main() -> int:
    arguments = parse_arguments()

    if arguments.requests <= 0:
        raise SystemExit("--requests deve ser maior que zero.")

    headers = {"Authorization": f"Bearer {issue_token(arguments)}", "Accept": "application/json"}
    url = balance_url(arguments)

    for _ in range(arguments.warmup):
        request_json(url=url, method="GET", headers=headers, timeout=arguments.timeout)

    writes = 0
    samples_ms: List[float] = []
    started = time.perf_counter()

    miss_base = date(2200, 1, 1) + timedelta(days=random.randint(0, 2_000_000))

    for index in range(arguments.requests):
        if arguments.write_every > 0 and index > 0 and index % arguments.write_every == 0:
            writes += 1
            create_transaction(arguments=arguments, headers=headers, sequence=writes)

        target = url

        if arguments.mode == "miss":
            target = balance_url(arguments, projection_until=(miss_base + timedelta(days=index)).isoformat())

        before = time.perf_counter()
        request_json(url=target, method="GET", headers=headers, timeout=arguments.timeout)
        samples_ms.append((time.perf_counter() - before) * 1000)

    total_seconds = time.perf_counter() - started

    result = {
        "label": arguments.label,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requests": arguments.requests,
        "writes": writes,
        "total_s": round(total_seconds, 3),
        "mean_ms": round(statistics.fmean(samples_ms), 3),
        "p50_ms": round(percentile(samples_ms, 0.50), 3),
        "p95_ms": round(percentile(samples_ms, 0.95), 3),
        "p99_ms": round(percentile(samples_ms, 0.99), 3),
        "min_ms": round(min(samples_ms), 3),
        "max_ms": round(max(samples_ms), 3),
        "req_per_s": round(arguments.requests / total_seconds, 1)
    }

    print(f"\nCenário: {result['label']} (modo {arguments.mode})  |  {url}")
    print(f"N = {result['requests']} leituras, {result['writes']} escritas intercaladas")
    print(f"Tempo total ........ {result['total_s']} s")
    print(f"Tempo médio ........ {result['mean_ms']} ms")
    print(f"p50 / p95 / p99 .... {result['p50_ms']} / {result['p95_ms']} / {result['p99_ms']} ms")
    print(f"mín / máx .......... {result['min_ms']} / {result['max_ms']} ms")
    print(f"Vazão .............. {result['req_per_s']} req/s")

    if arguments.csv:
        path = Path(arguments.csv)
        is_new = not path.exists()

        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result.keys()))

            if is_new:
                writer.writeheader()

            writer.writerow(result)

        print(f"Resultado acrescentado a {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
