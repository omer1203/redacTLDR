def span_to_box(span_start: int, span_end: int, line_length: int, line_index: int, total_lines: int) -> dict[str, float]:
    """
    Map text span offsets from a line into normalized page coordinates.

    This is a deterministic approximation used for tests and fallback mapping.
    """
    if span_end <= span_start:
        raise ValueError("span_end must be greater than span_start")
    if line_length <= 0:
        raise ValueError("line_length must be positive")
    if total_lines <= 0:
        raise ValueError("total_lines must be positive")
    if not (0 <= line_index < total_lines):
        raise ValueError("line_index out of bounds")

    start_ratio = max(0.0, min(1.0, span_start / line_length))
    end_ratio = max(0.0, min(1.0, span_end / line_length))
    x = start_ratio
    width = max(0.001, end_ratio - start_ratio)
    y = line_index / total_lines
    height = 1.0 / total_lines

    return {"x": x, "y": y, "width": width, "height": height}
