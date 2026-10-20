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

## 5. Medição: ficha de resultados

Com cache, a leitura repetida do saldo ficou **3,6× mais rápida na média** (37,3 ms para 10,4 ms) e 5,0× na
mediana. Ganho = tempo antes ÷ tempo depois. Dados brutos em [`resultados.csv`](resultados.csv).

| Operação (GET /balance, N = 1000) | Antes, sem cache | Depois, com cache | Ganho |
|---|---|---|---|
| Leitura repetida, HIT: média | 37,3 ms | 10,4 ms | ~3,6× |
| Leitura repetida, HIT: mediana (p50) | 31,2 ms | 6,3 ms | ~5,0× |
| Leitura repetida, HIT: p95 | 51,5 ms | 26,0 ms | ~2,0× |
| Vazão | 26,8 req/s | 96,5 req/s | ~3,6× |
| Primeira leitura, MISS: média | 37,3 ms | 39,1 ms | ~0,95× (5% mais lento) |
| 1 escrita a cada 50 leituras: média | 37,3 ms | 10,2 ms (19 escritas, ~98% de HIT) | ~3,7× |

**Condições.** Mesma máquina (AMD Ryzen 7 5700X, 32 GB DDR4, Windows com Docker Desktop/WSL2), mesmos dados
(100.000 lançamentos de `scripts/seed_benchmark.sql`, semente fixa), mesmo N (1.000 requisições sequenciais por
cenário, sem aquecimento) e mesmo binário: entre o antes e o depois só muda `BALANCE_CACHE_ENABLED`. O cliente
mede a requisição HTTP completa, incluindo autenticação. Medido em 20/10/2026.

**Leitura dos números.**

- **O cache tirou o banco do caminho.** A economia média foi de 26,9 ms por requisição, o que bate com os
  cerca de 25 ms que a agregação leva dentro do PostgreSQL com 100 mil lançamentos (`EXPLAIN ANALYZE`).
- **Por que ~3,6× e não ~30×.** Mesmo em HIT, cada chamada ainda paga autenticação (decifrar o token JWE),
  middleware e HTTP. Esse custo fixo vira o piso do tempo com cache.
- **MISS.** Ficou 1,9 ms mais lento que o antes: repete a agregação e ainda paga um GET vazio e a gravação da
  cópia no Redis.
- **Escrita não anula o ganho.** Com 1 escrita a cada 50 leituras houve 20 MISS em 1000 leituras, e a média
  das leituras continuou em 10,2 ms.
- **Baseline da Semana 1.** Aquela medição (3,07 ms) foi na rota `/health`, que não consulta o banco, e por
  isso não serve de comparação. O "antes" acima foi medido na rota de saldo, nas mesmas condições do "depois".

### Como reproduzir

```bash
# "Antes": BALANCE_CACHE_ENABLED=false no .env
docker compose up -d api
python3 scripts/benchmark_balance.py --requests 1000 --label sem-cache --csv resultados.csv

# "Depois": BALANCE_CACHE_ENABLED=true no .env
docker compose up -d api
python3 scripts/benchmark_balance.py --requests 1000 --label com-cache --csv resultados.csv          # HIT
python3 scripts/benchmark_balance.py --requests 1000 --mode miss --label miss --csv resultados.csv   # só MISS
python3 scripts/benchmark_balance.py --requests 1000 --write-every 50 --label com-cache-escrita --csv resultados.csv
```

No Windows (CMD), troque `python3` por `py` e as barras por `\` (`py scripts\benchmark_balance.py ...`). O
`--mode miss` usa um `projection_until` inédito a cada leitura: o saldo devolvido é o mesmo, mas a chave é nova
e toda leitura vira MISS. O script usa só a biblioteca padrão do Python.

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

## 7. Durabilidade, trade-offs e limites

- **Trade-off.** Ganhamos leitura rápida e menos carga no PostgreSQL. Pagamos memória no Redis, a complexidade
  de invalidar em todo ponto de escrita (resolvida aqui com um decorator do repositório) e um risco pequeno de
  dado velho, descrito no item seguinte.
- **Corrida clássica do Cache-Aside.** Se uma leitura em MISS calcular o saldo antes de uma escrita e gravar a
  cópia depois do `DEL`, a cópia velha sobrevive até o TTL. A janela é de milissegundos e o TTL de 1 h limita o
  pior caso; reduzir o TTL troca consistência por mais idas ao banco.
- **Durabilidade.** O cache é dado derivado: perder o Redis só custa MISS. O compose já usa AOF com
  `appendfsync everysec` e `maxmemory-policy volatile-lru`; como toda chave de saldo tem TTL, ela é elegível a
  despejo sob pressão de memória, enquanto chaves sem TTL (filas, contadores de faturamento) ficam protegidas.
- **Redis Cluster.** O script de invalidação apaga chaves que não declara em `KEYS`, o que funciona em instância
  única (o caso do projeto). Em cluster seria preciso hash tags para manter as chaves do usuário no mesmo slot.
- **Quando o cache não ajudaria.** Dado que muda a cada leitura (toda leitura viraria MISS, 5% mais lenta),
  baixa releitura (cada usuário consultando o saldo uma vez só) e exigência de exatidão absoluta em tempo real,
  sem tolerar nem a janela da corrida acima.
