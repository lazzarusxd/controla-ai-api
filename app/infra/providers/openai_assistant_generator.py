from typing import Any, Dict, List, Optional

import httpx

from app.config.logging_setup import logger
from app.application.interfaces import IAssistantGenerator
from app.application.services.usage_meter import UsageMeter
from app.infra.providers.token_usage import report_token_usage
from app.domain.exceptions.assistant_exceptions import AssistantUnavailableError
from app.application.dto import AssistantGenerationRequestDTO, GeneratedAnswerDTO


class OpenAiAssistantGenerator(IAssistantGenerator):

    def __init__(
            self,
            model: str,
            api_key: str,
            base_url: str,
            timeout_seconds: int,
            usage_meter: Optional[UsageMeter] = None
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._usage_meter = usage_meter
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def generate(self, assistant_generation_request: AssistantGenerationRequestDTO) -> GeneratedAnswerDTO:
        context_text = assistant_generation_request.context.to_prompt_text(
            max_characters=assistant_generation_request.max_context_characters
        )

        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": "Você é o assistente financeiro do Controla AI e responde a usuários brasileiros sobre as "
                           "próprias finanças. Responda exclusivamente com base nos trechos de contexto fornecidos, "
                           "que são os lançamentos reais da conta de quem pergunta. Nunca invente valores, datas, "
                           "categorias ou estabelecimentos que não estejam no contexto, e nunca some ou projete "
                           "números que o contexto não sustente. Se o contexto não permitir responder, diga isso "
                           "com clareza e indique o que faltaria para responder. Escreva em português do Brasil, "
                           "em tom direto e cordial, com valores no formato R$ 0,00 e datas em dd/mm/aaaa. Você "
                           "organiza e explica dados; não recomenda produtos financeiros, não indica investimentos "
                           "específicos e não substitui assessoria regulada. Cite os trechos usados pelo número "
                           "entre colchetes quando fizer afirmações numéricas. Os turnos anteriores desta conversa "
                           "servem apenas para resolver referências como \"e no mês anterior?\": eles não são fonte "
                           "de dado financeiro, que vem somente do contexto fornecido nesta mensagem. Se algo já foi "
                           "dito nesta conversa, não repita a explicação por inteiro: retome o ponto em uma frase "
                           "curta e concentre a resposta no que muda em relação ao que você já respondeu. Não reabra "
                           "a conversa a cada turno com saudações ou reapresentações do panorama financeiro."
            }
        ]

        for turn in assistant_generation_request.history:
            messages.append({"role": "user", "content": turn.question})
            messages.append({"role": "assistant", "content": turn.answer})

        messages.append(
            {
                "role": "user",
                "content": (
                    f"Contexto financeiro da conta:\n{context_text}\n\n"
                    f"Pergunta do usuário:\n{assistant_generation_request.question}"
                )
            }
        )

        payload: Dict[str, Any] = {
            "temperature": 0,
            "model": self._model,
            "messages": messages
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    url=f"{self._base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}"
                    }
                )

                response.raise_for_status()

                body = response.json()

        except httpx.HTTPError as exc:
            logger.warning("assistant_request_failed", error=type(exc).__name__)

            raise AssistantUnavailableError("Provedor de linguagem indisponível para o assistente.") from exc

        await report_token_usage(body=body, usage_meter=self._usage_meter)

        return self._to_dto(body=body, model=self._model)

    @staticmethod
    def _to_dto(body: Dict[str, Any], model: str) -> GeneratedAnswerDTO:
        try:
            choices = body.get("choices") or []
            answer = choices[0].get("message").get("content")

            if not answer or not answer.strip():
                raise ValueError("Resposta vazia.")

            return GeneratedAnswerDTO(model=model, answer=answer.strip())

        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            logger.warning("assistant_response_unusable", error=type(exc).__name__)

            raise AssistantUnavailableError("Resposta do provedor fora do contrato esperado.") from exc
