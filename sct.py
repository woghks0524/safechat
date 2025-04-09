import streamlit as st
import gspread
import json
import time
import openai
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_autorefresh import st_autorefresh

# 페이지 구성
st.set_page_config(page_title="교사용 응답 승인", layout="wide")

# 제작자 이름 
st.caption("웹 어플리케이션 문의사항은 정재환(서울창일초), woghks0524jjh@gmail.com, 010-3393-0283으로 연락주세요.")

# CSS 스타일을 사용하여 상단바와 메뉴 숨기기
hide_streamlit_style = """
            <style>
            MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st_autorefresh(interval=10000, key="refresh_teacher")

# OpenAI 클라이언트
api_keys = st.secrets["api"]["keys"]
openai.api_key = api_keys[0]  # 여러 개 있을 경우 하나 사용

client = openai.OpenAI(api_key=openai.api_key)
assistant_id = 'asst_prIG3LL7UZnZ1qJ8ChTr5cye'

# ─────────────────────────────
# ✅ 구글 시트 연결
# ─────────────────────────────
@st.cache_resource
def get_sheet():
    credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    gc = gspread.authorize(credentials)
    return gc.open(st.secrets["google"]["sc"]).sheet1

sheet = get_sheet()
data = sheet.get_all_records()

# ─────────────────────────────
# ✅ 코드 필터링
# ─────────────────────────────
st.title("👩‍🏫 생성형AI 응답 승인 페이지")
code_input = st.text_input("🔐 교사 코드 입력", placeholder="예: 바나나")

if code_input:
    pending_data = [row for row in data if row["코드"] == code_input and row["승인여부"].upper() != "TRUE"]

    if not pending_data:
        st.warning("아직 승인되지 않은 질문이 없습니다.")
    else:
        st.markdown(f"### 📋 '{code_input}' 코드에 대한 미승인 질문 ({len(pending_data)}개)")

        rows = (len(pending_data) + 4) // 5
        for i in range(rows):
            cols = st.columns(5)
            for j, row in enumerate(pending_data[i * 5 : (i + 1) * 5]):
                with cols[j]:
                    with st.container(border=True):
                        st.markdown(f"#### 🙋 {row['이름']}")
                        st.markdown(f"**❓ 질문:** {row['질문']}")
                        st.markdown("**🤖 GPT 응답:**")
                        st.write(row["응답"])

                        row_index = data.index(row) + 2  # 시트는 1부터 시작, 헤더 제외

                        col_응답 = 4
                        col_승인 = 5

                        # 승인 버튼
                        if st.button("✅ 승인", key=f"approve_{row_index}"):
                            sheet.update_cell(row_index, col_승인, "TRUE")
                            st.success("✅ 승인 완료")
                            st.rerun()

                        # 재생성 버튼
                        if st.button("🔁 재생성", key=f"regen_{row_index}"):
                            thread = client.beta.threads.create()
                            prompt = f"""학생이 다음과 같이 질문했어요:
\"{row['질문']}\" 
다시 한번 친절하게, 초등학생이 이해할 수 있도록 설명해주세요."""

                            client.beta.threads.messages.create(
                                thread_id=thread.id,
                                role="user",
                                content=prompt
                            )

                            run = client.beta.threads.runs.create(
                                thread_id=thread.id,
                                assistant_id=assistant_id
                            )

                            while True:
                                result = client.beta.threads.runs.retrieve(
                                    thread_id=thread.id,
                                    run_id=run.id)
                                if result.status == "completed":
                                    break
                                time.sleep(1)

                            new_msg = client.beta.threads.messages.list(thread_id=thread.id).data[0].content[0].text.value

                            sheet.update_cell(row_index, col_응답, new_msg)
                            sheet.update_cell(row_index, col_승인, "FALSE")
                            st.success("✅ 새 응답으로 업데이트 완료")
                            st.rerun()

else:
    st.info("먼저 교사 코드를 입력하세요.")