from __future__ import annotations


def plain_text(value, *, multiline: bool = False, max_length: int = 2000) -> str:
    text = str(value or "").strip()
    if multiline:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        normalized = "\n".join(line for line in lines if line)
    else:
        normalized = " ".join(text.split())
    if len(normalized) > int(max_length):
        raise ValueError(f"O TEXTO EXCEDE O LIMITE DE {int(max_length)} CARACTERES.")
    return normalized


def upper_text(value, *, multiline: bool = False, max_length: int = 2000) -> str:
    """Normaliza texto de entrada e grava sempre em maiúsculas."""
    return plain_text(value, multiline=multiline, max_length=max_length).upper()


def upper_code(value) -> str:
    return upper_text(value, max_length=120).replace("–", "-").replace("—", "-")
