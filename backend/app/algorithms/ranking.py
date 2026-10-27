from __future__ import annotations


def weighted_mean(components: list[tuple[float, float | None]]) -> float | None:
    available = [(weight, score) for weight, score in components if score is not None]
    total = sum(weight for weight, _score in available)
    if total <= 0:
        return None
    return sum((weight / total) * score for weight, score in available)


def reciprocal_rank_fusion(rankings: list[list[str]], k: int) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
