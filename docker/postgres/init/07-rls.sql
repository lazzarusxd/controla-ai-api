-- =============================================================================
-- 07-rls.sql, Row Level Security como defesa em profundidade da RN002
-- =============================================================================
SET search_path TO controla_ai, public;

CREATE OR REPLACE FUNCTION current_partner_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN nullif(current_setting('app.partner_id', true), '')::uuid;
EXCEPTION
    WHEN invalid_text_representation THEN
        RETURN NULL;
END;
$$;

COMMENT ON FUNCTION current_partner_id() IS 'Parceiro da transação corrente, definido via SET LOCAL app.partner_id.';

DO $$
DECLARE
    target text;
BEGIN
    FOREACH target IN ARRAY ARRAY[
        'users', 'receipts', 'transactions', 'subscriptions', 'assets',
        'goals', 'tax_deductions', 'metering_logs', 'invoices',
        'vector_embeddings'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', target);
        EXECUTE format(
            'CREATE POLICY pl_%1$s_tenant ON %1$I
                 USING (partner_id = current_partner_id())
                 WITH CHECK (partner_id = current_partner_id())',
            target
        );
    END LOOP;
END;
$$;
