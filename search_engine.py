from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

from services.gemini_service import create_query_embedding, rerank


def search_images(query: str, rows: list[dict[str, Any]], top_k: int = 8) -> list[dict[str, Any]]:
    if not query.strip() or not rows:
        return []

    qvec = np.asarray(create_query_embedding(query), dtype=float)
    results: list[dict[str, Any]] = []

    for row in rows:
        ivec = np.asarray(row.get("embedding", []), dtype=float)
        vector_score = cosine(qvec, ivec) if ivec.size else 0.0
        keyword_score = lexical_score(query, row)
        # 의미 검색을 중심으로 하되 OCR/태그의 정확한 일치도도 살린다.
        hybrid = 0.72 * vector_score + 0.28 * keyword_score
        item = dict(row)
        item["vector_score"] = vector_score
        item["keyword_score"] = keyword_score
        item["hybrid_score"] = hybrid
        results.append(item)

    results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    shortlist = results[: max(top_k, 10)]

    try:
        ranked_ids = rerank(query, shortlist)
        by_id = {int(r["id"]): r for r in shortlist}
        reranked = [by_id[i] for i in ranked_ids if i in by_id]
        return reranked[:top_k]
    except Exception:
        # LLM 재순위화가 실패해도 검색 자체는 동작하도록 fallback.
        return results[:top_k]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def lexical_score(query: str, row: dict[str, Any]) -> float:
    q_tokens = set(_tokens(query))
    if not q_tokens:
        return 0.0
    haystack = " ".join(
        [
            row.get("caption", ""),
            row.get("ocr_text", ""),
            " ".join(row.get("tags", [])),
            row.get("image_type", ""),
            row.get("scene", ""),
        ]
    ).lower()

    hits = sum(1 for token in q_tokens if token in haystack)
    score = hits / max(len(q_tokens), 1)

    # 사용자가 자주 말할 법한 이미지 유형 표현을 가볍게 보정한다.
    q = query.lower()
    image_type = row.get("image_type", "")
    if any(x in q for x in ["직접 찍", "카메라 사진", "내가 찍"]):
        score += 0.35 if image_type == "camera_photo" else -0.10
    if "스크린샷" in q or "캡처" in q:
        score += 0.35 if image_type == "screenshot" else -0.10

    return max(0.0, min(1.0, score))


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()) if len(t) >= 2]
