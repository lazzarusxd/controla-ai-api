-- =============================================================================
-- 12-billing-ledger.sql, tabela tarifária por parceiro, idempotência da
-- consolidação de consumo, retrato tarifário da fatura e trilha de auditoria.
--
-- Complementa o 05-billing.sql, que criou METERING_LOGS e INVOICES sem código
-- que as usasse. Nada aqui recria tabela: tudo é aditivo, para que um volume
-- já inicializado receba a migração sem perder a bilhetagem existente.
-- =============================================================================
SET search_path TO controla_ai, public;

-- -----------------------------------------------------------------------------
-- METERING_LOGS, marca da última consolidação do dia.
-- A linha é incrementada várias vezes ao longo do dia, e created_at sozinho
-- não diz quando o contador foi alimentado pela última vez.
-- -----------------------------------------------------------------------------
ALTER TABLE metering_logs
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NULL;

CREATE TRIGGER tg_metering_logs_updated_at
    BEFORE UPDATE ON metering_logs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS ix_metering_logs_partner_date
    ON metering_logs (partner_id, reference_date DESC);

-- -----------------------------------------------------------------------------
-- METERING_FLUSHES, registro de lotes já aplicados (Idempotent Consumer).
-- Cada lote reivindicado no Redis ganha um identificador. Inserir esse
-- identificador na mesma transação que incrementa METERING_LOGS torna a
-- aplicação exatamente-uma-vez: um lote reprocessado após queda do scheduler
-- colide na chave primária e não é somado de novo.
-- -----------------------------------------------------------------------------
CREATE TABLE metering_flushes (
    flush_id        uuid        NOT NULL,
    partner_id      uuid        NOT NULL,
    reference_date  date        NOT NULL,
    applied_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT pk_metering_flushes         PRIMARY KEY (flush_id),
    CONSTRAINT fk_metering_flushes_partner FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE
);

COMMENT ON TABLE metering_flushes IS
    'Lotes de consumo já incorporados a METERING_LOGS. Existe para impedir dupla contagem na reentrega.';

CREATE INDEX ix_metering_flushes_applied_at ON metering_flushes (partner_id, applied_at);

-- -----------------------------------------------------------------------------
-- PARTNER_PRICING_PLANS, contrato comercial versionado por competência.
-- Preço é atributo do contrato de cada parceiro, não da instância. A vigência
-- por mês permite reajuste sem reescrever faturas passadas: a fatura aponta
-- para a versão aplicada e ainda copia os preços (ver INVOICES abaixo).
-- -----------------------------------------------------------------------------
CREATE TABLE partner_pricing_plans (
    plan_id                        uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id                     uuid          NOT NULL,
    effective_from                 char(7)       NOT NULL,
    base_monthly_fee               numeric(15,2) NOT NULL,
    price_per_thousand_requests    numeric(15,6) NOT NULL,
    price_per_million_tokens_in    numeric(15,6) NOT NULL,
    price_per_million_tokens_out   numeric(15,6) NOT NULL,
    price_per_ocr_image            numeric(15,6) NOT NULL,
    created_at                     timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT pk_partner_pricing_plans          PRIMARY KEY (plan_id),
    CONSTRAINT uq_partner_pricing_plans_version  UNIQUE (partner_id, effective_from),
    CONSTRAINT fk_partner_pricing_plans_partner  FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
    CONSTRAINT ck_partner_pricing_plans_month    CHECK (effective_from ~ '^\d{4}-(0[1-9]|1[0-2])$'),
    CONSTRAINT ck_partner_pricing_plans_prices   CHECK (
        base_monthly_fee >= 0
        AND price_per_thousand_requests  >= 0
        AND price_per_million_tokens_in  >= 0
        AND price_per_million_tokens_out >= 0
        AND price_per_ocr_image          >= 0
    )
);

COMMENT ON TABLE partner_pricing_plans IS
    'Tabela tarifária negociada. Parceiro sem versão vigente é faturado pela tabela de balcão em configuração.';
COMMENT ON COLUMN partner_pricing_plans.effective_from IS
    'Primeira competência (YYYY-MM) em que a versão vale. A vigente é a maior effective_from <= competência.';

