from __future__ import annotations

import hashlib
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from search_engine import search_images
from services.gemini_service import analyze_image, create_image_embedding
from storage import IMAGE_DIR, clear_all, count_images, init_db, list_images, save_image_record

load_dotenv()
init_db()

st.set_page_config(page_title="Re:Mind — AI Gallery Search", page_icon="🔎", layout="wide")

st.markdown(
    """
<style>
:root { --ink:#172033; --muted:#697386; --line:#e9edf3; --blue:#4d72ff; --soft:#f5f7ff; }
.block-container {max-width: 1120px; padding-top: 2rem; padding-bottom: 4rem;}
.hero {padding: 28px 30px; border:1px solid var(--line); border-radius:24px; background:linear-gradient(135deg,#f8f9ff,#eef3ff); margin-bottom:18px;}
.hero h1 {font-size:2.25rem; margin:0 0 6px 0; color:var(--ink);}
.hero p {margin:0; color:var(--muted); font-size:1.02rem;}
.kicker {display:inline-block; padding:6px 10px; border-radius:999px; background:#e9eeff; color:#3858c9; font-weight:700; font-size:.82rem; margin-bottom:12px;}
.result-card {border:1px solid var(--line); border-radius:18px; padding:12px; background:white; height:100%;}
.meta {color:var(--muted); font-size:.86rem; line-height:1.5; margin-top:8px;}
.score-pill {display:inline-block; background:#f1f4ff; color:#3f5bc0; border-radius:999px; padding:4px 8px; font-size:.76rem; font-weight:700; margin-right:4px;}
.small-label {font-size:.82rem; color:var(--muted); font-weight:700;}
[data-testid="stFileUploader"] {border:1px dashed #cfd6e4; border-radius:18px; padding:10px;}
</style>
""",
    unsafe_allow_html=True,
)

for key, default in {
    "current_query": "",
    "conversation": [],
    "results": [],
}.items():
    st.session_state.setdefault(key, default)

