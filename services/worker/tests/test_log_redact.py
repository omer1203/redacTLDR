from services.shared.log_redact import redact_text


def test_redact_text_replaces_contact_shapes():
    raw = "reach ada@example.com or 415-555-0134 and ssn 123-45-6789"
    cleaned = redact_text(raw)
    assert "ada@example.com" not in cleaned
    assert "415-555-0134" not in cleaned
    assert "123-45-6789" not in cleaned
    assert "[email]" in cleaned
    assert "[phone]" in cleaned
    assert "[ssn]" in cleaned
