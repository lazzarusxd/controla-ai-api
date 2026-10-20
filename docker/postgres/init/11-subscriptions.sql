-- =============================================================================
-- 11-subscriptions.sql, rastro das notificações prévias de recorrência (RF004, RN005)
-- =============================================================================
SET search_path TO controla_ai, public;

CREATE TABLE subscription_notifications (
    notification_id uuid          NOT NULL DEFAULT uuid_generate_v7(),
    partner_id      uuid          NOT NULL,
    user_id         uuid          NOT NULL,
    subscription_id uuid          NOT NULL,
    due_date        date          NOT NULL,
    amount          numeric(15,2) NOT NULL,
    lead_days       numeric(3,0)  NOT NULL,
    delivered       boolean       NOT NULL DEFAULT false,
    delivered_at    timestamptz   NULL,
    created_at      timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT pk_subscription_notifications        PRIMARY KEY (notification_id),
    CONSTRAINT uq_subscription_notifications_cycle  UNIQUE (partner_id, subscription_id, due_date),
    CONSTRAINT fk_subscription_notifications_owner  FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_subscription_notifications_source FOREIGN KEY (partner_id, subscription_id) REFERENCES subscriptions (partner_id, subscription_id) ON DELETE CASCADE,
    CONSTRAINT ck_subscription_notifications_amount CHECK (amount > 0),
    CONSTRAINT ck_subscription_notifications_lead   CHECK (lead_days BETWEEN 0 AND 90),
    CONSTRAINT ck_subscription_notifications_stamp  CHECK (
        (delivered = true AND delivered_at IS NOT NULL)
        OR (delivered = false AND delivered_at IS NULL)
    )
);

COMMENT ON CONSTRAINT fk_subscription_notifications_source ON subscription_notifications IS
    'Chave composta com partner_id: um aviso não pode apontar para o contrato de outro parceiro nem por erro de aplicação.';

COMMENT ON TABLE subscription_notifications IS
    'Histórico dos avisos prévios de vencimento emitidos ao parceiro (RF004).';
COMMENT ON CONSTRAINT uq_subscription_notifications_cycle ON subscription_notifications IS
    'Um aviso por ciclo. É esta restrição que impede o cron de renotificar a cada varredura do mesmo dia.';
COMMENT ON COLUMN subscription_notifications.due_date IS
    'Vencimento efetivo do ciclo, já com o due_day ajustado ao último dia de meses mais curtos.';
COMMENT ON COLUMN subscription_notifications.delivered IS
    'Falso quando o callback foi reservado mas o destino não confirmou o recebimento.';

CREATE INDEX ix_subscription_notifications_user
    ON subscription_notifications (partner_id, user_id, due_date DESC);

CREATE INDEX ix_subscription_notifications_subscription
    ON subscription_notifications (partner_id, subscription_id, due_date DESC);

-- -----------------------------------------------------------------------------
-- RLS nos mesmos termos do 07-rls.sql e do 08-rls-roles.sql.
-- -----------------------------------------------------------------------------
ALTER TABLE subscription_notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY pl_subscription_notifications_tenant ON subscription_notifications
    USING (partner_id = current_partner_id())
    WITH CHECK (partner_id = current_partner_id());

ALTER TABLE subscription_notifications FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON subscription_notifications TO controla_ai_app;