from __future__ import annotations

import math


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return float(sum(a * b for a, b in zip(left, right)))


def mean_vector(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    width = len(vectors[0])
    totals = [0.0] * width
    for vector in vectors:
        for index, value in enumerate(vector):
            totals[index] += value
    count = float(len(vectors))
    return normalize([value / count for value in totals])
