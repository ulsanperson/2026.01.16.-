import streamlit as st
import google.generativeai as genai
import json
import urllib.parse
import re

# --------------------------------------------------------------------------
# 1. 기본 설정 및 API 구성
# --------------------------------------------------------------------------
st.set_page_config(page_title="Dinner Mate Chat", page_icon="🍳", layout="centered")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 API Key가 설정되지 않았습니다.")
    st.stop()

# --------------------------------------------------------------------------
# 2. 모델 설정
# --------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """
당신은 'Dinner Mate'라는 친절한 AI 셰프입니다.
사용자와 대화하며 [보유 재료, 날씨, 기분, 선호 요리 종류, 인분 수, 가용 시간, 요리 난이도]를 파악하세요.

[규칙]
1. 정보 수집 단계에서는 친구처럼 대화하세요. (JSON 금지)
2. 모든 정보가 파악되면 **오직 아래 JSON 데이터만** 출력하고 대화를 종료하세요.

[최종 결과 JSON 스키마]
{
    "is_final": true,
    "menu_name": "요리 이름",
    "reason": "추천 이유",
    "ingredients_owned": ["보유 재료"],
    "ingredients_missing": ["구매 필요 재료"],
    "recipe_steps": ["1. ...", "2. ..."],
    "substitutes": "대체 재료 팁",
    "tips": "꿀팁"
}
"""

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={"response_mime_type": "application/json"}
)

# --------------------------------------------------------------------------
# 3. 핵심 로직: 멈춤 방지를 위한 메시지 변환 함수
# --------------------------------------------------------------------------
def get_gemini_response(history_messages):
    """
    Streamlit의 대화 기록(st.session_state.messages)을
    Gemini가 이해하는 형식(Content Dict)으로 변환하여 전송합니다.
    이렇게 하면 무거운 ChatSession 객체를 저장할 필요가 없어 먹통 현상이 사라집니다.
    """
