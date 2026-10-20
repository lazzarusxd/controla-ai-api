-- =============================================================================
-- seed_benchmark.sql, massa de dados do Projeto N2 (ESW441), SOMENTE DESENVOLVIMENTO
--
-- Cria um parceiro, uma credencial OAuth e um usuário com identificadores fixos, e gera
-- :n lançamentos (padrão 100000) para que a agregação do saldo consolidado tenha custo
-- real no PostgreSQL. Idempotente: rodar de novo recria apenas os lançamentos.
--
-- Uso (na raiz do projeto, com o compose no ar):
--   docker compose exec -T postgres psql -U controlaai -d controlaai -v n=100000 < scripts/seed_benchmark.sql
--
-- Credencial gerada (client_credentials, RFC 6749 §4.4):
--   client_id     = esw441-n2-benchmark
--   client_secret = esw441-n2-benchmark-somente-dev
-- O hash abaixo é Argon2id no formato PHC, com os mesmos parâmetros do Argon2SecretHasher
-- (m=19456, t=2, p=1). Este segredo é público por estar versionado: NUNCA rode este
-- arquivo em um banco que não seja de desenvolvimento.
-- =============================================================================
\set ON_ERROR_STOP on

\if :{?n}
\else
    \set n 100000
\endif

SET search_path TO controla_ai, public;

BEGIN;

-- RLS com FORCE: mesmo o dono das tabelas só enxerga e grava linhas do parceiro corrente.
SELECT set_config('app.partner_id', '00000000-0000-7000-8000-000000000441', true) AS _partner \gset

INSERT INTO partners (partner_id, name)
VALUES ('00000000-0000-7000-8000-000000000441', 'ESW441 N2 Benchmark')
ON CONFLICT (partner_id) DO NOTHING;

INSERT INTO credentials (client_id, client_secret_hash, partner_id)
VALUES (
    'esw441-n2-benchmark',
    '$argon2id$v=19$m=19456,t=2,p=1$4nMcC6wAO3W5J7qi7JyKhQ$bh2+GIt5IxH4DyQ+yODLpwVTYogYnF4EfSCWbH0YjvE',
    '00000000-0000-7000-8000-000000000441'
)
ON CONFLICT (client_id) DO NOTHING;

INSERT INTO users (user_id, partner_id, name, email)
VALUES (
    '00000000-0000-7000-8000-000000000442',
    '00000000-0000-7000-8000-000000000441',
    'Usuário de Benchmark',
    'benchmark@esw441.dev'
)
ON CONFLICT (user_id) DO NOTHING;

DELETE FROM transactions
WHERE partner_id = '00000000-0000-7000-8000-000000000441'
    AND user_id = '00000000-0000-7000-8000-000000000442';

-- Distribuição: ~30% receitas, ~70% despesas; ~85% liquidadas, ~15% em aberto com vencimento.
-- Datas espalhadas pelos últimos 730 dias. setseed torna a massa reprodutível entre execuções.
SELECT setseed(0.441) AS _seed \gset

INSERT INTO transactions (
    partner_id,
    user_id,
    type,
    amount,
    category,
    description,
    transaction_date,
    due_date,
    status
)
SELECT
    '00000000-0000-7000-8000-000000000441',
    '00000000-0000-7000-8000-000000000442',
    CASE WHEN r.kind < 0.30 THEN 'INCOME' ELSE 'EXPENSE' END,
    round((1 + random() * 1999)::numeric, 2),
    (ARRAY['Alimentação', 'Moradia', 'Transporte', 'Saúde', 'Educação', 'Lazer', 'Salário', 'Investimentos'])
        [1 + floor(random() * 8)::int],
    'Lançamento sintético #' || g,
    r.day,
    CASE WHEN r.state < 0.15 THEN r.day + 30 END,
    CASE WHEN r.state < 0.15 THEN 'PENDING' ELSE 'SETTLED' END
FROM generate_series(1, :n) AS g
CROSS JOIN LATERAL (
    SELECT
        random() AS kind,
        random() AS state,
        (current_date - floor(random() * 730)::int) AS day,
        g AS anchor
) AS r;

COMMIT;

ANALYZE transactions;

SELECT set_config('app.partner_id', '00000000-0000-7000-8000-000000000441', false) AS _partner \gset

SELECT count(*) AS lancamentos_gerados
FROM transactions
WHERE user_id = '00000000-0000-7000-8000-000000000442';
