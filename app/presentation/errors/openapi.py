from typing import Any, Dict, Tuple, Callable, Iterable, Optional

from fastapi import FastAPI
from pydantic.json_schema import models_json_schema

from app.presentation.errors.schemas import ProblemDetailResponse, ValidationProblemResponse


PROBLEM_JSON = "application/problem+json"

_INTERNAL_ERROR_DESCRIPTION = (
    "Falha não tratada no processamento. O corpo não expõe detalhes internos: `title` vale `Erro interno do servidor` "
    "e `detail` traz apenas a mensagem genérica."
)

_VALIDATION_ERROR_DESCRIPTION = (
    "A requisição não satisfaz o contrato do endpoint. `title` vale `Corpo da requisição inválido.` e `errors` traz "
    "uma entrada por campo rejeitado. Violações de regra de negócio compartilham o status, mas trazem o `title` "
    "específico da regra e `errors` vazio."
)

_HTTP_METHODS = frozenset({"get", "put", "post", "patch", "delete", "options", "head", "trace"})


def _response(model_name: str, description: str) -> Dict[str, Any]:
    return {
        "description": description,
        "content": {
            PROBLEM_JSON: {
                "schema": {"$ref": f"#/components/schemas/{model_name}"}
            }
        }
    }


def register_default_responses(app: FastAPI, excluded_path_prefixes: Optional[Iterable[str]] = None) -> None:
    """Injeta 422 e 500 em toda operação do OpenAPI, sem tocar nos decoradores das rotas."""
    excluded: Tuple[str, ...] = tuple(excluded_path_prefixes or ())
    build_schema: Callable[[], Dict[str, Any]] = app.openapi

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = build_schema()

        _, model_definitions = models_json_schema(
            [
                (ProblemDetailResponse, "validation"),
                (ValidationProblemResponse, "validation")
            ],
            ref_template="#/components/schemas/{model}"
        )

        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components.update(model_definitions.get("$defs", {}))

        for path, path_item in schema.get("paths", {}).items():
            if path.startswith(excluded):
                continue

            for method, operation in path_item.items():
                if method.lower() not in _HTTP_METHODS:
                    continue

                responses = operation.setdefault("responses", {})

                responses["422"] = _response(
                    model_name=ValidationProblemResponse.__name__,
                    description=_VALIDATION_ERROR_DESCRIPTION
                )
                responses["500"] = _response(
                    model_name=ProblemDetailResponse.__name__,
                    description=_INTERNAL_ERROR_DESCRIPTION
                )

        app.openapi_schema = schema

        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
