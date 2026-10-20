from typing import Final

from fastapi.security import HTTPBearer, OAuth2
from fastapi.openapi.models import OAuthFlowClientCredentials, OAuthFlows


oauth2_client_credentials: Final[OAuth2] = OAuth2(
    auto_error=False,
    scheme_name="OAuth2ClientCredentials",
    description="Fluxo `client_credentials` da RFC 6749. Informe o `client_id` e o `client_secret` do parceiro "
                "e a própria interface obtém o access token, renovando-o pelo mesmo endpoint quando expirar.",
    flows=OAuthFlows(
        clientCredentials=OAuthFlowClientCredentials(
            scopes={},
            tokenUrl="/v1/oauth/token",
            refreshUrl="/v1/oauth/token"
        )
    )
)

bearer_token: Final[HTTPBearer] = HTTPBearer(
    auto_error=False,
    bearerFormat="JWE",
    scheme_name="BearerToken",
    description="Apresentação direta de um access token já emitido, conforme a RFC 6750. Cole apenas o valor do "
                "`access_token` devolvido pelo endpoint de emissão, sem o prefixo `Bearer`.",
)
