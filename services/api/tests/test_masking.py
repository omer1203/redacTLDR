from services.api.app.services.masking import mask_text


def test_mask_text_uses_deterministic_placeholders() -> None:
    text = "Alice emailed alice@example.com and alice@example.com replied."
    entities = [
        {"entity_type": "NAME", "detected_text": "Alice"},
        {"entity_type": "EMAIL", "detected_text": "alice@example.com"},
    ]
    masked, mapping = mask_text(text, entities)
    assert "[NAME]" in masked
    assert masked.count("[EMAIL]") == 2
    assert mapping["alice@example.com"] == "[EMAIL]"
