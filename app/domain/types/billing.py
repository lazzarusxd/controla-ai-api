from enum import Enum


class InvoiceStatus(str, Enum):
    """Situação da fatura de uma competência."""

    # Competência ainda acumulando consumo. Nunca é gravada: é sempre prévia calculada na leitura.
    OPEN = "OPEN"

    # Documento emitido, com volumes e preços congelados.
    CLOSED = "CLOSED"


class PricingSource(str, Enum):
    """Procedência da tabela tarifária aplicada."""

    # Contrato negociado com o parceiro, versionado por competência.
    CONTRACT = "CONTRACT"

    # Tabela de balcão em configuração, para parceiro sem contrato vigente.
    LIST_PRICE = "LIST_PRICE"


class BillingActor(str, Enum):
    """Quem disparou o fechamento da competência."""

    # Integrador do parceiro, pela rota de fechamento.
    PARTNER = "PARTNER"

    # Rotina agendada de virada de mês.
    SCHEDULER = "SCHEDULER"


class BillingAuditEventType(str, Enum):
    """Eventos registrados na trilha de auditoria do faturamento."""

    # Primeiro fechamento da competência: a fatura passou a existir.
    INVOICE_CLOSED = "invoice.closed"

    # Nova ordem de fechamento sobre competência já fechada. Nada é recalculado.
    INVOICE_CLOSE_REPLAYED = "invoice.close_replayed"
