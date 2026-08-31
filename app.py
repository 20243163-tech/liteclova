import streamlit as st
from groq import Groq
from pydub import AudioSegment
import os
import tempfile
import json
import csv
import io

# 페이지 설정
st.set_page_config(page_title="나만의 AI 녹취록", page_icon="🎙️")
st.title("🎙️ 초고속 AI 녹취 및 요약 (Groq Whisper & Llama3)")
st.write("1시간 이상의 강의 파일도 텍스트로 변환하고, 코넬 노트형 학습 자료로 자동 요약해 줍니다.")

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
    "간호학 (Nursing)": "다음은 간호학 전공 강의 음성 기록입니다. 의학 및 간호학 전문 용어, 해부학 용어, 질환명, 약물명, 병태생리 관련 영어 및 한국어 용어를 문맥에 맞게 정확하게 받아쓰기 해주세요.",
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
        label="📄 텍스트 파일로 다운로드",
        data=st.session_state.transcript,
        file_name="transcript.txt",
        mime="text/plain"
    )
    
    st.divider()
    st.subheader("📝 학습용 강의 노트 자동 생성")
    st.write("음성 인식 오류를 AI가 문맥에 맞게 자체 교정하여 완벽한 구조의 요약본을 만듭니다.")
    
    if st.button("✨ 강의 노트 만들기 (약 10~20초 소요)"):
        client = Groq(api_key=api_key)
        
        # LLM 프롬프트 설계 (에러 보정 및 JSON 구조 강제)
        summary_prompt = """당신은 대학생들의 훌륭한 학습 튜터입니다.
제공되는 텍스트는 AI가 음성을 인식한 녹취록이므로 오타나 문맥이 어색한 부분(STT 오류)이 있을 수 있습니다. 당신이 가진 전공 지식을 동원해 문맥을 파악하고 오류를 교정하여 완벽한 학습용 요약본을 만들어야 합니다.
반드시 아래의 JSON 형식으로만 답변을 출력하세요. 마크다운 기호나 다른 설명은 절대 추가하지 말고 오직 JSON만 출력하세요.

{
  "one_line_summary": "강의 전체를 관통하는 핵심 1줄 요약",
  "exam_points": ["교수님이 강조한 포인트나 시험 출제가 예상되는 문장 1", "포인트 2 (없으면 빈 배열)"],
  "flow_summary": [
    {"topic": "강의 대주제 1", "details": ["세부 내용 1", "세부 내용 2"]},
    {"topic": "강의 대주제 2", "details": ["세부 내용 1", "세부 내용 2"]}
  ],
  "expected_questions": [
    {"question": "핵심 개념을 묻는 객관식 또는 단답형 질문 1", "answer": "모범 답안"}
  ],
  "glossary": [
    {"word": "어려운 전공 용어나 핵심 단어 1", "meaning": "해당 단어의 정확한 뜻", "example": "강의에서 사용된 맥락이나 예시"}
  ]
}"""

        with st.spinner("AI 튜터가 노트를 정리하고 있습니다..."):
            try:
                response = client.chat.completions.create(
                    model="llama-3.1-70b-versatile", # 128k 컨텍스트 윈도우 지원
                    messages=[
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": st.session_state.transcript}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                
                # JSON 파싱
                summary_data = json.loads(response.choices[0].message.content)
                
                # --- 화면 출력부 (렌더링) ---
                
                # 1. 1줄 요약
                st.header("🎯 1줄 핵심 요약")
                st.info(summary_data.get("one_line_summary", "내용 없음"))
                
                # 2. 강조 포인트
                exam_points = summary_data.get("exam_points", [])
                if exam_points:
                    st.header("🚨 교수님 강조 포인트 (시험 주의!)")
                    for pt in exam_points:
                        st.error(f"✔️ {pt}")
                
                # 3. 상세 요약 (흐름별)
                st.header("📚 강의 흐름별 요약")
                for section in summary_data.get("flow_summary", []):
                    st.markdown(f"### 📌 {section.get('topic')}")
                    for detail in section.get("details", []):
                        st.markdown(f"- {detail}")
                
                # 4. 예상 질문 (코넬 노트형)
                st.header("❓ 코넬 노트형 셀프 테스트")
                for qna in summary_data.get("expected_questions", []):
                    with st.expander(f"Q. {qna.get('question')}"):
                        st.write(f"**A.** {qna.get('answer')}")
                        
                # 5. 용어 사전 및 CSV 추출
                st.header("📖 핵심 용어 사전")
                glossary = summary_data.get("glossary", [])
                
                if glossary:
                    # 표 형태로 렌더링하기 위한 데이터 가공
                    st.table(glossary)
                    
                    # CSV 만들기
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(["단어", "뜻", "예문"])
                    for item in glossary:
                        writer.writerow([item.get("word"), item.get("meaning"), item.get("example")])
                    
                    st.download_button(
                        label="💾 플래시카드용 CSV 다운로드 (Anki, Quizlet 호환)",
                        data=output.getvalue().encode('utf-8-sig'), # 한글 깨짐 방지용 utf-8-sig
                        file_name="glossary.csv",
                        mime="text/csv"
                    )
                
                st.success("학습용 강의 노트 생성이 완료되었습니다!")
                
            except Exception as e:
                st.error(f"요약 중 오류가 발생했습니다: {e}")
