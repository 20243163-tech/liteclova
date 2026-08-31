import streamlit as st
from groq import Groq
from pydub import AudioSegment
import os
import tempfile
import math

# 페이지 설정
st.set_page_config(page_title="나만의 AI 녹취록", page_icon="🎙️")
st.title("🎙️ 초고속 AI 녹취 변환기 (Groq Whisper)")
st.write("1시간 이상의 대용량 파일도 10분 단위로 자동 분할하여 빠르게 텍스트로 변환합니다.")

# API Key 입력란
api_key = st.text_input("Groq API 키를 입력하세요", type="password")

if not api_key:
    st.info("API 키가 필요합니다. [Groq Console](https://console.groq.com/keys)에서 무료로 발급받으세요.")

# 파일 업로더
uploaded_file = st.file_uploader("음성 파일을 업로드하세요 (mp3, m4a, wav 등)", type=["mp3", "m4a", "wav", "flac", "ogg"])

def process_audio(file, api_key):
    client = Groq(api_key=api_key)
    
    # pydub으로 처리하기 위해 업로드된 파일을 임시 파일로 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as temp_audio:
        temp_audio.write(file.read())
        temp_audio_path = temp_audio.name
    
    st.info("오디오 파일을 분석하고 있습니다... (파일 크기에 따라 약간의 시간이 소요됩니다)")
    try:
        audio = AudioSegment.from_file(temp_audio_path)
    except Exception as e:
        st.error(f"오디오 파일을 읽는 데 실패했습니다: {e}")
        st.error("주의: 로컬에서 실행 중이라면 시스템에 ffmpeg가 설치되어 있어야 합니다.")
        os.remove(temp_audio_path)
        return

    # 10분 단위로 분할 (10 * 60 * 1000 ms)
    # Groq의 25MB 제한을 여유롭게 피하기 위함
    chunk_length_ms = 10 * 60 * 1000
    chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
    
    total_chunks = len(chunks)
    st.success(f"총 {total_chunks}개의 조각으로 나누어 변환을 시작합니다.")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    full_transcript = ""
    
    for i, chunk in enumerate(chunks):
        status_text.text(f"[{i+1}/{total_chunks}] 파트 변환 중...")
        
        # 각 조각을 임시 mp3 파일로 내보내기 (용량을 줄이기 위해 mp3 사용)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as chunk_file:
            chunk.export(chunk_file.name, format="mp3")
            chunk_file_path = chunk_file.name
        
        try:
            with open(chunk_file_path, "rb") as file_to_send:
                transcription = client.audio.transcriptions.create(
                  file=(os.path.basename(chunk_file_path), file_to_send.read()),
                  model="whisper-large-v3", # Groq의 최고성능 모델
                  prompt="다음은 한국어 음성 기록입니다. 최대한 정확하게 받아쓰기 해주세요.", # 문맥 유지를 위한 프롬프트
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

if uploaded_file and api_key:
    if st.button("녹취 시작하기"):
        with st.spinner("전체 처리 중..."):
            result_text = process_audio(uploaded_file, api_key)
            
            if result_text:
                st.success("변환이 완료되었습니다! 아래에서 결과를 확인하세요.")
                st.text_area("녹취 결과", result_text, height=400)
                
                # 다운로드 버튼
                st.download_button(
                    label="텍스트 파일로 다운로드",
                    data=result_text,
                    file_name="transcript.txt",
                    mime="text/plain"
                )
