import streamlit as st
from groq import Groq
from pydub import AudioSegment
import os
import tempfile
import json

# 페이지 기본 설정 (와이드 모드, 사이드바 활용)
st.set_page_config(page_title="강의 노트 AI", layout="wide", initial_sidebar_state="expanded")

# --- 커스텀 CSS (카드 디자인 입체감 극대화) ---
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif !important;
    }
    
    /* 🚨 배경색 강제 지정 (카드와 확실히 대비되도록 연회색 적용) */
    .stApp, .main {
        background-color: #f1f5f9 !important;
    }

    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    
    .univ-title {
        font-size: 32px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 8px;
        letter-spacing: -0.5px;
    }
    .univ-subtitle {
        font-size: 16px;
        color: #6b7280;
        margin-bottom: 40px;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 2px solid #e5e7eb;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        font-size: 16px;
        font-weight: 600;
        color: #6b7280;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        color: #6366f1 !important;
        border-bottom: 3px solid #6366f1 !important;
    }

    /* 🚨 요약 카드 뚜렷하게 (흰색 배경 + 입체감 있는 그림자) */
    .summary-card {
        background-color: #ffffff !important;
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 30px;
        border: 1px solid #e2e8f0;
    }
    
    .card-title {
        font-size: 18px;
        font-weight: 700;
        color: #111827;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .card-title::before {
        content: '';
        display: inline-block;
        width: 4px;
        height: 18px;
        background-color: #6366f1;
        border-radius: 2px;
    }

    .card-text {
        font-size: 15px;
        color: #374151;
        line-height: 1.7;
    }

    .keyword-badge {
        background: #eef2ff;
        color: #4f46e5;
        padding: 6px 12px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 15px;
        display: inline-block;
        margin-bottom: 10px;
    }
    
    .detail-list {
        list-style-type: none;
        padding-left: 0;
        margin: 0;
    }
    .detail-list li {
        position: relative;
        padding-left: 16px;
        margin-bottom: 8px;
        font-size: 15px;
        color: #4b5563;
        line-height: 1.6;
    }
    .detail-list li::before {
        content: '•';
        position: absolute;
        left: 0;
        color: #9ca3af;
    }

    .highlight-box {
        background: #fdf2f8;
        border: 1px solid #fce7f3;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        color: #be185d;
        font-weight: 600;
        font-size: 15px;
        display: flex;
        align-items: flex-start;
        gap: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Session state 초기화
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "summary_data" not in st.session_state:
    st.session_state.summary_data = None

# API Key 로직
api_key = ""
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]

def process_audio(file, api_key, prompt_text):
    client = Groq(api_key=api_key)
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as temp_audio:
        temp_audio.write(file.read())
        temp_audio_path = temp_audio.name
    try:
        audio = AudioSegment.from_file(temp_audio_path)
    except Exception as e:
        st.sidebar.error(f"파일 오류: {e}")
        os.remove(temp_audio_path)
        return ""
    chunk_length_ms = 10 * 60 * 1000
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    total_chunks = len(chunks)
    
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    full_transcript = ""
    for i, chunk in enumerate(chunks):
        status_text.text(f"음성 분석 중... ({i+1}/{total_chunks})")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as chunk_file:
            chunk.export(chunk_file.name, format="mp3")
            chunk_file_path = chunk_file.name
        try:
            with open(chunk_file_path, "rb") as file_to_send:
                transcription = client.audio.transcriptions.create(
                  file=(os.path.basename(chunk_file_path), file_to_send.read()),
                  model="whisper-large-v3", prompt=prompt_text, response_format="text", language="ko"
                )
            full_transcript += transcription + "\n\n"
        except Exception as e:
            st.sidebar.error(f"오류: {e}")
            break
        finally:
            os.remove(chunk_file_path)
        progress_bar.progress((i + 1) / total_chunks)
    status_text.empty()
    progress_bar.empty()
    os.remove(temp_audio_path)
    return full_transcript

