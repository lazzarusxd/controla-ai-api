# api-controla-ai · Projeto N2 (ESW441)

Fork acadêmico da API **Controla AI** (TFC de João Lázaro) usado no Projeto N2 da disciplina
**ESW441, Desenvolvimento de Software para Persistência** (Turma A, Prof. Gustavo Martins Lima).
As alterações deste repositório valem apenas para a disciplina e não são levadas ao repositório do TFC.

Trio: Enildo Martins de Oliveira Filho, Maria Eduarda Goetz Maia, João Lázaro Faria Bernardes.

| Semana | Entrega | Situação |
|---|---|---|
| 1 | Diagnóstico e baseline | entregue |
| 2 | Modelagem da camada (Redis, Cache-Aside, apagar na escrita, TTL 1 h) | entregue |
| 3 | **Implementação** (este README) | checkpoint |
| 4 | Medição do "depois", durabilidade, trade-offs, vídeo | entrega final em 03/11 |

---

## 1. Problema e decisão

**Dor (Semana 1).** O saldo consolidado (`GET /v1/users/{user_id}/transactions/balance`) é recalculado no
PostgreSQL a cada requisição: quatro `SUM(...) FILTER (...)` sobre todos os lançamentos do usuário no período.
Com 100 mil lançamentos, só a execução dessa agregação levou cerca de 25 ms em um PostgreSQL 16 de
desenvolvimento (`EXPLAIN ANALYZE` sobre a massa de `scripts/seed_benchmark.sql`, varredura sequencial
paralela), e o custo cresce linearmente com o histórico do usuário.

**Caminho (Semana 2).** Chave-valor no Redis como camada de cache, padrão **Cache-Aside** com **apagar na
escrita** e **TTL de 1 hora** como rede de segurança.

## 2. Como a camada funciona

```
                      GET /balance                                 POST | PATCH | DELETE | review
                           │                                                   │
                           ▼                                                   ▼
               CacheAsideTransactionRepository.summarize()       CacheAsideTransactionRepository.create/update/delete()
                           │                                                   │
                 GET balance:{p}:{u}:{ini}:{fim}:{proj}             1. grava no PostgreSQL (fonte da verdade)
                    ┌──────┴───────┐                                2. só se confirmou: EVAL invalidação
                  HIT            MISS                                  (DEL de todas as chaves do índice
                    │              │                                    balance:index:{p}:{u} + DEL do índice)
             devolve cópia   SUM no PostgreSQL
                                   │
                    MULTI  SET chave json EX 3600
                           SADD balance:index:{p}:{u} chave
                           EXPIRE balance:index:{p}:{u} 3600
                    EXEC → devolve resultado
```

| Item | Decisão |
|---|---|
| Estrutura | String com JSON (`SET ... EX 3600`); valores monetários serializados como texto para preservar a precisão de `Decimal` |
| Chave | `balance:{partner_id}:{user_id}:{start_date}:{end_date}:{projection_until}`, parâmetro ausente vira `-` |
| Busca | Chave exata, `GET` em O(1) |
| Índice por usuário | SET `balance:index:{partner_id}:{user_id}` com as chaves vivas, para apagar todas as variações de período em uma escrita |
| Invalidação | Script Lua atômico (`SMEMBERS` + `DEL` em lote + `DEL` do índice), executado **depois** da gravação na fonte da verdade |
| TTL | 3600 s (`BALANCE_CACHE_TTL_SECONDS`), também no índice |
| Falha do Redis | *Fail-open*: erro ou timeout (250 ms) vira MISS e a consulta segue no PostgreSQL; a API nunca cai por causa do cache |
| Esquecimento (LGPD) | A exclusão de conta (`DELETE /v1/users/{user_id}`) também apaga as cópias de saldo do titular |

### Por que a chave mudou em relação à Semana 2

O modelo previa `balance:{user_id}:{month_year}`. Ao implementar, vimos que a rota real não recebe mês: recebe
um período livre (`start_date`, `end_date`) e um horizonte de projeção (`projection_until`). Por isso:

1. **A chave carrega os parâmetros reais**, mantendo o padrão `recurso:identificador:parâmetros`. O caso "mês"
   continua coberto: outubro de 2026 é `...:2026-10-01:2026-10-31:-`.
2. **Entrou o `partner_id`.** O sistema é multi-tenant (B2B2C) e o `user_id` só tem significado sob o parceiro;
   a chave não pode permitir leitura cruzada entre parceiros.
