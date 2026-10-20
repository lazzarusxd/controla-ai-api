import unicodedata


def normalize_label(value: str) -> str:
    """Reduz um rótulo livre à forma comparável: sem acento, sem caixa e sem espaço redundante."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))

    return " ".join(without_accents.casefold().split())
