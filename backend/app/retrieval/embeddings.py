"""Deterministic local embeddings for chunk indexing and retrieval."""

from __future__ import annotations

import hashlib
import math
import re


class HashedEmbeddingModel:
    """A lightweight embedding model that runs on a laptop without external services."""

    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            index = self._token_index(token)
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        return sum(left[index] * right[index] for index in range(min(len(left), len(right))))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9]+", text.lower())

    def _token_index(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % self._dimensions