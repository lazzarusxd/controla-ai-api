-- =============================================================================
-- 08-rls-roles.sql, papel de aplicação e correção do escopo da RLS
--
-- Corrige duas condições que tornavam o 07-rls.sql inoperante:
--
-- 1. Políticas em CREDENTIALS e REFRESH_TOKENS. Ambas filtram por
--    partner_id = current_partner_id(), mas são consultadas na autenticação,
--    momento em que o partner_id ainda é desconhecido, porque descobri-lo é o
--    próprio objetivo da consulta. O isolamento dessas tabelas é garantido pelo
--    client_id na cláusula WHERE, não pela RLS.
--
-- 2. Ausência de FORCE ROW LEVEL SECURITY. O PostgreSQL dispensa o dono da tabela
--    das políticas por padrão; se a API conectasse com o papel que criou o schema,
--    a RLS seria decorativa.
-- =============================================================================
SET search_path TO controla_ai, public;

DROP POLICY IF EXISTS pl_credentials_tenant   ON credentials;
DROP POLICY IF EXISTS pl_refresh_tokens_tenant ON refresh_tokens;

ALTER TABLE credentials    DISABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens DISABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- Papel de aplicação: sem BYPASSRLS, sem propriedade de tabela.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'controla_ai_app') THEN
        EXECUTE format(
            'CREATE ROLE controla_ai_app LOGIN PASSWORD %L NOBYPASSRLS',
            current_setting('controla_ai.app_password', true)
        );
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA controla_ai TO controla_ai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA controla_ai TO controla_ai_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA controla_ai TO controla_ai_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA controla_ai
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO controla_ai_app;

-- -----------------------------------------------------------------------------
-- FORCE aplica as políticas inclusive ao dono da tabela.
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    target text;
BEGIN
    FOREACH target IN ARRAY ARRAY[
        'users', 'receipts', 'transactions', 'subscriptions', 'assets',
        'goals', 'tax_deductions', 'metering_logs', 'invoices', 'vector_embeddings'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', target);
    END LOOP;
END;
$$;
