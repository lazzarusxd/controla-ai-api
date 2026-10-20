from typing import Annotated, Optional

from fastapi import Header


ERASURE_CONFIRMATION_HEADER = "X-Confirm-Erasure"

ErasureConfirmationHeader = Annotated[
    Optional[str],
    Header(
        alias=ERASURE_CONFIRMATION_HEADER,
        description="Confirmação explícita da eliminação. Deve repetir exatamente o identificador do "
                    "usuário presente no caminho.\n\n"
                    "A confirmação viaja em cabeçalho, e não em corpo, porque a RFC 9110 declara indefinida "
                    "a semântica de corpo em `DELETE` e intermediários podem descartá-lo. Exigir que o "
                    "integrador repita o identificador impede que uma varredura acidental de rotas elimine "
                    "uma conta, e deixa rastro no registro de acesso.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
]
