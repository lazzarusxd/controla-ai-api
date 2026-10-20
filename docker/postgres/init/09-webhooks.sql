-- =============================================================================
-- 09-webhooks.sql, destino de callback dos parceiros (RF003)
-- =============================================================================
SET search_path TO controla_ai, public;

CREATE TABLE partner_webhooks (
    partner_id uuid          NOT NULL,
    target_url varchar(1024) NOT NULL,
    secret     varchar(128)  NOT NULL,
    is_active  boolean       NOT NULL DEFAULT true,
    created_at timestamptz   NOT NULL DEFAULT now(),
    updated_at timestamptz   NULL,

    CONSTRAINT pk_partner_webhooks       PRIMARY KEY (partner_id),
    CONSTRAINT fk_partner_webhooks_owner FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
    CONSTRAINT ck_partner_webhooks_url   CHECK (target_url ~ '^https://')
);

COMMENT ON COLUMN partner_webhooks.target_url IS
    'Destino da notificação. Restrito a https: o corpo carrega dado financeiro do usuário final.';
COMMENT ON COLUMN partner_webhooks.secret IS
    'Segredo compartilhado da assinatura HMAC-SHA256. Nunca é devolvido após o registro.';

CREATE TRIGGER tg_partner_webhooks_updated_at
    BEFORE UPDATE ON partner_webhooks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- RLS nos mesmos termos do 07-rls.sql e do 08-rls-roles.sql.
-- -----------------------------------------------------------------------------
ALTER TABLE partner_webhooks ENABLE ROW LEVEL SECURITY;

CREATE POLICY pl_partner_webhooks_tenant ON partner_webhooks
    USING (partner_id = current_partner_id())
    WITH CHECK (partner_id = current_partner_id());

ALTER TABLE partner_webhooks FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON partner_webhooks TO controla_ai_app;
