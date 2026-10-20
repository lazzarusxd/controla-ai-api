-- =============================================================================
-- 06-rag.sql, base vetorial do assistente (RF010, RN011)
-- =============================================================================
SET search_path TO controla_ai, public;

-- -----------------------------------------------------------------------------
-- VECTOR_EMBEDDINGS
-- -----------------------------------------------------------------------------
CREATE TABLE vector_embeddings (
    embedding_id uuid         NOT NULL DEFAULT uuid_generate_v7(),
    partner_id   uuid         NOT NULL,
    user_id      uuid         NOT NULL,
    source_type  varchar(50)  NOT NULL,
    source_id    uuid         NOT NULL,
    context_text text         NOT NULL,
    vector       vector(1536) NOT NULL,
    created_at   timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_vector_embeddings        PRIMARY KEY (embedding_id),
    CONSTRAINT fk_vector_embeddings_user   FOREIGN KEY (partner_id, user_id) REFERENCES users (partner_id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_vector_embeddings_source UNIQUE (partner_id, user_id, source_type, source_id),
    CONSTRAINT ck_vector_embeddings_source CHECK (
        source_type IN ('transaction', 'receipt', 'goal', 'asset', 'subscription', 'tax_deduction')
    ),
    CONSTRAINT ck_vector_embeddings_text   CHECK (length(btrim(context_text)) > 0)
);

COMMENT ON TABLE vector_embeddings IS
    'Contexto vetorizado do assistente RAG. RN011: toda recuperação é filtrada por partner_id e user_id.';

CREATE INDEX ix_vector_embeddings_tenant ON vector_embeddings (partner_id, user_id);

CREATE INDEX ix_vector_embeddings_hnsw
    ON vector_embeddings
    USING hnsw (vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 96);
