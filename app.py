import streamlit as st
from groq import Groq
from pydub import AudioSegment
import os
import tempfile
import json

# 페이지 설정
st.set_page_config(page_title="나만의 AI 녹취록", page_icon="🎙️")
st.title("🎙️ 초고속 AI 녹취 및 코넬식 요약")
st.write("강의 음성을 텍스트로 변환하고, 가장 효율적인 학습 포맷인 '코넬 노트' 형식으로 완벽하게 요약합니다.")

# Session state 초기화
if "transcript" not in st.session_state:
    st.session_state.transcript = ""

# API Key 입력란 (Secrets 우선 적용)
api_key = ""
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
    st.success("✅ 시스템에 저장된 API 키를 자동으로 불러왔습니다.")
else:
    api_key = st.text_input("Groq API 키를 입력하세요", type="password")
    if not api_key:
        st.info("API 키가 필요합니다. [Groq Console](https://console.groq.com/keys)에서 무료로 발급받으세요.")

# 전공 분야 선택 (프롬프트 튜닝용)
domain_options = {
    "일반 (기본)": "다음은 한국어 음성 기록입니다. 최대한 정확하게 받아쓰기 해주세요.",
    "간호학 (Nursing)": "다음은 간호학 전공 강의 음성 기록입니다. 의학 및 간호학 전문 용어, 해부학 용어, 질환명, 약물명, 병태생리 관련 영단어 및 한국어 용어를 문맥에 맞게 정확하게 받아쓰기 해주세요.",
    "기독교 (Theology/Christianity)": "다음은 기독교 및 신학 강의 음성 기록입니다. 성경 인물, 지명, 신학 용어, 교리, 역사적 배경과 관련된 전문 용어를 문맥에 맞게 정확하게 받아쓰기 해주세요."
}
domain_choice = st.selectbox("📚 강의 전공 분야 선택 (인식률 향상)", list(domain_options.keys()))
system_prompt_stt = domain_options[domain_choice]

# 파일 업로더
uploaded_file = st.file_uploader("음성 파일을 업로드하세요 (mp3, m4a, wav 등)", type=["mp3", "m4a", "wav", "flac", "ogg"])

def process_audio(file, api_key, prompt_text):
    client = Groq(api_key=api_key)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as temp_audio:
        temp_audio.write(file.read())
        temp_audio_path = temp_audio.name
    
    st.info("오디오 파일을 분석하고 있습니다... (파일 크기에 따라 약간의 시간이 소요됩니다)")
    try:
        audio = AudioSegment.from_file(temp_audio_path)
    except Exception as e:
        st.error(f"오디오 파일을 읽는 데 실패했습니다: {e}")
        os.remove(temp_audio_path)
        return ""

    chunk_length_ms = 10 * 60 * 1000
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    
    total_chunks = len(chunks)
    st.success(f"총 {total_chunks}개의 조각으로 나누어 변환을 시작합니다.")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    full_transcript = ""
    
    for i, chunk in enumerate(chunks):
        status_text.text(f"[{i+1}/{total_chunks}] 파트 변환 중...")
        
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
            st.error(f"API 호출 중 오류 발생 (파트 {i+1}): {e}")
            break
        finally:
            os.remove(chunk_file_path)
        
        progress_bar.progress((i + 1) / total_chunks)
        
    os.remove(temp_audio_path)
    return full_transcript

# --- 1. 녹취 진행 로직 ---
if uploaded_file and api_key:
    if st.button("🎙️ 녹취 시작하기"):
        with st.spinner("전체 처리 중..."):
            result_text = process_audio(uploaded_file, api_key, system_prompt_stt)
            if result_text:
                st.session_state.transcript = result_text
                st.success("변환이 완료되었습니다!")

# --- 2. 녹취 결과 및 요약 로직 ---
if st.session_state.transcript:
    st.text_area("녹취 결과 (원본 텍스트)", st.session_state.transcript, height=200)
    st.download_button(
        label="📄 원본 텍스트 다운로드",
        data=st.session_state.transcript,
        file_name="transcript.txt",
        mime="text/plain"
    )
    
    st.divider()
    st.subheader("📝 코넬식 강의 노트 자동 생성")
    
    if st.button("✨ 요약 노트 만들기 (약 10초 소요)"):
        client = Groq(api_key=api_key)
        
        # 엄격하게 통제된 요약 특화 프롬프트
        summary_prompt = """당신은 뛰어난 요약 능력을 가진 대학생들의 학습 튜터입니다.
[엄격한 지시사항]
1. 오직 아래에 제공된 <강의 녹취록>의 내용만을 바탕으로 요약해야 합니다. 절대 외부 지식으로 내용을 지어내지 마세요(Hallucination 금지).
2. 녹취록 내용이 부실하다면 억지로 채우지 말고 있는 사실만 요약하세요.
3. 코넬 노트 필기 방식에 맞춰, 중요한 '핵심 키워드(대주제)'를 뽑고 그에 대한 '상세 설명(소주제)'을 계층적으로 정리하세요.
4. 반드시 아래의 JSON 형식으로만 답변을 출력하세요.

{
  "executive_summary": "강의 전체 내용을 꿰뚫는 핵심 2~3문장 요약",
  "cornell_notes": [
    {
      "keyword": "핵심 개념어 또는 대주제 1",
      "details": [
        "해당 키워드에 대한 상세 설명 1",
        "상세 설명 2 (예시 등)"
      ]
    },
    {
      "keyword": "핵심 개념어 또는 대주제 2",
      "details": [
        "상세 설명 1"
      ]
    }
  ],
  "key_takeaways": ["교수님이 특별히 강조한 포인트나 시험 출제 예상 포인트 1 (없으면 생략)", "포인트 2"]
}"""

        with st.spinner("가장 완벽한 형태로 강의를 요약하고 있습니다..."):
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b", # 최신 주력 모델 사용
                    messages=[
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": f"<강의 녹취록>\n{st.session_state.transcript}\n</강의 녹취록>"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0 # 상상력 차단, 팩트 기반 요약 
                )
                
                # JSON 파싱
                summary_data = json.loads(response.choices[0].message.content)
                
                # --- 화면 출력부 (렌더링) ---
                
                # 1. 전체 요약 (Executive Summary)
                st.markdown("### 🎯 강의 전체 요약")
                st.info(summary_data.get("executive_summary", "요약 내용이 없습니다."))
                
                # 2. 코넬 노트 (상세 요약)
                st.markdown("### 📚 상세 필기 노트 (코넬식)")
                notes = summary_data.get("cornell_notes", [])
                
                if not notes:
                    st.write("상세 요약을 추출할 내용이 부족합니다.")
                else:
                    # Streamlit columns를 활용해 코넬 노트의 느낌(좌/우)을 살림
                    for note in notes:
                        col1, col2 = st.columns([1, 3]) # 1:3 비율 (키워드 : 내용)
                        with col1:
                            st.markdown(f"**{note.get('keyword', '')}**")
                        with col2:
                            for detail in note.get("details", []):
                                st.markdown(f"- {detail}")
                        st.divider() # 구분선
                
                # 3. 핵심 강조 포인트 (Takeaways)
                takeaways = summary_data.get("key_takeaways", [])
                if takeaways:
                    st.markdown("### 🚨 교수님 강조 포인트 (Takeaways)")
                    for pt in takeaways:
                        st.error(f"📌 {pt}")
                
                st.success("요약 노트 생성이 완료되었습니다!")
                
            except Exception as e:
                st.error(f"요약 중 오류가 발생했습니다: {e}")
