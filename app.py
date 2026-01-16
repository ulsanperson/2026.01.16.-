import streamlit as st
import google.generativeai as genai
import json
import urllib.parse
import re

# --------------------------------------------------------------------------
# 1. 기본 설정 및 API 구성
# --------------------------------------------------------------------------
st.set_page_config(page_title="Dinner Mate Chat", page_icon="🍳", layout="centered")

# API 키 설정 (st.secrets 사용)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("🚨 API Key가 설정되지 않았습니다. .streamlit/secrets.toml을 확인해주세요.")
    st.stop()

# --------------------------------------------------------------------------
# 2. 모델 및 프롬프트 설정 (JSON 출력 강제화 강화)
# --------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """
당신은 'Dinner Mate'라는 친절한 AI 셰프입니다.
사용자와 대화하며 [보유 재료, 날씨, 기분, 선호 요리 종류, 인분 수, 가용 시간, 요리 난이도]를 파악하세요.

[중요 규칙]
1. 정보 수집 단계에서는 친구처럼 편하게 대화하세요. (JSON 출력 금지)
2. 모든 정보가 파악되면, 즉시 대화를 멈추고 **오직 아래 JSON 데이터만** 출력하세요.
3. JSON 외에 "알겠습니다", "여기 레시피입니다" 같은 사족을 절대 붙이지 마세요.

[최종 결과 JSON 스키마]
{
    "is_final": true,
    "menu_name": "요리 이름",
    "reason": "추천 이유",
    "ingredients_owned": ["보유 재료1", "보유 재료2"],
    "ingredients_missing": ["구매 필요 재료1", "구매 필요 재료2"],
    "recipe_steps": ["1. 재료를 손질합니다.", "2. 팬을 달굽니다."],
    "substitutes": "대체 재료 팁",
    "tips": "맛내기 꿀팁"
}
"""

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={"response_mime_type": "application/json"}  # JSON 응답 강제
)

# --------------------------------------------------------------------------
# 3. 유틸리티 함수 (파싱 및 링크 생성)
# --------------------------------------------------------------------------
def get_youtube_link(menu_name):
    """메뉴 이름으로 유튜브 검색 링크 생성"""
    query = urllib.parse.quote(f"{menu_name} 레시피 만드는 법")
    return f"https://www.youtube.com/results?search_query={query}"

def parse_response(text):
    """
    모델의 응답 텍스트를 분석하여 JSON 객체인지 일반 대화인지 판별합니다.
    JSON 파싱에 성공하고 'is_final': true가 있으면 결과 데이터로 반환합니다.
    """
    try:
        # 혹시 모를 마크다운 코드블록(```json ... ```) 제거
        cleaned_text = re.sub(r"```json|```", "", text).strip()
        data = json.loads(cleaned_text)
        
        if isinstance(data, dict) and data.get("is_final"):
            return True, data
    except (json.JSONDecodeError, TypeError):
        pass
    
    return False, text

# --------------------------------------------------------------------------
# 4. 결과 화면 렌더링 (개조식 UI)
# --------------------------------------------------------------------------
def render_result_card(data):
    """최종 결과를 깔끔한 카드 UI로 출력"""
    
    # 컨테이너로 감싸서 구분감 주기
    with st.chat_message("assistant", avatar="👨‍🍳"):
        st.success("👨‍🍳 주문하신 맞춤형 레시피가 도착했습니다!")
        
        with st.container(border=True):
            # 1. 메뉴명 및 이유
            st.markdown(f"### 🍽️ {data.get('menu_name')}")
            st.info(f"{data.get('reason')}")
            
            st.divider()
            
            # 2. 재료 (2단 구성)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ 냉장고 재료**")
                for item in data.get('ingredients_owned', []):
                    st.markdown(f"- {item}")
            
            with c2:
                st.markdown("**🛒 부족한 재료 (쇼핑)**")
                missing = data.get('ingredients_missing', [])
                if missing:
                    for item in missing:
                        st.markdown(f":red[- {item}]")
                else:
                    st.markdown("- 없음 (완벽해요!)")
            
            st.divider()

            # 3. 레시피 (개조식)
            st.subheader("📜 조리 순서")
            steps = data.get('recipe_steps', [])
            for i, step in enumerate(steps):
                st.markdown(f"**{i+1}.** {step}")
            
            st.divider()

            # 4. 꿀팁 및 대체재료
            st.markdown(f"💡 **셰프의 팁:** {data.get('tips', '맛있게 드세요!')}")
            if data.get('substitutes'):
                st.markdown(f"🔄 **대체 재료:** {data.get('substitutes')}")

            # 5. 유튜브 링크 버튼
            menu_name = data.get('menu_name')
            if menu_name:
                yt_url = get_youtube_link(menu_name)
                st.markdown("---")
                st.link_button(f"📺 '{menu_name}' 유튜브 영상 보러가기", yt_url, use_container_width=True)

# --------------------------------------------------------------------------
# 5. 메인 앱 로직
# --------------------------------------------------------------------------
def main():
    st.title("🍳 Dinner Mate")
    st.caption("당신의 냉장고 상황에 딱 맞는 저녁 메뉴를 추천해드립니다.")

    # 세션 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.chat = model.start_chat(history=[])
        
        # 첫 인사
        first_msg = "안녕하세요! 냉장고에 어떤 재료가 있으신가요? (예: 계란, 양파, 스팸 있어)"
        st.session_state.messages.append({"role": "assistant", "content": first_msg, "type": "text"})
        st.session_state.chat.history.append({"role": "model", "parts": [first_msg]})

    # 대화 기록 표시
    for msg in st.session_state.messages:
        if msg["type"] == "text":
            st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "👨‍🍳").write(msg["content"])
        elif msg["type"] == "result":
            # 결과물은 전용 렌더링 함수 사용
            render_result_card(msg["content"])

    # 사용자 입력 (문제의 예시 문구 수정됨)
    if prompt := st.chat_input("재료를 알려주세요 (예: 김치랑 돼지고기 있어, 매운거 좋아해)"):
        
        # 사용자 메시지 표시
        st.chat_message("user", avatar="🧑‍💻").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt, "type": "text"})

        # AI 응답 처리
        with st.spinner("셰프가 레시피를 고민 중입니다..."):
            try:
                response = st.session_state.chat.send_message(prompt)
                is_json, content = parse_response(response.text)

                if is_json:
                    # JSON 결과라면 -> 카드 UI 렌더링 및 저장
                    render_result_card(content)
                    st.session_state.messages.append({"role": "assistant", "content": content, "type": "result"})
                else:
                    # 일반 대화라면 -> 텍스트 말풍선 출력
                    st.chat_message("assistant", avatar="👨‍🍳").write(content)
                    st.session_state.messages.append({"role": "assistant", "content": content, "type": "text"})
            
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