-- -----------------------------------------------------------------------------
-- INVOICES, retrato do que foi medido e de quanto custava cada unidade.
-- Sem os volumes e os preços unitários copiados, uma fatura fechada só seria
-- reproduzível enquanto METERING_LOGS e o contrato não mudassem.
-- -----------------------------------------------------------------------------
ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS api_requests                  numeric(20,0) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS llm_tokens_in                 numeric(30,0) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS llm_tokens_out                numeric(30,0) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ocr_images                    numeric(20,0) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS price_per_thousand_requests   numeric(15,6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS price_per_million_tokens_in   numeric(15,6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS price_per_million_tokens_out  numeric(15,6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS price_per_ocr_image           numeric(15,6) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pricing_source                varchar(20)   NOT NULL DEFAULT 'LIST_PRICE',
    ADD COLUMN IF NOT EXISTS pricing_plan_id               uuid          NULL,
    ADD COLUMN IF NOT EXISTS closed_by                     varchar(20)   NULL;

ALTER TABLE invoices
    ADD CONSTRAINT ck_invoices_pricing_source CHECK (pricing_source IN ('CONTRACT', 'LIST_PRICE')),
    ADD CONSTRAINT ck_invoices_closed_by      CHECK (closed_by IS NULL OR closed_by IN ('PARTNER', 'SCHEDULER')),
    ADD CONSTRAINT ck_invoices_volumes        CHECK (
        api_requests >= 0 AND llm_tokens_in >= 0 AND llm_tokens_out >= 0 AND ocr_images >= 0
    ),
    ADD CONSTRAINT ck_invoices_plan_source    CHECK (
        (pricing_source = 'CONTRACT' AND pricing_plan_id IS NOT NULL)
        OR (pricing_source = 'LIST_PRICE' AND pricing_plan_id IS NULL)
    ),
    ADD CONSTRAINT fk_invoices_pricing_plan   FOREIGN KEY (pricing_plan_id)
        REFERENCES partner_pricing_plans (plan_id) ON DELETE SET NULL;

COMMENT ON COLUMN invoices.pricing_plan_id IS
    'Versão do contrato aplicada. Os preços unitários ao lado são cópia, não referência: a fatura sobrevive ao reajuste.';

CREATE INDEX IF NOT EXISTS ix_invoices_closed_history
    ON invoices (partner_id, reference_month DESC)
    WHERE status = 'CLOSED';

-- Fatura fechada é documento emitido. Corrigir exige documento novo, nunca
-- regravação: a trigger cobre inclusive quem tem privilégio de UPDATE.
CREATE OR REPLACE FUNCTION forbid_closed_invoice_changes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'CLOSED' THEN
        RAISE EXCEPTION 'Fatura % já fechada e imutável.', OLD.invoice_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

CREATE TRIGGER tg_invoices_immutable_when_closed
    BEFORE UPDATE OR DELETE ON invoices
    FOR EACH ROW EXECUTE FUNCTION forbid_closed_invoice_changes();

-- -----------------------------------------------------------------------------
-- BILLING_AUDIT_EVENTS, primeira trilha de auditoria em tabela do projeto.
--
-- Até aqui a auditoria foi log estruturado, adequado a dado operacional. A
-- fatura muda o critério: é documento com efeito financeiro, contestável pelo
-- parceiro, e a prova do fechamento precisa nascer na mesma transação que o
-- fechamento. Log escrito depois do COMMIT pode faltar; linha na mesma
-- transação não.
--
-- Sem FK para PARTNERS de propósito: a trilha precisa sobreviver à exclusão do
-- parceiro, que em cascata apaga faturas e consumo.
-- -----------------------------------------------------------------------------
CREATE TABLE billing_audit_events (
    event_id         uuid         NOT NULL DEFAULT uuid_generate_v7(),
    partner_id       uuid         NOT NULL,
    event_type       varchar(40)  NOT NULL,
    actor            varchar(20)  NOT NULL,
    client_id        varchar(128) NULL,
    reference_month  char(7)      NOT NULL,
    invoice_id       uuid         NULL,
    payload          jsonb        NOT NULL DEFAULT '{}'::jsonb,
    occurred_at      timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_billing_audit_events        PRIMARY KEY (event_id),
    CONSTRAINT ck_billing_audit_events_type   CHECK (event_type IN ('invoice.closed', 'invoice.close_replayed')),
    CONSTRAINT ck_billing_audit_events_actor  CHECK (actor IN ('PARTNER', 'SCHEDULER')),
    CONSTRAINT ck_billing_audit_events_month  CHECK (reference_month ~ '^\d{4}-(0[1-9]|1[0-2])$'),
    CONSTRAINT ck_billing_audit_events_client CHECK (actor <> 'PARTNER' OR client_id IS NOT NULL)
);

COMMENT ON TABLE billing_audit_events IS
    'Trilha append-only dos fechamentos de fatura. Gravada na mesma transação do fato auditado.';

CREATE INDEX ix_billing_audit_events_partner
    ON billing_audit_events (partner_id, reference_month, occurred_at DESC);

CREATE OR REPLACE FUNCTION forbid_audit_changes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Trilha de auditoria é somente inclusão.'
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER tg_billing_audit_events_append_only
    BEFORE UPDATE OR DELETE ON billing_audit_events
    FOR EACH ROW EXECUTE FUNCTION forbid_audit_changes();

-- -----------------------------------------------------------------------------
-- RLS nos mesmos termos do 07-rls.sql e do 08-rls-roles.sql.
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    target text;
BEGIN
    FOREACH target IN ARRAY ARRAY['metering_flushes', 'partner_pricing_plans', 'billing_audit_events']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', target);
        EXECUTE format(
            'CREATE POLICY pl_%1$s_tenant ON %1$I
                 USING (partner_id = current_partner_id())
                 WITH CHECK (partner_id = current_partner_id())',
            target
        );
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', target);
    END LOOP;
END;
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON metering_flushes      TO controla_ai_app;
GRANT SELECT                         ON partner_pricing_plans TO controla_ai_app;
GRANT SELECT, INSERT                 ON billing_audit_events  TO controla_ai_app;

REVOKE UPDATE, DELETE ON billing_audit_events  FROM controla_ai_app;
REVOKE INSERT, UPDATE, DELETE ON partner_pricing_plans FROM controla_ai_app;
