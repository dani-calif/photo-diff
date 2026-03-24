from __future__ import annotations

import math
from typing import Sequence


class CosineSimilarityService:
    def cosine_similarity(
        self, vector_a: Sequence[float], vector_b: Sequence[float]
    ) -> float:
        if len(vector_a) != len(vector_b):
            raise ValueError(
                f"Embedding dimensions do not match: {len(vector_a)} vs {len(vector_b)}"
            )
        if not vector_a:
            raise ValueError("Embedding vectors are empty.")

        dot = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a))
        norm_b = math.sqrt(sum(b * b for b in vector_b))
        if norm_a == 0 or norm_b == 0:
            raise ValueError("Cannot compute cosine similarity for zero-magnitude vector.")
        return dot / (norm_a * norm_b)
