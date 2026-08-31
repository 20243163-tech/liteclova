import streamlit as st
from groq import Groq
from pydub import AudioSegment
import os
import tempfile
import json
import urllib.request
from fpdf import FPDF
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import time

# 페이지 기본 설정
st.set_page_config(page_title="강의 노트 AI", layout="wide", initial_sidebar_state="expanded")

# --- 커스텀 CSS ---
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif !important; }
    .stApp, .main { background-color: #f1f5f9 !important; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e7eb; }
    .univ-title { font-size: 32px; font-weight: 800; color: #111827; margin-bottom: 8px; letter-spacing: -0.5px; }
    .univ-subtitle { font-size: 16px; color: #6b7280; margin-bottom: 40px; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 2px solid #e5e7eb; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-size: 16px; font-weight: 600; color: #6b7280; border: none; }
    .stTabs [aria-selected="true"] { color: #6366f1 !important; border-bottom: 3px solid #6366f1 !important; }
    .summary-card { background-color: #ffffff !important; border-radius: 16px; padding: 32px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); margin-bottom: 30px; border: 1px solid #e2e8f0; }
    .card-title { font-size: 18px; font-weight: 700; color: #111827; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
    .card-title::before { content: ''; display: inline-block; width: 4px; height: 18px; background-color: #6366f1; border-radius: 2px; }
    .card-text { font-size: 15px; color: #374151; line-height: 1.7; }
    .keyword-badge { background: #eef2ff; color: #4f46e5; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block; margin-bottom: 10px; }
    .detail-list { list-style-type: none; padding-left: 0; margin: 0; }
    .detail-list li { position: relative; padding-left: 16px; margin-bottom: 8px; font-size: 15px; color: #4b5563; line-height: 1.6; }
    .detail-list li::before { content: '•'; position: absolute; left: 0; color: #9ca3af; }
    .highlight-box { background: #fdf2f8; border: 1px solid #fce7f3; border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; color: #be185d; font-weight: 600; font-size: 15px; display: flex; align-items: flex-start; gap: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# Firebase 초기화
# ==========================================
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            key_dict = json.loads(st.secrets["FIREBASE_KEY"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase 연결 오류: {e}")
            return None
    return firestore.client()

db = init_firebase()

# Session state 초기화
if "transcript" not in st.session_state: st.session_state.transcript = ""
if "summary_data" not in st.session_state: st.session_state.summary_data = None
if "current_lecture_title" not in st.session_state: st.session_state.current_lecture_title = ""
if "current_subject_id" not in st.session_state: st.session_state.current_subject_id = ""
if "doc_id" not in st.session_state: st.session_state.doc_id = None 

api_key = st.secrets["GROQ_API_KEY"] if "GROQ_API_KEY" in st.secrets else ""

# --- 한글 폰트 다운로드 및 PDF 생성 함수 ---
@st.cache_resource
def load_font():
    font_path = "NanumGothic.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        urllib.request.urlretrieve(url, font_path)
    return font_path

def create_pdf(data):
    font_path = load_font()
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('Nanum', '', font_path, uni=True)
    pdf.set_font('Nanum', '', 20)
    pdf.cell(200, 15, txt="AI 강의 요약 노트", ln=True, align='C')
    pdf.ln(10)
    
    if data.get("executive_summary"):
        pdf.set_font('Nanum', '', 14)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(200, 10, txt="[ Executive Summary ]", ln=True)
        pdf.set_font('Nanum', '', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 8, txt=data.get("executive_summary"))
        pdf.ln(10)
        
    notes = data.get("cornell_notes", [])
    if notes:
        pdf.set_font('Nanum', '', 14)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(200, 10, txt="[ 상세 필기 노트 ]", ln=True)
        pdf.set_text_color(0, 0, 0)
        for note in notes:
            pdf.set_font('Nanum', '', 12)
            pdf.multi_cell(0, 8, txt=f"▶ {note.get('keyword', '')}")
            pdf.set_font('Nanum', '', 10)
            for detail in note.get("details", []):
                pdf.multi_cell(0, 7, txt=f"    - {detail}")
            pdf.ln(5)
            
    takeaways = data.get("key_takeaways", [])
    if takeaways:
        pdf.set_font('Nanum', '', 14)
        pdf.set_text_color(190, 24, 93)
        pdf.cell(200, 10, txt="[ 주요 강조 포인트 ]", ln=True)
        pdf.set_font('Nanum', '', 11)
        pdf.set_text_color(0, 0, 0)
        for pt in takeaways:
            pdf.multi_cell(0, 8, txt=f"💡 {pt}")
            
    return bytes(pdf.output())

# 오디오 처리 함수
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

# ==========================================
# 사이드바 (Firebase 연동)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='font-size: 20px; font-weight: 800; color: #111827;'>📂 나의 학습 폴더</h2>", unsafe_allow_html=True)
    
    if db is None:
        st.error("데이터베이스가 연결되지 않았습니다.")
    else:
        # 과목 폴더 불러오기
        subjects_ref = db.collection('subjects').order_by('created_at').get()
        subjects = {doc.id: doc.to_dict().get('name', '이름 없음') for doc in subjects_ref}
        
        # 새 과목 만들기
        with st.expander("➕ 새 과목 추가하기"):
            new_subject_name = st.text_input("과목 이름 입력", placeholder="예: 간호학개론")
            if st.button("추가", use_container_width=True) and new_subject_name:
                db.collection('subjects').add({
                    'name': new_subject_name,
                    'created_at': firestore.SERVER_TIMESTAMP
                })
                st.rerun()

        if not subjects:
            st.info("먼저 새 과목(폴더)을 추가해주세요.")
        else:
            # 과목 선택
            selected_subject_id = st.selectbox("현재 선택된 과목", list(subjects.keys()), format_func=lambda x: subjects[x])
            st.session_state.current_subject_id = selected_subject_id
            
            # 🚨 과목 삭제 버튼
            with st.expander("🗑️ 현재 과목 삭제"):
                st.write("해당 과목 폴더를 삭제하시겠습니까?")
                if st.button("과목 영구 삭제", type="primary", use_container_width=True):
                    db.collection('subjects').document(selected_subject_id).delete()
                    
                    # 삭제 완료 알림 띄우기 (UX 개선)
                    st.toast(f"과목이 성공적으로 삭제되었습니다!", icon="✅")
                    time.sleep(1) # 알림을 읽을 수 있게 1초 대기
                    
                    st.session_state.current_subject_id = ""
                    st.session_state.transcript = ""
                    st.session_state.summary_data = None
                    st.session_state.current_lecture_title = ""
                    st.session_state.doc_id = None
                    st.rerun()
            
            # --- 신규 녹취 업로드 영역 ---
            st.markdown("<br><h3 style='font-size: 16px; font-weight: 700;'>🎙️ 새 강의 업로드</h3>", unsafe_allow_html=True)
            lecture_title = st.text_input("강의 제목", placeholder="예: 3주차 심혈관계")
            
            domain_options = {
                "일반 (기본)": "다음은 한국어 음성 기록입니다. 정확하게 받아쓰기 해주세요.",
                "간호학 (Nursing)": "간호학 전공 강의입니다. 의학, 질환명, 약물명 전문 용어를 정확하게 받아쓰기 해주세요.",
                "기독교 (Theology)": "기독교 신학 강의입니다. 성경 인물, 신학 용어, 교리를 정확하게 받아쓰기 해주세요."
            }
            domain_choice = st.selectbox("전공 도메인 (음성 인식 최적화)", list(domain_options.keys()))
            system_prompt_stt = domain_options[domain_choice]
            
            uploaded_file = st.file_uploader("오디오 파일 선택", type=["mp3", "m4a", "wav"], label_visibility="collapsed")
            
            if uploaded_file and lecture_title and api_key:
                if st.button("분석 시작", type="primary", use_container_width=True):
                    with st.spinner("AI가 음성을 듣고 있습니다..."):
                        result_text = process_audio(uploaded_file, api_key, system_prompt_stt)
                        if result_text:
                            new_doc = db.collection('lectures').add({
                                'subject_id': selected_subject_id,
                                'title': lecture_title,
                                'transcript': result_text,
                                'summary_json': None,
                                'created_at': firestore.SERVER_TIMESTAMP
                            })
                            st.session_state.transcript = result_text
                            st.session_state.summary_data = None 
                            st.session_state.current_lecture_title = lecture_title
                            st.session_state.doc_id = new_doc[1].id
                            st.rerun()
            elif uploaded_file and not lecture_title:
                st.warning("강의 제목을 입력해야 분석이 시작됩니다.")

            st.divider()
            
            # --- 과거 기록 불러오기 영역 ---
            st.markdown(f"<h3 style='font-size: 16px; font-weight: 700;'>📜 '{subjects[selected_subject_id]}' 과거 기록</h3>", unsafe_allow_html=True)
            
            lectures_ref = db.collection('lectures').where('subject_id', '==', selected_subject_id).get()
            lectures_list = []
            for doc in lectures_ref:
                data = doc.to_dict()
                data['id'] = doc.id
                created_at = data.get('created_at')
                data['sort_time'] = created_at.timestamp() if created_at else 0
                lectures_list.append(data)
                
            lectures_list.sort(key=lambda x: x['sort_time'], reverse=True)
            
            if not lectures_list:
                st.write("아직 저장된 강의가 없습니다.")
            else:
                for lec in lectures_list:
                    if st.button(f"📄 {lec.get('title', '제목 없음')}", key=f"btn_{lec['id']}", use_container_width=True):
                        st.session_state.doc_id = lec['id']
                        st.session_state.current_lecture_title = lec.get('title', '')
                        st.session_state.transcript = lec.get('transcript', '')
                        st.session_state.summary_data = lec.get('summary_json', None)
                        
                        if "messages" in st.session_state:
                            st.session_state.messages = []
                        st.rerun()

# ==========================================
# 메인 화면
# ==========================================
col_title, col_btn_1, col_btn_2 = st.columns([6, 2, 2])
with col_title:
    if st.session_state.current_lecture_title:
        st.markdown(f"<div class='univ-title'>{st.session_state.current_lecture_title}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='univ-title'>강의 노트 AI 공간</div>", unsafe_allow_html=True)
    st.markdown("<div class='univ-subtitle'>사이드바에서 과목을 만들고 새 강의를 업로드하거나 과거 기록을 불러오세요.</div>", unsafe_allow_html=True)

with col_btn_1:
    if st.button("🔄 화면 초기화", use_container_width=True):
        st.session_state.transcript = ""
        st.session_state.summary_data = None
        st.session_state.current_lecture_title = ""
        st.session_state.doc_id = None
        if "messages" in st.session_state: st.session_state.messages = []
        st.rerun()

with col_btn_2:
    if st.session_state.doc_id:
        if st.button("🗑️ 현재 강의 삭제", use_container_width=True):
            db.collection('lectures').document(st.session_state.doc_id).delete()
            
            st.toast("강의가 성공적으로 삭제되었습니다!", icon="✅")
            time.sleep(1)
            
            st.session_state.transcript = ""
            st.session_state.summary_data = None
            st.session_state.current_lecture_title = ""
            st.session_state.doc_id = None
            if "messages" in st.session_state: st.session_state.messages = []
            st.rerun()

if not st.session_state.transcript:
    st.info("👈 왼쪽 사이드바에서 [과목]을 선택하고 강의를 업로드하거나 과거 기록을 클릭해주세요.")
else:
    tab1, tab2, tab3 = st.tabs(["📝 AI 요약 노트", "📜 원본 스크립트", "💬 AI 튜터에게 질문하기"])
    
    with tab2:
        st.markdown("<div class='summary-card'>", unsafe_allow_html=True)
        st.text_area("전사 텍스트", st.session_state.transcript, height=500, label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
        st.download_button("원본 텍스트 다운로드", data=st.session_state.transcript, file_name="script.txt", mime="text/plain")

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
                with st.spinner("AI 튜터가 노트를 분석하고 구조화하고 있습니다..."):
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
                        json_result = json.loads(response.choices[0].message.content)
                        st.session_state.summary_data = json_result
                        
                        if st.session_state.doc_id:
                            db.collection('lectures').document(st.session_state.doc_id).update({
                                'summary_json': json_result
                            })
                            
                        st.rerun() 
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
        else:
            data = st.session_state.summary_data
            
            col_pdf, col_space = st.columns([3, 7])
            with col_pdf:
                pdf_bytes = create_pdf(data)
                st.download_button(
                    label="📥 PDF로 다운로드",
                    data=pdf_bytes,
                    file_name=f"{st.session_state.current_lecture_title}_노트.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
            
            st.markdown("<br>", unsafe_allow_html=True)

            if data.get("executive_summary"):
                st.markdown(f"<div class='summary-card'><div class='card-title'>Executive Summary</div><div class='card-text'>{data.get('executive_summary')}</div></div>", unsafe_allow_html=True)
            
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

            takeaways = data.get("key_takeaways", [])
            if takeaways:
                st.markdown("<div class='summary-card'><div class='card-title'>핵심 강조 사항 (Takeaways)</div>", unsafe_allow_html=True)
                for pt in takeaways:
                    st.markdown(f"<div class='highlight-box'>💡 {pt}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    # --- 탭 3: AI 튜터 질문하기 ---
    with tab3:
        st.markdown("<h3 style='font-size: 18px; font-weight: 700; color: #1e293b;'>💬 현재 강의 내용에 대해 질문하세요</h3>", unsafe_allow_html=True)
        st.write("강의 내용 중 이해가 안 가는 부분이나, 핵심 개념을 다시 설명해달라고 요청해보세요.")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        if prompt := st.chat_input("질문을 입력하세요... (예: 여기서 말한 1형 당뇨의 원인이 뭐야?)"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                client = Groq(api_key=api_key)
                
                tutor_prompt = f"""당신은 이 강의의 전담 조교(Tutor)입니다.
아래 제공된 [강의 원본 텍스트]를 완벽하게 숙지한 상태에서, 학생의 질문에 친절하고 이해하기 쉽게 답변해 주세요.
만약 강의 내용에 없는 것을 물어본다면, "이 강의에서는 다루지 않은 내용입니다"라고 말한 뒤 알고 있는 외부 지식을 조금만 섞어서 대답하세요.

[강의 원본 텍스트 시작]
{st.session_state.transcript}
[강의 원본 텍스트 끝]
"""
                api_messages = [{"role": "system", "content": tutor_prompt}]
                api_messages.extend(st.session_state.messages)
                
                try:
                    response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=api_messages,
                        temperature=0.3
                    )
                    full_response = response.choices[0].message.content
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"채팅 오류: {e}")