3. **Entrou o índice por usuário.** Como um mesmo usuário pode ter várias chaves (um período por consulta), o
   `DEL` da escrita precisa saber quais apagar. O SET índice preserva a estratégia "apagar na escrita" sem usar
   `KEYS`/`SCAN` no caminho da requisição.

### Onde está no código

O cache foi implementado como **Decorator** (GoF) do port `ITransactionRepository`, respeitando a Clean
Architecture do projeto: casos de uso não mudaram, e todo caminho que grava lançamentos (rotas HTTP, revisão de
OCR, processamento assíncrono de comprovantes no worker) invalida o cache automaticamente.

| Arquivo | Papel |
|---|---|
| `app/application/interfaces/i_consolidated_balance_cache.py` | Port da camada (get, put, invalidate_user) |
| `app/application/services/cache_aside_transaction_repository.py` | Decorator com a lógica Cache-Aside (HIT, MISS, invalidação) |
| `app/infra/cache/consolidated_balance_cache.py` | Adapter Redis: chave, JSON, TTL, índice, script Lua, fail-open |
| `app/infra/repositories/transaction_repository_factory.py` | Composition root: decora o repositório quando `BALANCE_CACHE_ENABLED=true` |
| `app/presentation/api/v1/transactions/dependencies.py`, `.../tax/dependencies.py`, `app/infra/queue/tasks/process_receipt.py` | Passam a usar a factory |
| `app/application/usecases/erasure/erase_account.py`, `.../accounts/dependencies.py` | Purga do saldo em cache na exclusão de conta |
| `app/config/settings.py`, `.env.example` | `BALANCE_CACHE_ENABLED`, `BALANCE_CACHE_TTL_SECONDS`, `BALANCE_CACHE_TIMEOUT_SECONDS` |
| `tests/application/test_balance_cache_aside.py`, `tests/infra/test_consolidated_balance_cache.py` | Testes unitários e de integração com Redis real |
| `scripts/seed_benchmark.sql`, `scripts/benchmark_balance.py` | Massa de dados e medição |

## 3. Como subir e rodar

Pré-requisitos: Docker com Compose v2 e OpenSSL. Os comandos abaixo partem da raiz do repositório.

```bash
# 1. Variáveis de ambiente (em desenvolvimento, para ter o /docs e logs legíveis)
cp .env.example .env
sed -i 's/^APP_ENV=.*/APP_ENV=development/; s/^LOG_LEVEL=.*/LOG_LEVEL=DEBUG/' .env

# 2. Par de chaves do token JWE
bash docker/scripts/generate-jwe-keys.sh

# 3. Servidores (PostgreSQL, Redis) + API + worker, build do zero
#    O compose do fork usa projeto, containers, imagem e volumes próprios (controla-ai-n2*) e as portas
#    8001 (API) e 5433 (PostgreSQL), então não interfere em uma build do projeto original no mesmo Docker.
docker compose build --no-cache --pull
docker compose up -d

# 4. Conferir o Redis (deve responder PONG) e a API
docker compose exec redis redis-cli ping
curl -s http://localhost:8001/health/readiness

# 5. Massa de dados: parceiro, credencial, usuário e 100 mil lançamentos
docker compose exec -T postgres psql -U controlaai -d controlaai -v n=100000 < scripts/seed_benchmark.sql
```

> A credencial criada pelo seed (`esw441-n2-benchmark` / `esw441-n2-benchmark-somente-dev`) é pública por estar
> versionada. Use apenas em banco de desenvolvimento.

**Rodando a API fora do Docker** (com `uv`): suba só o Redis com o comando do enunciado,
`docker run -d --name redis -p 6379:6379 redis:7`, aponte `REDIS_URL=redis://localhost:6379/0` e
`DATABASE_URL` para o seu PostgreSQL no `.env`, e rode `uv sync && uv run python main.py`.

## 4. Demonstração: MISS, HIT e invalidação

