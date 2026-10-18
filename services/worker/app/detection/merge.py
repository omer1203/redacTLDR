"""Collapse overlapping hits into one detection.

Policy runs before this step, so every input already has a decision and
ignored types are gone. That order matters: an ignored DATE_TIME with a
higher score must not swallow an auto-redacted DATE_OF_BIRTH on the same text.

Within an overlapping cluster the winner is the hit that redacts by default,
then a specific type over a generic one (DATE_OF_BIRTH over DATE_TIME,
SOCIAL_PROFILE_URL over URL), then the higher confidence, then the longer
span. The stored range is the union of the whole cluster, so nothing a
detector flagged is left uncovered.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from services.shared.policy import PolicyDecision
from services.worker.app.detection.models import Candidate


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    decision: PolicyDecision


@dataclass(frozen=True)
class Merged:
    start: int
    end: int
    winner: Scored


_GENERIC_TYPES = frozenset({"DATE_TIME", "URL"})


def _rank(item: Scored) -> tuple[bool, bool, float, int]:
    candidate = item.candidate
    return (
        item.decision.accepted,
        candidate.entity_type not in _GENERIC_TYPES,
        candidate.confidence,
        candidate.end - candidate.start,
    )


def merge_overlapping(items: Iterable[Scored]) -> list[Merged]:
    ordered = sorted(items, key=lambda item: (item.candidate.start, -item.candidate.end))
    merged: list[Merged] = []
    cluster: list[Scored] = []
    cluster_end = -1

    def flush() -> None:
        if not cluster:
            return
        merged.append(
            Merged(
                start=min(item.candidate.start for item in cluster),
                end=max(item.candidate.end for item in cluster),
                winner=max(cluster, key=_rank),
            )
        )

    for item in ordered:
        # Strict `<`: touching spans ("a@b.com" then ",") are separate entities.
        if cluster and item.candidate.start < cluster_end:
            cluster.append(item)
            cluster_end = max(cluster_end, item.candidate.end)
            continue
        flush()
        cluster = [item]
        cluster_end = item.candidate.end
    flush()
    return merged
