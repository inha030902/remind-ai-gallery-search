from __future__ import annotations

import json
import os
import re
from typing import Any

from google import genai
from google.genai import types

GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-3.6-flash")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


def analyze_image(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Vision + OCR + tags를 한 번의 멀티모달 호출로 추출한다."""
    client = get_client()
    prompt = """
너는 개인 갤러리 검색을 위한 이미지 인덱서다.
첨부 이미지를 분석하고 아래 JSON만 반환해라. 설명 문장이나 마크다운은 금지한다.
{
  "caption": "이미지 내용을 검색에 유용하도록 한국어 1~2문장으로 설명",
  "ocr_text": "이미지에서 실제로 읽히는 텍스트. 없으면 빈 문자열",
  "tags": ["검색 가능한 핵심 태그 5~10개"],
  "image_type": "screenshot 또는 camera_photo 또는 document 또는 other 중 하나",
  "scene": "장소/상황/분위기/주요 객체를 짧게 요약"
}
텍스트가 보이지 않으면 ocr_text를 지어내지 마라.
""".strip()

    response = client.models.generate_content(
        model=GENERATION_MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
    )
    data = _parse_json(response.text or "")
    return {
        "caption": str(data.get("caption", "")),
        "ocr_text": str(data.get("ocr_text", "")),
        "tags": [str(x) for x in data.get("tags", [])][:12],
        "image_type": str(data.get("image_type", "other")),
        "scene": str(data.get("scene", "")),
    }


def create_image_embedding(
    image_bytes: bytes, mime_type: str, metadata: dict[str, Any]
) -> list[float]:
    """이미지 + 추출 메타데이터를 하나의 multimodal embedding으로 만든다."""
    client = get_client()
    text = metadata_to_text(metadata)
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[
            text,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(result.embeddings[0].values)


def create_query_embedding(query: str) -> list[float]:
    client = get_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=f"검색 질의: {query}",
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(result.embeddings[0].values)


def rerank(query: str, candidates: list[dict[str, Any]]) -> list[int]:
    """상위 후보 메타데이터를 LLM으로 재검증해 관련도 순서를 반환한다."""
    if not candidates:
        return []
    client = get_client()
    compact = []
    for c in candidates:
        compact.append(
            {
                "id": c["id"],
                "caption": c["caption"],
                "ocr_text": c["ocr_text"][:700],
                "tags": c["tags"],
                "image_type": c["image_type"],
                "scene": c["scene"],
                "hybrid_score": round(float(c.get("hybrid_score", 0.0)), 4),
            }
        )

    prompt = f"""
너는 Re:Mind 이미지 검색의 마지막 재순위화 단계다.
사용자 질의와 후보 이미지 메타데이터를 비교해서 관련도가 높은 순서로 정렬해라.
질의에 명시된 조건(스크린샷/직접 찍은 사진, 장소, 메뉴, 시기, 객체 등)을 최우선으로 반영한다.
후보에 없는 사실은 추측하지 마라.

사용자 질의:
{query}

후보:
{json.dumps(compact, ensure_ascii=False)}

아래 JSON만 반환해라.
{{"ranked_ids": [가장 관련도 높은 id, ...]}}
""".strip()

    response = client.models.generate_content(model=GENERATION_MODEL, contents=prompt)
    data = _parse_json(response.text or "")
    ids = [int(x) for x in data.get("ranked_ids", []) if str(x).isdigit()]
    valid = {int(c["id"]) for c in candidates}
    ordered = [x for x in ids if x in valid]
    # 모델이 누락한 후보는 기존 hybrid 순서를 유지하며 뒤에 붙인다.
    ordered.extend(int(c["id"]) for c in candidates if int(c["id"]) not in ordered)
    return ordered


def metadata_to_text(metadata: dict[str, Any]) -> str:
    return " | ".join(
        [
            f"설명: {metadata.get('caption', '')}",
            f"OCR: {metadata.get('ocr_text', '')}",
            f"태그: {', '.join(metadata.get('tags', []))}",
            f"유형: {metadata.get('image_type', '')}",
            f"장면: {metadata.get('scene', '')}",
        ]
    )


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini 응답을 JSON으로 해석하지 못했습니다: {text[:300]}") from exc