st.markdown(
    """
<div class="hero">
  <div class="kicker">CODEGATE 2026 · AI Gallery Search MVP</div>
  <h1>Re:Mind</h1>
  <p>정확한 키워드가 기억나지 않아도, 자연어로 찾고 대화하듯 검색 조건을 좁혀보세요.</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Gallery Index")
    st.metric("색인된 이미지", count_images())
    st.caption("이미지는 로컬 data/images에 저장되고, 검색 메타데이터와 임베딩은 SQLite에 저장됩니다.")
    if st.button("전체 인덱스 초기화", use_container_width=True):
        clear_all()
        st.session_state.results = []
        st.session_state.current_query = ""
        st.session_state.conversation = []
        st.rerun()

    st.divider()
    st.caption("Models")
    st.code(
        f"Vision/LLM: {os.getenv('GEMINI_GENERATION_MODEL','gemini-3.6-flash')}\n"
        f"Embedding: {os.getenv('GEMINI_EMBEDDING_MODEL','gemini-embedding-2')}",
        language=None,
    )

upload_tab, search_tab, timeline_tab = st.tabs(["1. 이미지 색인", "2. AI 검색", "3. 전체 갤러리"])

with upload_tab:
    st.subheader("사진과 스크린샷을 먼저 색인하세요")
    st.caption("MVP에서는 휴대폰 갤러리 직접 연동 대신 파일 업로드 방식으로 검증합니다.")
    files = st.file_uploader(
        "PNG/JPG 이미지를 여러 장 선택",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )
    if files and st.button("AI로 분석하고 색인하기", type="primary"):
        if not os.getenv("GEMINI_API_KEY"):
            st.error(".env 파일에 GEMINI_API_KEY를 먼저 설정해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            for idx, uploaded in enumerate(files, start=1):
                image_bytes = uploaded.getvalue()
                digest = hashlib.sha1(image_bytes).hexdigest()[:12]
                ext = Path(uploaded.name).suffix.lower() or ".jpg"
                target = IMAGE_DIR / f"{digest}{ext}"
                if target.exists():
                    status.info(f"{uploaded.name}: 이미 저장된 파일이라 건너뜁니다.")
                else:
                    try:
                        status.info(f"{uploaded.name}: Vision/OCR 분석 중...")
                        metadata = analyze_image(image_bytes, uploaded.type or "image/jpeg")
                        status.info(f"{uploaded.name}: 멀티모달 임베딩 생성 중...")
                        embedding = create_image_embedding(
                            image_bytes, uploaded.type or "image/jpeg", metadata
                        )
                        target.write_bytes(image_bytes)
                        save_image_record(
                            filename=uploaded.name,
                            stored_path=str(target),
                            mime_type=uploaded.type or "image/jpeg",
                            metadata=metadata,
                            embedding=embedding,
                        )
                    except Exception as exc:
                        st.error(f"{uploaded.name} 처리 실패: {exc}")
                progress.progress(idx / len(files))
            status.success("색인이 완료되었습니다. AI 검색 탭에서 검색해보세요.")
            st.rerun()

with search_tab:
    st.subheader("대화형 하이브리드 검색")
    st.caption("임베딩 유사도 + OCR/태그 키워드 점수로 후보를 만들고, LLM이 상위 후보를 재순위화합니다.")

    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "자연어 검색",
            value=st.session_state.current_query,
            placeholder="예: 작년 여름에 저장한 파스타 맛집 / 포항 음식점 스크린샷",
            label_visibility="collapsed",
        )
    with col_btn:
        run = st.button("검색", type="primary", use_container_width=True)

    if run and query.strip():
        st.session_state.current_query = query.strip()
        st.session_state.conversation = [("user", query.strip())]
        try:
            with st.spinner("갤러리에서 관련 이미지를 찾는 중..."):
                st.session_state.results = search_images(query.strip(), list_images(), top_k=8)
        except Exception as exc:
            st.error(f"검색 중 오류가 발생했습니다: {exc}")

    if st.session_state.current_query:
        st.markdown(f"**현재 검색 맥락** · {st.session_state.current_query}")

    if st.session_state.results:
        st.success(f"관련도가 높은 이미지 {len(st.session_state.results)}장을 찾았습니다.")
        cols = st.columns(4)
        for i, item in enumerate(st.session_state.results):
            with cols[i % 4]:
                st.image(item["stored_path"], use_container_width=True)
                st.markdown(
                    f"<span class='score-pill'>Hybrid {item.get('hybrid_score',0):.2f}</span>"
                    f"<span class='score-pill'>{item.get('image_type','')}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{item['caption'][:80]}**")
                if item.get("ocr_text"):
                    st.caption("OCR · " + item["ocr_text"][:120])
                if item.get("tags"):
                    st.caption("#" + " #".join(item["tags"][:6]))

        st.divider()
        st.markdown("#### 조건을 더해서 좁혀보기")
        refine = st.chat_input("예: 이 중에서 직접 찍은 사진만 보여줘")
        if refine:
            previous = st.session_state.current_query
            refined_query = f"이전 검색 조건: {previous}. 추가 조건: {refine}"
            st.session_state.current_query = refined_query
            st.session_state.conversation.append(("user", refine))
            try:
                with st.spinner("이전 검색 맥락을 유지하며 결과를 좁히는 중..."):
                    st.session_state.results = search_images(refined_query, list_images(), top_k=8)
                st.rerun()
            except Exception as exc:
                st.error(f"검색 조건을 좁히는 중 오류가 발생했습니다: {exc}")
    elif st.session_state.current_query:
        st.info("관련 이미지를 찾지 못했습니다. 다른 표현으로 검색해보세요.")
    else:
        st.info("먼저 이미지를 색인한 뒤 자연어로 검색해보세요.")

with timeline_tab:
    st.subheader("색인된 전체 이미지")
    rows = list_images()
    if not rows:
        st.info("아직 색인된 이미지가 없습니다.")
    else:
        cols = st.columns(5)
        for i, item in enumerate(rows):
            with cols[i % 5]:
                st.image(item["stored_path"], use_container_width=True)
                st.caption(item["filename"])
                st.caption(item["caption"][:75])
