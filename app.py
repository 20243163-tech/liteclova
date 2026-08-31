import streamlit as st
from groq import Groq
from pydub import AudioSegment
import os
import tempfile
import json

# 페이지 기본 설정 (와이드 모드로 넓게)
st.set_page_config(page_title="강의 노트 AI", layout="centered")

# --- 커스텀 CSS (디자인 고급화, AI 티 없애기) ---
st.markdown("""
<style>
    /* 전체 배경을 깔끔한 연회색으로 */
    .stApp {
        background-color: #f8fafc;
    }
    
    /* 기본 텍스트 폰트 색상 */
    p, li {
        color: #334155;
    }

    /* 제목 스타일 */
    .main-title {
        font-size: 26px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
        padding-top: 20px;
    }
    .sub-title {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 30px;
    }
    
    /* 섹션 제목 */
    .section-header {
        font-size: 18px;
        font-weight: 700;
        color: #1e293b;
        margin-top: 30px;
        margin-bottom: 15px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 8px;
    }

    /* 전체 요약 박스 */
    .summary-box {
        background: #ffffff;
        border-radius: 10px;
        padding: 20px;
        border-left: 4px solid #3b82f6; /* 파란색 포인트 */
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        font-size: 15px;
        line-height: 1.6;
        color: #1e293b;
    }
    
    /* 코넬 노트 박스 */
    .cornell-container {
        background: #ffffff;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        margin-bottom: 16px;
        border: 1px solid #f1f5f9;
    }
    
    .cornell-keyword {
        font-size: 16px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 12px;
        background-color: #f1f5f9;
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
    }
    
    .cornell-detail {
        font-size: 15px;
        color: #475569;
        line-height: 1.7;
        margin-bottom: 6px;
        padding-left: 8px;
        border-left: 2px solid #e2e8f0;
    }
    
    /* 강조 포인트 박스 */
    .takeaway-box {
        background: #fff1f2;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #ffe4e6;
        margin-bottom: 30px;
    }
    
    .takeaway-item {
        color: #be123c;
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# 헤더 디자인
st.markdown("<div class='main-title'>강의 녹음 분석 시스템</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>음성 데이터를 텍스트로 변환하고 구조화된 학습 노트를 생성합니다.</div>", unsafe_allow_html=True)

# Session state 초기화
if "transcript" not in st.session_state:
    st.session_state.transcript = ""

# API Key 로직
api_key = ""
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = st.text_input("Groq API Key", type="password")

# 컨트롤 패널 영역 (박스 안에 깔끔하게)
with st.container(border=True):
    domain_options = {
        "일반 (기본)": "다음은 한국어 음성 기록입니다. 정확하게 받아쓰기 해주세요.",
        "간호학 (Nursing)": "간호학 전공 강의입니다. 의학, 질환명, 약물명 전문 용어를 정확하게 받아쓰기 해주세요.",
        "기독교 (Theology)": "기독교 신학 강의입니다. 성경 인물, 신학 용어, 교리를 정확하게 받아쓰기 해주세요."
    }
    domain_choice = st.selectbox("전공 도메인 선택", list(domain_options.keys()))
    system_prompt_stt = domain_options[domain_choice]
    
    uploaded_file = st.file_uploader("음성 파일 업로드", type=["mp3", "m4a", "wav"])

def process_audio(file, api_key, prompt_text):
    client = Groq(api_key=api_key)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as temp_audio:
        temp_audio.write(file.read())
        temp_audio_path = temp_audio.name
    
    try:
        audio = AudioSegment.from_file(temp_audio_path)
    except Exception as e:
        st.error(f"파일을 읽는 데 실패했습니다: {e}")
        os.remove(temp_audio_path)
        return ""

    chunk_length_ms = 10 * 60 * 1000
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    total_chunks = len(chunks)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    full_transcript = ""
    
    for i, chunk in enumerate(chunks):
        status_text.text(f"처리 중... ({i+1}/{total_chunks})")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as chunk_file:
            chunk.export(chunk_file.name, format="mp3")
            chunk_file_path = chunk_file.name
        
        try:
            with open(chunk_file_path, "rb") as file_to_send:
                transcription = client.audio.transcriptions.create(
                  file=(os.path.basename(chunk_file_path), file_to_send.read()),
                  model="whisper-large-v3",
                  prompt=prompt_text,
                  response_format="text",
                  language="ko"
                )
            full_transcript += transcription + "\n\n"
        except Exception as e:
            st.error(f"오류 발생: {e}")
            break
        finally:
            os.remove(chunk_file_path)
        
        progress_bar.progress((i + 1) / total_chunks)
        
    status_text.empty()
    progress_bar.empty()
    os.remove(temp_audio_path)
    return full_transcript

# --- 1. 녹취 진행 ---
if uploaded_file and api_key:
    if st.button("분석 시작", type="primary", use_container_width=True):
        with st.spinner("음성을 텍스트로 변환 중입니다..."):
            result_text = process_audio(uploaded_file, api_key, system_prompt_stt)
            if result_text:
                st.session_state.transcript = result_text

# --- 2. 결과 출력 및 요약 ---
if st.session_state.transcript:
    st.markdown("<div class='section-header'>원본 스크립트</div>", unsafe_allow_html=True)
    st.text_area("텍스트 데이터", st.session_state.transcript, height=150, label_visibility="collapsed")
    
    if st.button("구조화된 학습 노트 생성", type="primary"):
        client = Groq(api_key=api_key)
        
        summary_prompt = """당신은 수석 연구원입니다.
[지시사항]
1. 오직 아래에 제공된 <강의 녹취록>의 내용만을 바탕으로 정리해야 합니다. (Hallucination 엄격히 금지)
2. 짧은 요약이 아닌 '완벽한 필기 대행'이 목적입니다. 등장하는 모든 개념의 정의, 인과관계, 예시, 수치 등을 최대한 구체적이고 길고 상세하게 기록하세요.
3. 코넬 노트 필기 방식에 맞춰 핵심 키워드(대주제)와 상세 설명(소주제)을 계층화하세요.
4. 아래 JSON 형식으로만 출력하세요.

{
  "executive_summary": "강의 전체 내용을 꿰뚫는 핵심 2~3문장",
  "cornell_notes": [
    {
      "keyword": "핵심 개념어",
      "details": [
        "상세 설명 1",
        "상세 설명 2"
      ]
    }
  ],
  "key_takeaways": ["교수 강조 포인트 1", "포인트 2"]
}"""

        with st.spinner("노트 데이터를 생성 중입니다..."):
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b", 
                    messages=[
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": f"<강의 녹취록>\n{st.session_state.transcript}\n</강의 녹취록>"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                
                summary_data = json.loads(response.choices[0].message.content)
                
                # --- 세련된 UI 렌더링 ---
                
                # 1. 전체 요약
                if summary_data.get("executive_summary"):
                    st.markdown("<div class='section-header'>핵심 요약</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='summary-box'>{summary_data.get('executive_summary')}</div>", unsafe_allow_html=True)
                
                # 2. 코넬 노트
                notes = summary_data.get("cornell_notes", [])
                if notes:
                    st.markdown("<div class='section-header'>상세 필기 노트</div>", unsafe_allow_html=True)
                    for note in notes:
                        details_html = "".join([f"<div class='cornell-detail'>{d}</div>" for d in note.get("details", [])])
                        html = f"""
                        <div class='cornell-container'>
                            <div class='cornell-keyword'>{note.get('keyword', '')}</div>
                            <div>{details_html}</div>
                        </div>
                        """
                        st.markdown(html, unsafe_allow_html=True)
                
                # 3. Takeaways
                takeaways = summary_data.get("key_takeaways", [])
                if takeaways:
                    st.markdown("<div class='section-header'>주요 강조 포인트</div>", unsafe_allow_html=True)
                    takeaways_html = "".join([f"<div class='takeaway-item'>✓ {pt}</div>" for pt in takeaways])
                    st.markdown(f"<div class='takeaway-box'>{takeaways_html}</div>", unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"처리 중 오류가 발생했습니다: {e}")
