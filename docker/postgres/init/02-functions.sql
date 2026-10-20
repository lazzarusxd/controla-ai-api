-- =============================================================================
-- 02-functions.sql, funções utilitárias compartilhadas pelo schema
-- =============================================================================
SET search_path TO controla_ai, public;

-- -----------------------------------------------------------------------------
-- uuid_generate_v7(), identificadores UUIDv7 (RFC 9562, seção 5.7)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION uuid_generate_v7()
RETURNS uuid
LANGUAGE plpgsql
VOLATILE
AS $$
BEGIN
    RETURN encode(
        set_bit(
            set_bit(
                overlay(
                    uuid_send(gen_random_uuid())
                    PLACING substring(
                        int8send(
                            floor(extract(EPOCH FROM clock_timestamp()) * 1000)::bigint
                        )
                        FROM 3
                    )
                    FROM 1 FOR 6
                ),
                52, 1
            ),
            53, 1
        ),
        'hex'
    )::uuid;
END;
$$;

COMMENT ON FUNCTION uuid_generate_v7() IS
    'Gera UUID versão 7 (RFC 9562) com prefixo temporal de 48 bits.';

-- -----------------------------------------------------------------------------
-- set_updated_at(), trigger genérica de auditoria temporal
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION set_updated_at() IS
    'Trigger BEFORE UPDATE que preenche updated_at com o horário do servidor.';
