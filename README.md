# Re:Mind — AI Gallery Search MVP

CODEGATE 2026 AI Startup 해커톤에서 기획한 **대화형 스마트 갤러리 검색**을 실제 동작하는 웹 MVP로 구현한 프로젝트입니다.

## 핵심 기능

- 여러 장의 사진/스크린샷 업로드
- Gemini Vision 기반 이미지 설명 + OCR 텍스트 + 태그 + 이미지 유형 자동 추출
- `gemini-embedding-2` 기반 이미지/텍스트 멀티모달 임베딩
- 임베딩 유사도 + OCR/태그 키워드 점수를 결합한 Hybrid Search
- LLM 기반 상위 검색 결과 재순위화(Reranking)
- "이 중에서 직접 찍은 사진만"처럼 이전 검색 맥락에 조건을 더하는 Conversational Refine
- SQLite 기반 로컬 메타데이터/임베딩 저장

## 구조

```text
remind_mvp/
├─ app.py
├─ search_engine.py
├─ storage.py
├─ services/
│  └─ gemini_service.py
├─ data/
│  └─ images/
├─ .env.example
├─ .gitignore
├─ requirements.txt
└─ README.md
```

## 1. 설치

Python 3.11 이상 권장

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

## 2. Gemini API Key 설정

`.env.example`을 복사해 `.env`를 만듭니다.

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

`.env` 안의 값을 수정합니다.

```env
GEMINI_API_KEY=발급받은_API_KEY
GEMINI_GENERATION_MODEL=gemini-3.6-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-2
```

> `.env`는 `.gitignore`에 포함되어 있으므로 GitHub에 업로드하지 마세요.

## 3. 실행

```bash
streamlit run app.py
```

브라우저에서 Streamlit 페이지가 열리면:

1. **이미지 색인** 탭에서 사진/스크린샷 10~30장 업로드
2. **AI로 분석하고 색인하기** 클릭
3. **AI 검색** 탭에서 자연어 검색
4. 결과가 나온 뒤 `이 중에서 직접 찍은 사진만 보여줘` 같은 후속 조건 입력

## 데모에 추천하는 이미지 세트

한 번의 검색에서 차이가 잘 보이도록 아래처럼 12~20장 정도 준비하세요.

- 여행지 직접 촬영 사진 4~5장
- 맛집/지도/메뉴 스크린샷 4~5장
- 쇼핑 상품 스크린샷 3~4장
- 관계없는 일상 사진 3~4장

추천 데모 검색:

```text
포항에서 저장한 음식점 찾아줘
```

후속 검색:

```text
이 중에서 직접 찍은 사진만 보여줘
```

또는

```text
파스타 메뉴가 보이는 스크린샷만 보여줘
```

## GitHub 업로드

GitHub에서 빈 저장소를 하나 만든 뒤, 프로젝트 폴더에서 아래 명령을 실행합니다.

```bash
git init
git add .
git commit -m "feat: build ReMind AI gallery search MVP"
git branch -M main
git remote add origin https://github.com/YOUR_ID/remind-ai-gallery-search.git
git push -u origin main
```

그러면 최종 주소는 다음 형태가 됩니다.

```text
https://github.com/YOUR_ID/remind-ai-gallery-search
```

## 포트폴리오 설명 예시

> CODEGATE 2026 AI Startup 해커톤에서 기획한 스마트 갤러리 검색 아이디어를 웹 MVP로 구현했습니다. Gemini 기반 이미지 분석/OCR과 멀티모달 임베딩, 키워드 점수를 결합해 후보를 검색하고 LLM 재순위화를 적용했습니다. 자연어 검색 이후 후속 조건을 더해 결과를 좁힐 수 있는 Conversational Refine 흐름을 구현했습니다.

## 현재 MVP의 범위

- 실제 휴대폰 갤러리 권한 연동 대신 웹 파일 업로드 방식
- 촬영 날짜/위치 EXIF 필터는 아직 미구현
- 대규모 Vector DB 대신 SQLite에 embedding을 저장하고 NumPy로 유사도를 계산
- 개인용 데모를 목표로 하므로 인증/멀티유저 기능은 미구현

이 범위를 README에 명확히 적어두는 것이 포트폴리오에서 오히려 신뢰도를 높여줍니다.
