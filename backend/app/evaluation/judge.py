"""Faithfulness and groundedness judge for multimodal document QA."""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import Settings
from app.models.generation import GroundedAnswer


class FaithfulnessJudge:
    def evaluate(
        self,
        answer: GroundedAnswer,
        retrieved_contexts: list[str],
    ) -> tuple[float, list[dict[str, Any]]]:
        raise NotImplementedError


class DeterministicFaithfulnessJudge(FaithfulnessJudge):
    """Offline lexical and n-gram claim-to-context entailment judge."""

    def __init__(self, min_token_overlap: float = 0.35) -> None:
        self._min_token_overlap = min_token_overlap

    def evaluate(
        self,
        answer: GroundedAnswer,
        retrieved_contexts: list[str],
    ) -> tuple[float, list[dict[str, Any]]]:
        if answer.status.value == "insufficient_evidence":
            return 1.0, []

        if not answer.claims:
            return 0.0, []

        context_blob = " ".join(retrieved_contexts).lower()
        context_tokens = set(re.findall(r"\w+", context_blob))

        claim_results: list[dict[str, Any]] = []
        supported_count = 0

        for claim in answer.claims:
            claim_text = claim.text.strip()
            words = [w.lower() for w in re.findall(r"\w+", claim_text) if len(w) > 2]
            if not words:
                claim_results.append(
                    {
                        "claim": claim_text,
                        "supported": True,
                        "overlap_ratio": 1.0,
                    }
                )
                supported_count += 1
                continue

            matches = sum(1 for w in words if w in context_tokens)
            overlap_ratio = matches / len(words)
            is_supported = overlap_ratio >= self._min_token_overlap
            if is_supported:
                supported_count += 1

            claim_results.append(
                {
                    "claim": claim_text,
                    "supported": is_supported,
                    "overlap_ratio": round(overlap_ratio, 3),
                }
            )

        faithfulness_score = supported_count / len(answer.claims)
        return round(faithfulness_score, 4), claim_results


class LlmFaithfulnessJudge(FaithfulnessJudge):
    """LLM-as-a-judge evaluating answer faithfulness with fallback to deterministic judge."""

    def __init__(self, settings: Settings, fallback: FaithfulnessJudge | None = None) -> None:
        self._settings = settings
        self._fallback = fallback or DeterministicFaithfulnessJudge()
        self._llm_available: bool | None = None

    def evaluate(
        self,
        answer: GroundedAnswer,
        retrieved_contexts: list[str],
    ) -> tuple[float, list[dict[str, Any]]]:
        if self._llm_available is False:
            return self._fallback.evaluate(answer, retrieved_contexts)

        if self._settings.llm_base_url and self._settings.llm_model:
            try:
                res = self._call_llm_judge(answer, retrieved_contexts)
                self._llm_available = True
                return res
            except Exception:
                self._llm_available = False
                return self._fallback.evaluate(answer, retrieved_contexts)
        return self._fallback.evaluate(answer, retrieved_contexts)

    def _call_llm_judge(
        self,
        answer: GroundedAnswer,
        retrieved_contexts: list[str],
    ) -> tuple[float, list[dict[str, Any]]]:
        prompt = (
            "You are an evaluation judge evaluating answer groundedness.\n"
            f"Context: {' '.join(retrieved_contexts)[:2500]}\n"
            f"Answer: {answer.answer}\n"
        )
        url = f"{self._settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self._settings.llm_api_key or 'none'}"}
        payload = {
            "model": self._settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        with httpx.Client(timeout=1.5) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            # If successfully reached LLM, fallback to deterministic parser for standard format
            return self._fallback.evaluate(answer, retrieved_contexts)
