from enum import Enum
from typing import List


class ExportFormat(str, Enum):
    """Formato de serialização do dossiê exportado."""

    # Portabilidade plena, estrutura aninhada preservada.
    JSON = "JSON"

    # Portabilidade plena, tabular. Seção única sai em texto puro, várias seções saem empacotadas.
    CSV = "CSV"

    # Relatório legível. Admite truncamento por seção, por isso não é formato de portabilidade.
    PDF = "PDF"


class ExportStatus(str, Enum):
    """Estágio da exportação dentro do pipeline assíncrono."""

    # Solicitação registrada e job enfileirado. Nenhum byte foi gerado ainda.
    PENDING = "PENDING"

    # O worker reivindicou a exportação. Estado transitório.
    PROCESSING = "PROCESSING"

    # Artefato gravado e disponível para retirada.
    COMPLETED = "COMPLETED"

    # Falha na leitura ou na serialização. Nenhum artefato foi gravado.
    FAILED = "FAILED"


class ExportSection(str, Enum):
    """Conjuntos de dados que podem compor o dossiê."""

    # Cadastro do titular sob o parceiro.
    PROFILE = "PROFILE"

    # Lançamentos de receita e despesa. Recortável por período.
    TRANSACTIONS = "TRANSACTIONS"

    # Metadados dos comprovantes enviados. Recortável por período. O binário original não viaja.
    RECEIPTS = "RECEIPTS"

    # Despesas recorrentes declaradas. Estado corrente.
    SUBSCRIPTIONS = "SUBSCRIPTIONS"

    # Bens duráveis e o custo efetivo apurado. Estado corrente.
    ASSETS = "ASSETS"

    # Objetivos financeiros e o plano pactuado. Estado corrente.
    GOALS = "GOALS"

    @classmethod
    def canonical_order(cls) -> List["ExportSection"]:
        """Ordem de apresentação no artefato, do cadastro para o derivado."""
        return [
            cls.PROFILE,
            cls.TRANSACTIONS,
            cls.RECEIPTS,
            cls.SUBSCRIPTIONS,
            cls.ASSETS,
            cls.GOALS
        ]

    @property
    def is_period_scoped(self) -> bool:
        """Só histórico datado responde ao recorte por período; estado corrente viaja inteiro."""
        return self in (ExportSection.TRANSACTIONS, ExportSection.RECEIPTS)


class ExportEvent(str, Enum):
    """Eventos de exportação entregues ao parceiro pelo callback."""

    # Artefato disponível para retirada.
    EXPORT_COMPLETED = "export.completed"

    # Geração interrompida. Nenhum artefato foi gravado.
    EXPORT_FAILED = "export.failed"