```bash
BASE=http://localhost:8001
USER=00000000-0000-7000-8000-000000000442
TOKEN=$(curl -s -u esw441-n2-benchmark:esw441-n2-benchmark-somente-dev \
  -d grant_type=client_credentials $BASE/v1/oauth/token | sed -E 's/.*"access_token":"([^"]+)".*/\1/')

# Em outro terminal, acompanhe os comandos que chegam ao Redis:
docker compose exec redis redis-cli MONITOR

# 1ª leitura: MISS (GET vazio, depois MULTI/SET/SADD/EXPIRE/EXEC)
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/v1/users/$USER/transactions/balance"
# 2ª leitura: HIT (só um GET)
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/v1/users/$USER/transactions/balance"

# O que ficou guardado
docker compose exec redis redis-cli --scan --pattern 'balance:*'
docker compose exec redis redis-cli TTL "balance:00000000-0000-7000-8000-000000000441:$USER:-:-:-"

# Escrita: grava no PostgreSQL e em seguida apaga as cópias (EVAL com DEL)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"type":"EXPENSE","amount":42.50,"status":"SETTLED","category":"Lazer","description":"Cinema","transaction_date":"2026-10-20"}' \
  "$BASE/v1/users/$USER/transactions"

# Próxima leitura volta a ser MISS e já reflete o lançamento novo
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/v1/users/$USER/transactions/balance"
```

Com `LOG_LEVEL=DEBUG`, os logs da API (`docker compose logs -f api`) mostram os eventos `balance_cache_miss`,
`balance_cache_hit` e `balance_cache_invalidated`.

## 5. Medição (prévia da Semana 4)

O baseline da Semana 1 mediu a rota `/health`, que não toca o banco. Para comparar antes e depois de forma
justa, medimos **a rota de saldo** com o mesmo binário, só alternando a flag:

```bash
# "Antes": cache desligado
sed -i 's/^BALANCE_CACHE_ENABLED=.*/BALANCE_CACHE_ENABLED=false/' .env && docker compose up -d api
python3 scripts/benchmark_balance.py --requests 1000 --label sem-cache --csv resultados.csv

# "Depois": cache ligado
sed -i 's/^BALANCE_CACHE_ENABLED=.*/BALANCE_CACHE_ENABLED=true/' .env && docker compose up -d api
python3 scripts/benchmark_balance.py --requests 1000 --label com-cache --csv resultados.csv

# Cenário com escrita: um lançamento a cada 50 leituras (taxa de acerto esperada de 98%)
python3 scripts/benchmark_balance.py --requests 1000 --write-every 50 --label com-cache-escrita --csv resultados.csv
```

O script usa só a biblioteca padrão do Python, reporta tempo total, médio, p50/p95/p99 e vazão, e acrescenta
uma linha por cenário ao CSV. Para isolar o efeito do cache, mantenha `GUNICORN_WORKERS` e a máquina iguais
entre as execuções.

## 6. Testes

```bash
uv sync
uv run pytest
```

Os testes de integração do adapter (`tests/infra/test_consolidated_balance_cache.py`) usam um Redis real em
`redis://localhost:6379/15` (banco lógico separado, limpo a cada teste) e são ignorados se ele não estiver no ar.
Para apontar para outro servidor: `REDIS_TEST_URL=redis://host:6379/15 uv run pytest`.

Cobertura da camada: MISS popula, HIT não toca a fonte, períodos são independentes, escrita grava antes de
invalidar, falha na escrita não invalida, invalidação apaga só o usuário certo (nem outro usuário, nem o mesmo
usuário sob outro parceiro), TTL aplicado na chave e no índice, `Decimal` preservado, JSON corrompido vira MISS,
Redis fora do ar vira MISS sem exceção, e exclusão de conta purga o cache.

## 7. Limitações conhecidas (insumo para a Semana 4)

- **Corrida clássica do Cache-Aside.** Se uma leitura em MISS calcular o saldo antes de uma escrita e gravar a
  cópia depois do `DEL`, a cópia velha sobrevive até o TTL. A janela é de milissegundos e o TTL de 1 h limita o
  pior caso; reduzir o TTL troca consistência por mais idas ao banco.
- **Durabilidade.** O cache é dado derivado: perder o Redis só custa MISS. O compose já usa AOF com
  `appendfsync everysec` e `maxmemory-policy volatile-lru`; como toda chave de saldo tem TTL, ela é elegível a
  despejo sob pressão de memória, enquanto chaves sem TTL (filas, contadores de faturamento) ficam protegidas.
- **Redis Cluster.** O script de invalidação apaga chaves que não declara em `KEYS`, o que funciona em instância
  única (o caso do projeto). Em cluster seria preciso hash tags para manter as chaves do usuário no mesmo slot.
