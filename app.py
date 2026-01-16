import streamlit as st
import google.generativeai as genai
import json
import urllib.parse
import time

# --------------------------------------------------------------------------
# 1. 설정 및 API 구성
# --------------------------------------------------------------------------
st.set_page_config(page_title="Dinner Mate Chat", page_icon="🍳", layout="centered")

def configure_genai():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
    except KeyError:
        st.error("🚨 API Key가 설정되지 않았습니다.")
        st.stop()

configure_genai()

# --------------------------------------------------------------------------
# 2. 시스템 프롬프트 (AI의 페르소나 및 행동 지침)
# --------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """
당신은 'Dinner Mate'라는 친절한 AI 셰프입니다. 사용자와 대화하며 저녁 메뉴를 추천해주기 위해 필요한 정보를 수집하세요.

[당신의 목표]
사용자로부터 아래 7가지 정보를 자연스러운 대화로 모두 알아내야 합니다.
1. 보유 재료 (냉장고)
2. 날씨
3. 기분/취향
4. 선호 요리 종류 (한식, 중식 등)
5. 인분 수
6. 가용 시간
7. 요리 난이도

[대화 규칙]
1. 한 번에 1~2가지 질문만 하세요. (사용자가 부담스럽지 않게)
2. 사용자가 정보를 주면, 적절히 반응하고 다음 질문을 하세요.
3. 사용자가 이미 정보를 말했다면 다시 묻지 마세요.
4. 모든 정보가 수집되었다면, 더 이상 질문하지 말고 **반드시 아래 JSON 형식으로만** 최종 결과를 출력하고 대화를 종료하세요.

[최종 결과 JSON 스키마]
{
    "is_final": true,
    "menu_name": "요리 이름",
    "reason": "추천 이유",
    "ingredients_owned": ["보유 재료"],
    "ingredients_missing": ["부족한 재료(구매 필요)"],
    "recipe_steps": ["1. ...", "2. ..."],
    "substitutes": "대체 재료 팁",
    "tips": "맛내기 꿀팁"
}

중요: 정보 수집 중에는 JSON을 출력하지 말고 일반 텍스트로 대화하세요. 모든 정보가 모였을 때만 JSON을 출력하세요.
"""

# 모델 초기화 (시스템 프롬프트 적용)
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=SYSTEM_INSTRUCTION
)

# --------------------------------------------------------------------------
# 3. 유틸리티 함수
# --------------------------------------------------------------------------
def get_youtube_link(menu_name):
    query = urllib.parse.quote(f"{menu_name} 레시피 만들기")
    return f"https://www.youtube.com/results?search_query={query}"

def parse_response(text):
    """모델 응답이 JSON(최종 결과)인지 일반 대화인지 판별"""
    try:
        # 마크다운 코드블록 제거
        clean_text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        if data.get("is_final"):
            return True, data
    except:
        pass
    return False, text

# --------------------------------------------------------------------------
# 4. 메인 앱 로직
# --------------------------------------------------------------------------
def main():
    st.title("🍳 Dinner Mate : 셰프와의 대화")
    st.markdown("저에게 상황을 말씀해주시면, 딱 맞는 저녁 메뉴를 골라드릴게요!")

    # 세션 상태 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # 초기 대화 시작 (chat_session 객체 생성)
        st.session_state.chat = model.start_chat(history=[])
        # 첫 인사말 생성 (강제로 모델에게 첫 턴을 넘김 혹은 미리 설정)
        initial_greeting = "안녕하세요! 셰프 Dinner Mate입니다. 👨‍🍳\n\n맛있는 저녁을 위해 냉장고에 어떤 재료들이 있는지 먼저 알려주시겠어요?"
        st.session_state.messages.append({"role": "assistant", "content": initial_greeting, "type": "text"})
        # 모델 히스토리에도 강제 주입 (Role 매칭을 위해)
        st.session_state.chat.history.append(
            {"role": "model", "parts": [initial_greeting]}
        )

    # 채팅 히스토리 표시
    for msg in st.session_state.messages:
        if msg["type"] == "text":
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        elif msg["type"] == "result":
            # 결과 UI 렌더링 (이전 결과도 다시 보여줌)
            render_result_card(msg["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("답변을 입력해주세요 (예: 계란랑 파 있어, 매운거 좋아해)"):
        # 1. 사용자 메시지 표시
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt, "type": "text"})

        # 2. AI 응답 요청
        try:
            response = st.session_state.chat.send_message(prompt)
            response_text = response.text
            
            # 3. 응답 분석 (JSON인가 대화인가?)
            is_json, content = parse_response(response_text)

            if is_json:
                # 최종 결과인 경우: UI 카드 렌더링 및 저장
                render_result_card(content)
                st.session_state.messages.append({"role": "assistant", "content": content, "type": "result"})
            else:
                # 일반 대화인 경우
                with st.chat_message("assistant"):
                    st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text, "type": "text"})

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

def render_result_card(data):
    """최종 결과 JSON을 예쁜 UI로 출력하는 함수"""
    with st.chat_message("assistant"):
        st.success("👨‍🍳 모든 정보를 확인했습니다! 오늘의 추천 메뉴를 대령합니다.")
        
        container = st.container(border=True)
        with container:
            st.markdown(f"## 🍽️ 추천 메뉴: **{data.get('menu_name')}**")
            st.info(f"🗣️ **선정 이유:** {data.get('reason')}")

            col1, col2 = st.columns(2)
            with col1:
                st.write("✅ **준비된 재료**")
                for item in data.get('ingredients_owned', []):
                    st.write(f"- {item}")
            with col2:
                st.write("🛒 **필요한 재료 (쇼핑)**")
                missing = data.get('ingredients_missing', [])
                if missing:
                    for item in missing:
                        st.markdown(f":red[- {item}]")
                else:
                    st.write("- 없음 (완벽해요! 👍)")

            st.divider()
            
            st.subheader("📜 조리법")
            for idx, step in enumerate(data.get('recipe_steps', [])):
                st.write(f"**{idx+1}.** {step}")
            
            st.divider()
            
            st.markdown(f"💡 **Tip:** {data.get('tips')}")
            st.markdown(f"🔄 **대체 가능:** {data.get('substitutes')}")
            
            yt_url = get_youtube_link(data.get('menu_name'))
            st.link_button("📺 유튜브 영상 보러가기", yt_url, use_container_width=True)

if __name__ == "__main__":
    main()
