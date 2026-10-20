from typing import Any, Dict, Type, TypeVar


T = TypeVar("T")


def from_context(ctx: Dict[str, Any], key: str, expected: Type[T]) -> T:
    """Recupera um recurso do contexto do worker, falhando cedo se o lifespan não o abriu."""
    resource = ctx.get(key)

    if not isinstance(resource, expected):
        raise RuntimeError(f"Recurso '{key}' ausente ou inválido no contexto do worker.")

    return resource