# 사이드바
with st.sidebar:
    st.markdown("<h2 style='font-size: 20px; font-weight: 800; color: #111827;'>⚙️ 프로젝트 설정</h2>", unsafe_allow_html=True)
    if not api_key:
        api_key = st.text_input("Groq API Key (필수)", type="password")
    domain_options = {
        "일반 (기본)": "다음은 한국어 음성 기록입니다. 정확하게 받아쓰기 해주세요.",
        "간호학 (Nursing)": "간호학 전공 강의입니다. 의학, 질환명, 약물명 전문 용어를 정확하게 받아쓰기 해주세요.",
        "기독교 (Theology)": "기독교 신학 강의입니다. 성경 인물, 신학 용어, 교리를 정확하게 받아쓰기 해주세요."
    }
    domain_choice = st.selectbox("전공 도메인", list(domain_options.keys()))
    system_prompt_stt = domain_options[domain_choice]
    st.markdown("<br>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("새 오디오 업로드", type=["mp3", "m4a", "wav"])
    
    if uploaded_file and api_key:
        if st.button("음성 텍스트 변환 시작", type="primary", use_container_width=True):
            with st.spinner("AI가 음성을 듣고 있습니다..."):
                result_text = process_audio(uploaded_file, api_key, system_prompt_stt)
                if result_text:
                    st.session_state.transcript = result_text
                    st.session_state.summary_data = None 

# 메인 화면
st.markdown("<div class='univ-title'>강의 노트 AI 공간</div>", unsafe_allow_html=True)
st.markdown("<div class='univ-subtitle'>업로드된 강의의 원본 스크립트를 확인하고 AI가 구조화한 핵심 노트를 학습하세요.</div>", unsafe_allow_html=True)

if not st.session_state.transcript:
    st.info("👈 왼쪽 메뉴에서 강의 음성 파일을 업로드하고 분석을 시작해주세요.")
else:
    tab1, tab2 = st.tabs(["📝 AI 요약 노트", "📜 원본 스크립트"])
    
    with tab2:
        st.markdown("<div class='summary-card'>", unsafe_allow_html=True)
        st.text_area("전사 텍스트", st.session_state.transcript, height=500, label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
        st.download_button("텍스트 파일 다운로드", data=st.session_state.transcript, file_name="script.txt", mime="text/plain")

    with tab1:
        if not st.session_state.summary_data:
            st.markdown("<div style='text-align: center; padding: 50px 0;'><p style='color: #6b7280;'>아직 요약된 노트가 없습니다.</p></div>", unsafe_allow_html=True)
            if st.button("✨ 노트 자동 생성하기", type="primary"):
                client = Groq(api_key=api_key)
                summary_prompt = """당신은 수석 연구원입니다.
[지시사항]
1. 오직 제공된 <강의 녹취록>의 내용만을 바탕으로 정리해야 합니다. (Hallucination 엄격히 금지)
2. 짧은 요약이 아닌 '완벽한 필기 대행'이 목적입니다. 등장하는 모든 개념의 정의, 인과관계, 예시, 수치 등을 최대한 구체적이고 길고 상세하게 기록하세요.
3. 아래 JSON 형식으로만 출력하세요.

{
  "executive_summary": "강의 전체 내용을 꿰뚫는 핵심 요약 (3문장 이내)",
  "cornell_notes": [
    {
      "keyword": "핵심 개념어",
      "details": ["상세 설명 1", "상세 설명 2"]
    }
  ],
  "key_takeaways": ["교수 강조 포인트 1", "포인트 2"]
}"""
                with st.spinner("AI 튜터가 강의 노트를 분석하고 구조화하고 있습니다..."):
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
                        st.session_state.summary_data = json.loads(response.choices[0].message.content)
                        st.rerun() 
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
        else:
            data = st.session_state.summary_data
            
            # --- 다운로드 / 인쇄 안내 버튼부 ---
            col_a, col_b = st.columns([8, 2])
            with col_a:
                st.info("💡 **PDF로 저장하는 꿀팁:** 키보드의 `Ctrl + P` (맥은 `Cmd + P`)를 눌러 'PDF로 저장'을 선택하시면 현재의 예쁜 디자인 그대로 저장됩니다!")
            with col_b:
                # 마크다운 텍스트 생성
                md_text = f"# 강의 노트\n\n## 🎯 Executive Summary\n{data.get('executive_summary', '')}\n\n## 📚 상세 필기 노트\n"
                for note in data.get("cornell_notes", []):
                    md_text += f"\n### {note.get('keyword', '')}\n"
                    for d in note.get("details", []):
                        md_text += f"- {d}\n"
                md_text += "\n## 🚨 주요 강조 포인트\n"
                for pt in data.get("key_takeaways", []):
                    md_text += f"- {pt}\n"
                
                st.download_button("📄 텍스트 복사본 다운로드", data=md_text, file_name="ai_notes.md", mime="text/markdown", use_container_width=True)

            # 1. 전체 요약
            if data.get("executive_summary"):
                st.markdown(f"""
                <div class='summary-card'>
                    <div class='card-title'>Executive Summary</div>
                    <div class='card-text'>{data.get('executive_summary')}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # 2. 코넬 노트 
            notes = data.get("cornell_notes", [])
            if notes:
                st.markdown("<div class='summary-card'><div class='card-title'>상세 필기 노트</div>", unsafe_allow_html=True)
                for note in notes:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.markdown(f"<div class='keyword-badge'>{note.get('keyword', '')}</div>", unsafe_allow_html=True)
                    with col2:
                        details_html = "".join([f"<li>{d}</li>" for d in note.get("details", [])])
                        st.markdown(f"<ul class='detail-list'>{details_html}</ul>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px dashed #e5e7eb;'>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # 3. Takeaways
            takeaways = data.get("key_takeaways", [])
            if takeaways:
                st.markdown("<div class='summary-card'><div class='card-title'>핵심 강조 사항 (Takeaways)</div>", unsafe_allow_html=True)
                for pt in takeaways:
                    st.markdown(f"<div class='highlight-box'>💡 {pt}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
