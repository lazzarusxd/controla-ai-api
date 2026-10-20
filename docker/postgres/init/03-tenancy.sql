-- =============================================================================
-- 03-tenancy.sql, parceiros, credenciais OAuth 2.0, refresh tokens e usuários
-- Cobre RN001 (autenticação) e RN002 (isolamento de parceiro).
-- =============================================================================
SET search_path TO controla_ai, public;

-- -----------------------------------------------------------------------------
-- PARTNERS, raiz do agregado de tenancy
-- -----------------------------------------------------------------------------
CREATE TABLE partners (
    partner_id  uuid         NOT NULL DEFAULT uuid_generate_v7(),
    name        varchar(255) NOT NULL,
    is_active   boolean      NOT NULL DEFAULT true,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NULL,

    CONSTRAINT pk_partners      PRIMARY KEY (partner_id),
    CONSTRAINT ck_partners_name CHECK (length(btrim(name)) > 0)
);

COMMENT ON TABLE  partners            IS 'Empresas contratantes da API no modelo B2B2C.';
COMMENT ON COLUMN partners.is_active  IS 'Parceiro inativo tem emissão de token bloqueada.';

CREATE TRIGGER tg_partners_updated_at
    BEFORE UPDATE ON partners
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- CREDENTIALS, pares client_id/client_secret do OAuth 2.0 (RFC 6749)
-- -----------------------------------------------------------------------------
CREATE TABLE credentials (
    credential_id       uuid         NOT NULL DEFAULT uuid_generate_v7(),
    client_id           varchar(128) NOT NULL,
    client_secret_hash  varchar(512) NOT NULL,
    partner_id          uuid         NOT NULL,
    is_revoked          boolean      NOT NULL DEFAULT false,
    created_at          timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_credentials            PRIMARY KEY (credential_id),
    CONSTRAINT uq_credentials_client_id  UNIQUE (client_id),
    CONSTRAINT fk_credentials_partner    FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE
);

COMMENT ON COLUMN credentials.client_secret_hash IS
    'Hash Argon2id do client_secret. O valor em claro nunca é persistido.';

CREATE INDEX ix_credentials_partner ON credentials (partner_id);

-- -----------------------------------------------------------------------------
-- REFRESH_TOKENS, rotação de refresh token (RFC 6749, seção 10.4)
-- -----------------------------------------------------------------------------
CREATE TABLE refresh_tokens (
    token_id    uuid         NOT NULL DEFAULT uuid_generate_v7(),
    token       varchar(512) NOT NULL,
    client_id   varchar(128) NOT NULL,
    partner_id  uuid         NOT NULL,
    expires_at  timestamptz  NOT NULL,
    is_used     boolean      NOT NULL DEFAULT false,
    created_at  timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_refresh_tokens          PRIMARY KEY (token_id),
    CONSTRAINT uq_refresh_tokens_token    UNIQUE (token),
    CONSTRAINT fk_refresh_tokens_client   FOREIGN KEY (client_id) REFERENCES credentials (client_id) ON DELETE CASCADE,
    CONSTRAINT fk_refresh_tokens_partner  FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
    CONSTRAINT ck_refresh_tokens_expiry   CHECK (expires_at > created_at)
);

COMMENT ON COLUMN refresh_tokens.token IS
    'Digest SHA-256 (hex) do refresh token opaco. O valor em claro só existe na resposta ao cliente.';

CREATE INDEX ix_refresh_tokens_active
    ON refresh_tokens (partner_id, expires_at)
    WHERE is_used = false;

CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens (expires_at);

-- -----------------------------------------------------------------------------
-- USERS, consumidores finais, sempre subordinados a um parceiro
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    user_id     uuid         NOT NULL DEFAULT uuid_generate_v7(),
    partner_id  uuid         NOT NULL,
    name        varchar(255) NOT NULL,
    email       varchar(255) NOT NULL,
    is_active   boolean      NOT NULL DEFAULT true,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NULL,

    CONSTRAINT pk_users          PRIMARY KEY (user_id),
    CONSTRAINT fk_users_partner  FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
    CONSTRAINT uq_users_tenant   UNIQUE (partner_id, user_id),
    CONSTRAINT uq_users_email    UNIQUE (partner_id, email),
    CONSTRAINT ck_users_email    CHECK (position('@' IN email) > 1)
);

COMMENT ON CONSTRAINT uq_users_tenant ON users IS
    'Habilita FK composta (partner_id, user_id) nas tabelas filhas, impedindo vínculo cruzado entre parceiros.';

CREATE TRIGGER tg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
