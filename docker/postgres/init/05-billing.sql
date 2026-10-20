-- =============================================================================
-- 05-billing.sql, bilhetagem por consumo e faturamento (RF012, RN013)
-- =============================================================================
SET search_path TO controla_ai, public;

-- -----------------------------------------------------------------------------
-- METERING_LOGS, consolidação diária do consumo por parceiro
-- -----------------------------------------------------------------------------
CREATE TABLE metering_logs (
    log_id          uuid           NOT NULL DEFAULT uuid_generate_v7(),
    partner_id      uuid           NOT NULL,
    reference_date  date           NOT NULL,
    api_requests    numeric(10,0)  NOT NULL DEFAULT 0,
    llm_tokens_in   numeric(30,0)  NOT NULL DEFAULT 0,
    llm_tokens_out  numeric(30,0)  NOT NULL DEFAULT 0,
    ocr_images      numeric(20,0)  NOT NULL DEFAULT 0,
    created_at      timestamptz    NOT NULL DEFAULT now(),

    CONSTRAINT pk_metering_logs         PRIMARY KEY (log_id),
    CONSTRAINT uq_metering_logs_period  UNIQUE (partner_id, reference_date),
    CONSTRAINT fk_metering_logs_partner FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
    CONSTRAINT ck_metering_logs_counters CHECK (
        api_requests   >= 0
        AND llm_tokens_in  >= 0
        AND llm_tokens_out >= 0
        AND ocr_images     >= 0
    )
);

COMMENT ON TABLE metering_logs IS
    'Consumo diário consolidado por parceiro; base de cálculo da fatura mensal (RN013).';

-- -----------------------------------------------------------------------------
-- INVOICES, fatura mensal do parceiro
-- -----------------------------------------------------------------------------
CREATE TABLE invoices (
    invoice_id      uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id      uuid          NOT NULL,
    reference_month char(7)       NOT NULL,
    base_fee        numeric(15,2) NOT NULL DEFAULT 0,
    api_fee         numeric(15,2) NOT NULL DEFAULT 0,
    llm_fee         numeric(15,2) NOT NULL DEFAULT 0,
    ocr_fee         numeric(15,2) NOT NULL DEFAULT 0,
    total           numeric(15,2) NOT NULL DEFAULT 0,
    status          varchar(20)   NOT NULL DEFAULT 'OPEN',
    closed_at       timestamptz   NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT pk_invoices          PRIMARY KEY (invoice_id),
    CONSTRAINT uq_invoices_period   UNIQUE (partner_id, reference_month),
    CONSTRAINT fk_invoices_partner  FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
    CONSTRAINT ck_invoices_month    CHECK (reference_month ~ '^\d{4}-(0[1-9]|1[0-2])$'),
    CONSTRAINT ck_invoices_status   CHECK (status IN ('OPEN', 'CLOSED')),
    CONSTRAINT ck_invoices_fees     CHECK (
        base_fee >= 0 AND api_fee >= 0 AND llm_fee >= 0 AND ocr_fee >= 0
    ),
    CONSTRAINT ck_invoices_total    CHECK (total = base_fee + api_fee + llm_fee + ocr_fee),
    CONSTRAINT ck_invoices_closed   CHECK (
        (status = 'CLOSED' AND closed_at IS NOT NULL)
        OR (status = 'OPEN' AND closed_at IS NULL)
    )
);

COMMENT ON COLUMN invoices.reference_month IS
    'Mês de competência no formato YYYY-MM, único por parceiro.';

CREATE INDEX ix_invoices_open ON invoices (partner_id) WHERE status = 'OPEN';
