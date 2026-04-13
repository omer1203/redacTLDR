import pytest

from services.worker.app.geometry import span_to_box
from services.worker.app.redaction import clamp_bbox


def test_span_to_box_maps_offset_to_normalized_bbox() -> None:
    box = span_to_box(span_start=10, span_end=20, line_length=100, line_index=2, total_lines=10)
    assert box == {"x": 0.1, "y": 0.2, "width": 0.1, "height": 0.1}


def test_span_to_box_rejects_invalid_span() -> None:
    with pytest.raises(ValueError):
        span_to_box(span_start=5, span_end=5, line_length=100, line_index=0, total_lines=1)


def test_clamp_bbox_constrains_values() -> None:
    box = clamp_bbox({"x": -1, "y": 0.8, "width": 4, "height": 1})
    assert box == {"x": 0.0, "y": 0.8, "width": 1.0, "height": 0.19999999999999996}
