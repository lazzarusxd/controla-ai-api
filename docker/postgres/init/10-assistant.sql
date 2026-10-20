-- =============================================================================
-- 10-assistant.sql, histórico do assistente financeiro (RF010, RN011)
-- =============================================================================
SET search_path TO controla_ai, public;

CREATE TABLE assistant_messages (
    message_id         uuid         NOT NULL DEFAULT uuid_generate_v7(),
    partner_id         uuid         NOT NULL,
    user_id            uuid         NOT NULL,
    conversation_id    uuid         NOT NULL,
    question           text         NOT NULL,
    answer             text         NOT NULL,
    status             varchar(20)  NOT NULL,
    model              varchar(100) NULL,
    context_source_ids uuid[]       NOT NULL DEFAULT '{}',
    created_at         timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_assistant_messages        PRIMARY KEY (message_id),
    CONSTRAINT fk_assistant_messages_user   FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_assistant_messages_status CHECK (status IN ('ANSWERED', 'NO_CONTEXT')),
    CONSTRAINT ck_assistant_messages_text   CHECK (length(btrim(question)) > 0 AND length(btrim(answer)) > 0),
    CONSTRAINT ck_assistant_messages_model  CHECK (
        (status = 'ANSWERED' AND model IS NOT NULL)
        OR (status = 'NO_CONTEXT' AND model IS NULL)
    )
);

COMMENT ON TABLE assistant_messages IS
    'Rastro das interações com o assistente RAG (RF010).';
COMMENT ON COLUMN assistant_messages.status IS
    'ANSWERED houve contexto recuperado e geração; NO_CONTEXT o modelo foi bloqueado pela RN011.';
COMMENT ON COLUMN assistant_messages.conversation_id IS
    'Agrupador dos turnos de um mesmo diálogo. Emitido pela API quando ausente na requisição.';
COMMENT ON COLUMN assistant_messages.context_source_ids IS
    'Registros de origem que fundamentaram a resposta. Vazio quando status = NO_CONTEXT.';

CREATE INDEX ix_assistant_messages_user ON assistant_messages (partner_id, user_id, created_at DESC);

CREATE INDEX ix_assistant_messages_conversation
    ON assistant_messages (partner_id, user_id, conversation_id, created_at DESC);

-- -----------------------------------------------------------------------------
-- RLS nos mesmos termos do 07-rls.sql e do 08-rls-roles.sql.
-- -----------------------------------------------------------------------------
ALTER TABLE assistant_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY pl_assistant_messages_tenant ON assistant_messages
    USING (partner_id = current_partner_id())
    WITH CHECK (partner_id = current_partner_id());

ALTER TABLE assistant_messages FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON assistant_messages TO controla_ai_app;
