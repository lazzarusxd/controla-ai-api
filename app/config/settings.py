from functools import lru_cache
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class ServiceSettings(BaseSettings):
    """Configuração completa da API, carregada do ambiente."""
    APP_NAME: str = Field(
        default="api-controla-ai",
        description="Identificador da aplicação, usado em logs e nas probes de saúde.",
        examples=["api-controla-ai"]
    )

    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="production",
        description="Ambiente de execução. "
                    "Em 'production' a documentação interativa é desabilitada e os logs são emitidos em JSON.",
        examples=["production", "development"]
    )

    APP_DEBUG: bool = Field(
        default=False,
        description="Modo de depuração do FastAPI. Deve permanecer desligado fora do desenvolvimento.",
    )

    APP_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Porta TCP em que a aplicação escuta.",
        examples=[8000]
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Nível mínimo de severidade registrado pelo structlog.",
        examples=["INFO", "DEBUG"],
    )

    TZ: str = Field(
        default="America/Sao_Paulo",
        description="Fuso horário do processo, no formato IANA.",
        examples=["America/Sao_Paulo"],
    )

    DATABASE_URL: SecretStr = Field(
        default=...,
        description="DSN de conexão do PostgreSQL no formato aceito pelo asyncpg.",
        examples=["postgres://usuario:senha@postgres:5432/controlaai"]
    )

    DATABASE_SCHEMA: str = Field(
        default="controla_ai",
        description="Schema aplicado ao search_path na inicialização de cada conexão do pool.",
        examples=["controla_ai"]
    )

    DATABASE_MIN_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        description="Conexões mantidas abertas por processo, mesmo em ociosidade.",
        examples=[5]
    )

    DATABASE_MAX_POOL_SIZE: int = Field(
        default=15,
        ge=1,
        description="Teto de conexões por processo.",
        examples=[15]
    )

    DATABASE_COMMAND_TIMEOUT: int = Field(
        default=30,
        ge=1,
        description="Tempo limite, em segundos, para a execução de uma query.",
        examples=[30],
    )

    REDIS_URL: SecretStr = Field(
        default=...,
        description="URL de conexão do Redis.",
        examples=["redis://redis:6379/0"]
    )

    REDIS_CACHE_DB: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Banco lógico do cache.",
        examples=[0]
    )

    REDIS_QUEUE_DB: int = Field(
        default=1,
        ge=0,
        le=15,
        description="Banco lógico das filas do arq.",
        examples=[1]
    )

    REDIS_METERING_DB: int = Field(
        default=2,
        ge=0,
        le=15,
        description="Banco lógico dos contadores de consumo.",
        examples=[2]
    )

    RECEIPT_STORAGE_ROOT: str = Field(
        default="/var/lib/controlaai/receipts",
        description="Diretório raiz dos comprovantes. "
                    "Os arquivos são gravados em {partner_id}/{user_id}/{receipt_id}.{ext} e referenciados por "
                    "RECEIPTS.FILE_PATH.",
        examples=["/var/lib/controlaai/receipts"]
    )

    RECEIPT_MAX_SIZE_BYTES: int = Field(
        default=10485760,
        ge=1,
        description="Tamanho máximo aceito no upload.",
        examples=[10485760]
    )

    RECEIPT_ALLOWED_MIME: Annotated[
        List[str],
        NoDecode,
        Field(
            default_factory=lambda: ["image/jpeg", "image/png", "application/pdf"],
            description="Tipos MIME aceitos no upload. "
                        "Aceita lista separada por vírgula na variável de ambiente.",
            examples=[["image/jpeg", "image/png", "application/pdf"]]
        )
    ]

    JWE_PRIVATE_KEY_PATH: str = Field(
        default="/run/secrets/jwe_private.pem",
        description="Caminho da chave privada RSA usada na decriptação dos tokens.",
        examples=["/run/secrets/jwe_private.pem"],
    )

    JWE_PUBLIC_KEY_PATH: str = Field(
        default="/run/secrets/jwe_public.pem",
        description="Caminho da chave pública RSA usada na emissão dos tokens.",
        examples=["/run/secrets/jwe_public.pem"]
    )

    JWE_ALGORITHM: str = Field(
        default="RSA-OAEP-256",
        description="Algoritmo de gerenciamento de chave do JWE, conforme RFC 7518.",
        examples=["RSA-OAEP-256"]
    )

    JWE_ENCRYPTION: str = Field(
        default="A256GCM",
        description="Algoritmo de criptografia do conteúdo do JWE, conforme RFC 7518.",
        examples=["A256GCM"]
    )

    JWE_ISSUER: str = Field(
        default="https://api.controla.ai",
        description="Emissor registrado na claim 'iss' do access token, conforme RFC 7519.",
        examples=["https://api.controla.ai"]
    )

    JWE_AUDIENCE: str = Field(
        default="controla-ai-api",
        description="Destinatário registrado na claim 'aud'. Rejeitar tokens de outra audiência impede que "
                    "um token emitido para outro serviço do mesmo domínio seja aceito aqui.",
        examples=["controla-ai-api"]
    )

    ACCESS_TOKEN_TTL_SECONDS: int = Field(
        default=900,
        ge=60,
        description="Validade do access token. Intervalo curto limita a janela de exploração em caso de vazamento.",
        examples=[900]
    )

    REFRESH_TOKEN_TTL_SECONDS: int = Field(
        default=2592000,
        ge=3600,
        description="Validade do refresh token, persistido em REFRESH_TOKENS.",
        examples=[2592000],
    )

    OCR_LANGUAGE: str = Field(
        default="por",
        description="Código do modelo de idioma do Tesseract, instalado na imagem de runtime.",
        examples=["por"]
    )

    OCR_CONFIDENCE_THRESHOLD: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Limiar da extração abaixo deste índice marca a transação para revisão manual.",
        examples=[0.85]
    )

    LLM_PROVIDER: str = Field(
        default="openai",
        description="Provedor do modelo de linguagem utilizado na inferência.",
        examples=["openai"]
    )

    LLM_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Raiz da API do provedor. Isolada em configuração para permitir apontar "
                    "para um gateway compatível sem alterar o adaptador.",
        examples=["https://api.openai.com/v1"]
    )

    LLM_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Credencial de acesso ao provedor. Ausente, extração e assistente ficam indisponíveis.",
        examples=["sk-..."]
    )

    LLM_MODEL: str = Field(
        default="gpt-4.1-mini",
        description="Modelo usado na estruturação do comprovante. Deve suportar Structured Outputs "
                    "com `json_schema` e `strict`.",
        examples=["gpt-4.1-mini"]
    )

    LLM_TIMEOUT_SECONDS: int = Field(
        default=30,
        ge=1,
        description="Tempo limite das chamadas ao provedor.",
        examples=[30]
    )

    WEBHOOK_TIMEOUT_SECONDS: int = Field(
        default=10,
        ge=1,
        description="Tempo limite de cada tentativa de entrega do callback.",
        examples=[10]
    )

    WEBHOOK_MAX_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        description="Tentativas de entrega do callback. Apenas falhas de rede e respostas 5xx são repetidas: "
                    "4xx indica contrato incompatível e repetir não muda o desfecho.",
        examples=[3]
    )

    WEBHOOK_RETRY_BACKOFF_SECONDS: float = Field(
        default=2.0,
        ge=0.0,
        description="Base do intervalo linear entre as tentativas de entrega.",
        examples=[2.0]
    )

    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Modelo de geração dos vetores persistidos em VECTOR_EMBEDDINGS.",
        examples=["text-embedding-3-small"]
    )

    EMBEDDING_DIMENSIONS: int = Field(
        default=1536,
        ge=1,
        description="Dimensionalidade do vetor.",
        examples=[1536]
    )

    RAG_TOP_K: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Vizinhos recuperados da base vetorial por pergunta.",
        examples=[8]
    )

    RAG_MIN_SIMILARITY: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Similaridade de cosseno mínima para um trecho entrar no prompt. "
                    "Abaixo dela o trecho é descartado ainda que seja o vizinho mais próximo.",
        examples=[0.25]
    )

    RAG_MAX_CONTEXT_CHARS: int = Field(
        default=6000,
        ge=500,
        description="Teto de caracteres do contexto injetado no prompt do assistente.",
        examples=[6000]
    )

    ASSISTANT_HISTORY_TURNS: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Turnos anteriores do mesmo diálogo injetados no prompt. Zero desliga a memória "
                    "conversacional e cada pergunta volta a ser independente.",
        examples=[5]
    )

    RAG_INDEX_BATCH_SIZE: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Registros vetorizados por passada de indexação, por parceiro.",
        examples=[200]
    )

    ASSET_VEHICLE_DEPRECIATION_RATE: float = Field(
        default=0.0167,
        ge=0.0,
        le=1.0,
        description="Taxa de depreciação mensal aplicada a veículos no cálculo do CET.",
        examples=[0.0167]
    )

    ASSET_PROPERTY_DEPRECIATION_RATE: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Taxa de depreciação mensal aplicada a imóveis. Zero mantém o CET apenas tributário.",
        examples=[0.0]
    )

    ASSET_OTHER_DEPRECIATION_RATE: float = Field(
        default=0.0083,
        ge=0.0,
        le=1.0,
        description="Taxa de depreciação mensal aplicada aos demais bens duráveis.",
        examples=[0.0083]
    )

    PARETO_CUTOFF_RATIO: float = Field(
        default=0.8,
        ge=0.5,
        le=1.0,
        description="Participação acumulada que delimita os poucos vitais no ranqueamento de ofensores.",
        examples=[0.8]
    )

    PARETO_ESSENTIAL_CATEGORIES: Annotated[
        List[str],
        NoDecode,
        Field(
            default_factory=lambda: [
                "Moradia",
                "Aluguel",
                "Condomínio",
                "Energia Elétrica",
                "Água e Esgoto",
                "Gás",
                "Internet",
                "Plano de Saúde",
                "Educação"
            ],
            description="Categorias tratadas como Despesas Fixas Essenciais e excluídas do ranqueamento. "
                        "Aceita lista separada por vírgula na variável de ambiente. O confronto é feito "
                        "sobre forma normalizada, sem sensibilidade a caixa ou acentuação.",
            examples=[["Moradia", "Energia Elétrica", "Água e Esgoto"]]
        )
    ]

    GOAL_ANNUAL_RISK_FREE_RATE: float = Field(
        default=0.1075,
        ge=0.0,
        le=1.0,
        description="Taxa livre de risco anual usada na simulação de metas, em forma decimal. "
                    "A taxa mensal é derivada por equivalência composta, nunca por divisão por doze.",
        examples=[0.1075]
    )

    GOAL_MAX_PROJECTION_MONTHS: int = Field(
        default=600,
        ge=1,
        le=99999,
        description="Horizonte máximo projetável para uma meta. Serve de teto quando a capacidade de "
                    "poupança observada é nula ou negativa e a série não converge.",
        examples=[600]
    )

    GOAL_CAPACITY_LOOKBACK_MONTHS: int = Field(
        default=6,
        ge=1,
        le=60,
        description="Meses de histórico observados na inferência da capacidade de poupança. Janela "
                    "curta reage rápido a mudanças de renda; janela longa suaviza sazonalidade.",
        examples=[6]
    )

    EXPORT_PDF_MAX_ROWS_PER_SECTION: int = Field(
        default=5000,
        ge=100,
        le=100000,
        description="Teto de linhas por seção no relatório em PDF. Só o PDF trunca, porque é resumo "
                    "legível; JSON e CSV são os formatos de portabilidade e saem sempre íntegros.",
        examples=[5000]
    )

    EXPORT_STORAGE_ROOT: str = Field(
        default="/var/lib/controlaai/exports",
        description="Diretório raiz dos artefatos de exportação. Separado da raiz dos comprovantes: "
                    "comprovante é dado enviado pelo titular e vive enquanto a conta viver, artefato de "
                    "exportação é derivado e descartável.",
        examples=["/var/lib/controlaai/exports"]
    )

    EXPORT_RETENTION_SECONDS: int = Field(
        default=86400,
        ge=300,
        le=604800,
        description="Prazo de retenção do artefato e do metadado da exportação, que expiram juntos. "
                    "Janela curta é decisão de privacidade: o pacote concentra o dossiê financeiro "
                    "inteiro do titular em um único arquivo.",
        examples=[86400]
    )

    TAX_DEDUCTIBLE_HEALTH_CATEGORIES: Annotated[
        List[str],
        NoDecode,
        Field(
            default_factory=lambda: [
                "Saúde",
                "Plano de Saúde",
                "Consulta Médica",
                "Exames",
                "Odontologia",
                "Fisioterapia",
                "Psicologia",
                "Internação Hospitalar"
            ],
            description="Categorias enquadradas como despesa dedutível de saúde. Aceita lista separada "
                        "por vírgula na variável de ambiente. O confronto é feito sobre forma normalizada, "
                        "sem sensibilidade a caixa ou acentuação.",
            examples=[["Saúde", "Plano de Saúde", "Odontologia"]]
        )
    ]

    TAX_DEDUCTIBLE_EDUCATION_CATEGORIES: Annotated[
        List[str],
        NoDecode,
        Field(
            default_factory=lambda: [
                "Educação",
                "Mensalidade Escolar",
                "Faculdade",
                "Pós-Graduação",
                "Creche",
                "Ensino Técnico"
            ],
            description="Categorias enquadradas como despesa dedutível de instrução. Mesma normalização "
                        "aplicada às categorias de saúde.",
            examples=[["Educação", "Mensalidade Escolar", "Creche"]]
        )
    ]

    TAX_EDUCATION_CEILING_BY_YEAR: Annotated[
        Dict[int, float],
        NoDecode,
        Field(
            default_factory=lambda: {2024: 3561.50, 2025: 3561.50, 2026: 3561.50},
            description="Teto anual de dedução com instrução, por exercício, no formato "
                        "`2026:3561.50,2025:3561.50`. Exercício não declarado herda o mais recente "
                        "anterior a ele. Vive em configuração porque muda por ato da autoridade "
                        "tributária, em cadência que não é a do deploy da API.",
            examples=[{2026: 3561.50}]
        )
    ]

    TAX_UNLIMITED_CEILING: float = Field(
        default=9999999999999.99,
        gt=0,
        description="Teto sentinela aplicado às categorias sem limite legal, como saúde. Existe porque a "
                    "coluna que registra o teto não admite nulo e a restrição que amarra o valor elegível "
                    "ao menor entre declarado e teto depende disso. Deve exceder qualquer valor "
                    "representável na coluna monetária.",
        examples=[9999999999999.99]
    )

    TAX_ANNUAL_BRACKETS: Annotated[
        List[str],
        NoDecode,
        Field(
            default_factory=lambda: [
                "2026:26963.20:0:0",
                "2026:33919.80:0.075:2022.24",
                "2026:45012.60:0.15:4566.23",
                "2026:55976.16:0.225:7942.17",
                "2026::0.275:10740.98"
            ],
            description="Tabela progressiva anual, uma faixa por entrada no formato "
                        "`exercício:teto:alíquota:parcela a deduzir`. Teto vazio marca a faixa aberta. "
                        "Aceita lista separada por vírgula na variável de ambiente.",
            examples=[["2026:26963.20:0:0", "2026::0.275:10740.98"]]
        )
    ]

    TAX_CONSOLIDATION_CRON_HOUR: int = Field(
        default=3,
        ge=0,
        le=23,
        description="Hora local da varredura diária de consolidação fiscal executada pelo scheduler.",
        examples=[3]
    )

    TAX_CONSOLIDATION_BATCH_SIZE: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Pares de usuário e exercício reapurados por passada, por parceiro.",
        examples=[500]
    )

    TAX_CONSOLIDATION_MAX_AGE_HOURS: int = Field(
        default=24,
        ge=1,
        le=8760,
        description="Idade a partir da qual uma consolidação é reapurada mesmo sem lançamento novo. "
                    "Exclusão física de lançamento não deixa marca temporal, e é este teto que garante "
                    "a convergência da consolidação depois dela.",
        examples=[24]
    )

    SUBSCRIPTION_ALERT_LEAD_DAYS: int = Field(
        default=3,
        ge=0,
        le=90,
        description="Antecedência, em dias, do aviso de vencimento de recorrência. Zero avisa no próprio "
                    "dia do vencimento.",
        examples=[3]
    )

    SUBSCRIPTION_NOTIFY_CRON_HOUR: int = Field(
        default=8,
        ge=0,
        le=23,
        description="Hora local da varredura diária de vencimentos executada pelo scheduler.",
        examples=[8]
    )

    SUBSCRIPTION_SWEEP_BATCH_SIZE: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Recorrências ativas avaliadas por passada, por parceiro.",
        examples=[500]
    )

    RAG_INDEX_CRON_MINUTES: int = Field(
        default=15,
        ge=1,
        le=60,
        description="Intervalo, em minutos, da varredura de indexação executada pelo scheduler.",
        examples=[15]
    )

    METERING_FLUSH_CRON_MINUTES: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Intervalo, em minutos, da drenagem dos contadores de consumo para o consumo diário "
                    "consolidado. Janela curta reduz o volume exposto a uma perda do Redis; janela longa "
                    "reduz a escrita no banco.",
        examples=[5]
    )

    METERING_CLAIM_BATCH_SIZE: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Lotes de consumo reivindicados por passada de drenagem.",
        examples=[1000]
    )

    BILLING_INVOICE_CLOSE_CRON_HOUR: int = Field(
        default=2,
        ge=0,
        le=23,
        description="Hora local da rotina diária que fecha a competência anterior. Roda todo dia, e não só no "
                    "primeiro, para recuperar uma virada de mês perdida por indisponibilidade do agendador.",
        examples=[2]
    )

    BILLING_LIST_BASE_MONTHLY_FEE: float = Field(
        default=499.00,
        ge=0.0,
        description="Taxa base mensal da tabela de balcão, aplicada ao parceiro sem contrato vigente na "
                    "competência. Preço negociado vive na tabela tarifária do parceiro, porque contrato é "
                    "atributo comercial de cada um, não da instância.",
        examples=[499.00]
    )

    BILLING_LIST_PRICE_PER_THOUSAND_REQUESTS: float = Field(
        default=2.50,
        ge=0.0,
        description="Preço de balcão por mil requisições autenticadas à API.",
        examples=[2.50]
    )

    BILLING_LIST_PRICE_PER_MILLION_TOKENS_IN: float = Field(
        default=4.00,
        ge=0.0,
        description="Preço de balcão por milhão de tokens de entrada processados pelos modelos de linguagem.",
        examples=[4.00]
    )

    BILLING_LIST_PRICE_PER_MILLION_TOKENS_OUT: float = Field(
        default=16.00,
        ge=0.0,
        description="Preço de balcão por milhão de tokens de saída gerados pelos modelos de linguagem. "
                    "Separado da entrada porque os provedores também cobram os dois de forma distinta.",
        examples=[16.00]
    )

    BILLING_LIST_PRICE_PER_OCR_IMAGE: float = Field(
        default=0.08,
        ge=0.0,
        description="Preço de balcão por imagem lida pelo motor de OCR. Cada página renderizada de um PDF "
                    "conta como uma imagem.",
        examples=[0.08]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # noinspection PyNestedDecorators
    @field_validator("RECEIPT_ALLOWED_MIME", mode="before")
    @classmethod
    def _split_mime_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    # noinspection PyNestedDecorators
    @field_validator(
        "TAX_ANNUAL_BRACKETS",
        "TAX_DEDUCTIBLE_HEALTH_CATEGORIES",
        "TAX_DEDUCTIBLE_EDUCATION_CATEGORIES",
        mode="before"
    )
    @classmethod
    def _split_tax_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    # noinspection PyNestedDecorators
    @field_validator("TAX_EDUCATION_CEILING_BY_YEAR", mode="before")
    @classmethod
    def _split_education_ceilings(cls, value: object) -> object:
        """Aceita `2026:3561.50,2025:3561.50` na variável de ambiente."""
        if isinstance(value, str):
            entries = [item.strip() for item in value.split(",") if item.strip()]

            return {
                int(entry.split(":")[0]): float(entry.split(":")[1])
                for entry in entries
            }

        return value

    # noinspection PyNestedDecorators
    @field_validator("PARETO_ESSENTIAL_CATEGORIES", mode="before")
    @classmethod
    def _split_essential_categories(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value

    @model_validator(mode="after")
    def _validate_pool_bounds(self) -> "ServiceSettings":
        if self.DATABASE_MAX_POOL_SIZE < self.DATABASE_MIN_POOL_SIZE:
            raise ValueError("DATABASE_MAX_POOL_SIZE não pode ser menor que DATABASE_MIN_POOL_SIZE")

        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# noinspection PyArgumentList
@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    return ServiceSettings()
