-- =============================================================================
-- 04-financial.sql, comprovantes, transações, assinaturas, patrimônio, metas e deduções fiscais
-- Cobre RN002 a RN009. Toda tabela deste arquivo é tenant-scoped: a chave estrangeira composta (partner_id, user_id) impede vínculo entre parceiros.
-- =============================================================================
SET search_path TO controla_ai, public;

-- -----------------------------------------------------------------------------
-- RECEIPTS, comprovantes enviados para ingestão via OCR (RF003)
-- -----------------------------------------------------------------------------
CREATE TABLE receipts (
    receipt_id       uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id       uuid          NOT NULL,
    user_id          uuid          NOT NULL,
    file_path        varchar(1024) NOT NULL,
    file_type        varchar(20)   NOT NULL,
    file_size_bytes  numeric(14,0) NOT NULL,
    raw_text         text          NULL,
    confidence_score numeric(3,2)  NULL,
    status           varchar(20)   NOT NULL DEFAULT 'UPLOADED',
    processed_at     timestamptz   NULL,
    created_at       timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT pk_receipts          PRIMARY KEY (receipt_id),
    CONSTRAINT uq_receipts_tenant   UNIQUE (partner_id, receipt_id),
    CONSTRAINT fk_receipts_user     FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_receipts_type     CHECK (file_type IN ('image/jpeg', 'image/png', 'application/pdf')),
    CONSTRAINT ck_receipts_status   CHECK (status IN ('UPLOADED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    CONSTRAINT ck_receipts_size     CHECK (file_size_bytes > 0),
    CONSTRAINT ck_receipts_score    CHECK (confidence_score BETWEEN 0 AND 1),
    CONSTRAINT ck_receipts_processed CHECK (
        (status IN ('COMPLETED', 'FAILED') AND processed_at IS NOT NULL)
        OR (status IN ('UPLOADED', 'PROCESSING') AND processed_at IS NULL)
    )
);

COMMENT ON COLUMN receipts.file_path IS
    'Caminho relativo a RECEIPT_STORAGE_ROOT: {partner_id}/{user_id}/{receipt_id}.{ext}';

CREATE INDEX ix_receipts_user ON receipts (partner_id, user_id, created_at DESC);

CREATE INDEX ix_receipts_pending ON receipts (created_at) WHERE status IN ('UPLOADED', 'PROCESSING');

-- -----------------------------------------------------------------------------
-- TRANSACTIONS, lançamentos de entrada e saída (RF002, RN003, RN004)
-- -----------------------------------------------------------------------------
CREATE TABLE transactions (
    transaction_id   uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id       uuid          NOT NULL,
    user_id          uuid          NOT NULL,
    type             varchar(20)   NOT NULL,
    amount           numeric(15,2) NOT NULL,
    category         varchar(100)  NOT NULL,
    description      varchar(500)  NOT NULL,
    transaction_date date          NOT NULL,
    due_date         date          NULL,
    status           varchar(20)   NOT NULL DEFAULT 'PENDING',
    pending_review   boolean       NOT NULL DEFAULT false,
    confidence_score numeric(3,2)  NULL,
    receipt_id       uuid          NULL,
    created_at       timestamptz   NOT NULL DEFAULT now(),
    updated_at       timestamptz   NULL,

    CONSTRAINT pk_transactions         PRIMARY KEY (transaction_id),
    CONSTRAINT fk_transactions_user    FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_transactions_receipt FOREIGN KEY (partner_id, receipt_id) REFERENCES receipts (partner_id, receipt_id) ON DELETE SET NULL (receipt_id),
    CONSTRAINT ck_transactions_type    CHECK (type IN ('INCOME', 'EXPENSE')),
    CONSTRAINT ck_transactions_status  CHECK (status IN ('PENDING', 'SETTLED', 'CANCELED')),
    CONSTRAINT ck_transactions_amount  CHECK (amount > 0),
    CONSTRAINT ck_transactions_score   CHECK (confidence_score BETWEEN 0 AND 1),
    CONSTRAINT ck_transactions_review  CHECK (
        pending_review = false OR confidence_score IS NOT NULL
    )
);

COMMENT ON COLUMN transactions.due_date IS
    'Vencimento no regime de competência. NULL quando o lançamento já nasce liquidado (RN003).';
COMMENT ON COLUMN transactions.confidence_score IS
    'Índice de confiança do OCR. NULL em inserção manual.';

CREATE INDEX ix_transactions_statement ON transactions (partner_id, user_id, transaction_date DESC) INCLUDE (type, amount, category);

CREATE INDEX ix_transactions_due
    ON transactions (partner_id, user_id, due_date)
    WHERE status = 'PENDING';

CREATE INDEX ix_transactions_review
    ON transactions (partner_id, user_id, created_at)
    WHERE pending_review = true;

CREATE INDEX ix_transactions_category
    ON transactions (partner_id, user_id, category, transaction_date DESC)
    WHERE type = 'EXPENSE';

CREATE TRIGGER tg_transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- SUBSCRIPTIONS, despesas recorrentes de valor fixo (RF004, RN005)
-- -----------------------------------------------------------------------------
CREATE TABLE subscriptions (
    subscription_id uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id      uuid          NOT NULL,
    user_id         uuid          NOT NULL,
    company_name    varchar(255)  NOT NULL,
    amount          numeric(15,2) NOT NULL,
    description     varchar(500)  NOT NULL,
    due_day         numeric(2,0)  NOT NULL,
    is_active       boolean       NOT NULL DEFAULT true,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    updated_at      timestamptz   NULL,

    CONSTRAINT pk_subscriptions        PRIMARY KEY (subscription_id),
    CONSTRAINT uq_subscriptions_tenant UNIQUE (partner_id, subscription_id),
    CONSTRAINT fk_subscriptions_user   FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_subscriptions_amount CHECK (amount > 0),
    CONSTRAINT ck_subscriptions_day    CHECK (due_day BETWEEN 1 AND 31)
);

COMMENT ON COLUMN subscriptions.due_day IS
    'Dia do vencimento (1 a 31). Meses mais curtos são resolvidos na aplicação, não no dado.';

CREATE INDEX ix_subscriptions_due_day ON subscriptions (due_day) WHERE is_active = true;

CREATE INDEX ix_subscriptions_user ON subscriptions (partner_id, user_id) WHERE is_active = true;

CREATE TRIGGER tg_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- ASSETS, patrimônio e custo efetivo total mensal (RF005, RN006)
-- -----------------------------------------------------------------------------
CREATE TABLE assets (
    asset_id              uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id            uuid          NOT NULL,
    user_id               uuid          NOT NULL,
    asset_type            varchar(20)   NOT NULL,
    description           varchar(500)  NOT NULL,
    market_value          numeric(15,2) NOT NULL,
    acquisition_date      date          NOT NULL,
    annual_taxes          numeric(15,2) NOT NULL,
    monthly_depreciation  numeric(15,2) NULL,
    monthly_tax_provision numeric(15,2) NOT NULL,
    total_monthly_cost    numeric(15,2) NOT NULL,
    created_at            timestamptz   NOT NULL DEFAULT now(),
    updated_at            timestamptz   NULL,

    CONSTRAINT pk_assets            PRIMARY KEY (asset_id),
    CONSTRAINT fk_assets_user       FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_assets_type       CHECK (asset_type IN ('VEHICLE', 'PROPERTY', 'OTHER')),
    CONSTRAINT ck_assets_values     CHECK (market_value >= 0 AND annual_taxes >= 0),
    CONSTRAINT ck_assets_acquired   CHECK (acquisition_date <= CURRENT_DATE),
    CONSTRAINT ck_assets_total_cost CHECK (
        total_monthly_cost = monthly_tax_provision + coalesce(monthly_depreciation, 0)
    )
);

CREATE INDEX ix_assets_user ON assets (partner_id, user_id, asset_type);

CREATE TRIGGER tg_assets_updated_at BEFORE UPDATE ON assets FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- GOALS, metas financeiras e simulação de viabilidade (RF007, RN008)
-- -----------------------------------------------------------------------------
CREATE TABLE goals (
    goal_id              uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id           uuid          NOT NULL,
    user_id              uuid          NOT NULL,
    name                 varchar(255)  NOT NULL,
    target_amount        numeric(15,2) NOT NULL,
    desired_months       numeric(5,0)  NOT NULL,
    monthly_contribution numeric(15,2) NOT NULL,
    projected_months     numeric(5,0)  NOT NULL,
    interest_rate        numeric(10,2) NOT NULL,
    is_viable            boolean       NOT NULL,
    created_at           timestamptz   NOT NULL DEFAULT now(),
    updated_at           timestamptz   NULL,

    CONSTRAINT pk_goals            PRIMARY KEY (goal_id),
    CONSTRAINT fk_goals_user       FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_goals_target     CHECK (target_amount > 0),
    CONSTRAINT ck_goals_months     CHECK (desired_months > 0 AND projected_months > 0),
    CONSTRAINT ck_goals_rate       CHECK (interest_rate >= 0),
    CONSTRAINT ck_goals_viability  CHECK (is_viable = (projected_months <= desired_months))
);

COMMENT ON COLUMN goals.interest_rate IS
    'Taxa livre de risco mensal, em pontos percentuais, usada na capitalização composta.';

CREATE INDEX ix_goals_user ON goals (partner_id, user_id, created_at DESC);

CREATE TRIGGER tg_goals_updated_at
    BEFORE UPDATE ON goals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- TAX_DEDUCTIONS, consolidação de deduções por ano fiscal (RF008, RN009)
-- -----------------------------------------------------------------------------
CREATE TABLE tax_deductions (
    deduction_id    uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id      uuid          NOT NULL,
    user_id         uuid          NOT NULL,
    fiscal_year     numeric(5,0)  NOT NULL,
    category        varchar(20)   NOT NULL,
    total_amount    numeric(15,2) NOT NULL,
    legal_ceiling   numeric(15,2) NOT NULL,
    eligible_amount numeric(15,2) NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),
    updated_at      timestamptz   NULL,

    CONSTRAINT pk_tax_deductions         PRIMARY KEY (deduction_id),
    CONSTRAINT fk_tax_deductions_user    FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_tax_deductions_period  UNIQUE (partner_id, user_id, fiscal_year, category),
    CONSTRAINT ck_tax_deductions_cat     CHECK (category IN ('HEALTH', 'EDUCATION')),
    CONSTRAINT ck_tax_deductions_year    CHECK (fiscal_year BETWEEN 2000 AND 2999),
    CONSTRAINT ck_tax_deductions_amounts CHECK (
        total_amount >= 0 AND legal_ceiling >= 0
    ),
    CONSTRAINT ck_tax_deductions_eligible CHECK (
        eligible_amount = least(total_amount, legal_ceiling)
    )
);

COMMENT ON COLUMN tax_deductions.legal_ceiling IS
    'Teto legal vigente. Despesas médicas não têm limite: usar valor sentinela suficientemente alto.';

CREATE TRIGGER tg_tax_deductions_updated_at
    BEFORE UPDATE ON tax_deductions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
