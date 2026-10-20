from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.application.dto import EraseAccountRequestDTO
from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.accounts.schemas import ErasureConfirmationHeader
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.erasure.erase_account import EraseAccountUseCase
from app.presentation.api.v1.accounts.dependencies import get_erase_account_usecase


router = APIRouter(prefix="/users", tags=["Eliminação de Dados"])

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]


@router.delete(
    path="/{user_id}",
    operation_id="erase-account-v1",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina definitivamente a conta do usuário final.",
    description="Exclusão física e irreversível do titular e de tudo que dele deriva: lançamentos, "
                "comprovantes e seus arquivos, recorrências e avisos emitidos, patrimônio, metas, "
                "deduções fiscais, histórico do assistente, vetores semânticos e exportações ainda "
                "dentro do prazo de retenção. Não há lixeira, não há inativação e não há reversão.\n\n"
                "A operação é síncrona. Ao contrário da exportação, não há artefato a produzir nem "
                "trabalho proporcional ao volume: o expurgo estruturado é um único comando e a remoção "
                "dos arquivos é sequencial. Um aceite assíncrono obrigaria o integrador a consultar o "
                "andamento de um recurso que já deixou de existir.\n\n"
                "A confirmação é obrigatória e viaja no cabeçalho `X-Confirm-Erasure`, que deve repetir "
                "o identificador presente no caminho. Sem ela nada é apagado.\n\n"
                "A resposta não descreve o que foi eliminado. O comprovante existe, mas vive no registro "
                "estruturado de auditoria, com a contagem por recurso e sem qualquer campo de conteúdo "
                "pessoal: devolver ao chamador um retrato do volume de dados do titular no instante da "
                "eliminação contrariaria o próprio propósito da operação.\n\n"
                "O parceiro autenticado não está no escopo.",
    responses={
        204: {
            "description": "Conta eliminada. Sem corpo de resposta. O identificador deixa de ser "
                           "resolvível em qualquer rota da API."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Usuário inexistente, já eliminado ou pertencente a outro parceiro. As três "
                           "condições são indistinguíveis por decisão de segurança. É também a resposta "
                           "da reentrada: o verbo é idempotente no efeito, não na representação, e "
                           "devolver 204 outra vez afirmaria ter eliminado algo que já não estava lá. "
                           "`title` vale `Usuário não encontrado.`."
        },
        428: {
            "model": ProblemDetailResponse,
            "description": "Cabeçalho de confirmação ausente ou divergente do identificador do caminho. "
                           "Nada foi apagado. `title` vale `Confirmação de eliminação ausente.`."
        }
    }
)
async def erase_account(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        confirmation: ErasureConfirmationHeader = None,
        erase_account_usecase: EraseAccountUseCase = Depends(get_erase_account_usecase)
) -> None:
    await erase_account_usecase.execute(
        erase_account_request=EraseAccountRequestDTO(
            user_id=user_id,
            confirmation=confirmation,
            partner_id=current_partner.partner_id
        )
    )
