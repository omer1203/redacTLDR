from collections.abc import Iterable


def mask_text(text: str, entities: Iterable[dict]) -> tuple[str, dict[str, str]]:
    """
    Apply deterministic typed placeholders to text.

    `entities` are expected to include:
    - entity_type
    - detected_text
    """
    mapping: dict[str, str] = {}
    masked = text
    for entity in entities:
        value = str(entity.get("detected_text", "")).strip()
        if not value:
            continue
        entity_type = str(entity.get("entity_type", "REDACTED")).upper()
        placeholder = mapping.get(value)
        if not placeholder:
            placeholder = f"[{entity_type}]"
            mapping[value] = placeholder
        masked = masked.replace(value, placeholder)
    return masked, mapping
