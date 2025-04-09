import streamlit as st
import openai
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import random
import json
from streamlit_autorefresh import st_autorefresh

# ──────────────────────────────
# ✅ 기본 설정
# ──────────────────────────────
api_keys = st.secrets["api"]["keys"]
selected_api_key = random.choice(api_keys)
client = openai.OpenAI(api_key=selected_api_key)
assistant_id = 'asst_prIG3LL7UZnZ1qJ8ChTr5cye'

st.set_page_config(page_title="학생 질문 페이지", layout="wide")

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

if "conversation" not in st.session_state:
    st.session_state["conversation"] = []
if "usingthread" not in st.session_state:
    new_thread = client.beta.threads.create()
    st.session_state["usingthread"] = new_thread.id
if "status" not in st.session_state:
    st.session_state["status"] = "idle"  # 또는 waiting_for_approval

# ──────────────────────────────
# ✅ 사이드바: 정보 입력
# ──────────────────────────────
with st.sidebar:
    st.header("📝 기본 정보")
    code = st.text_input("🔑 코드", key="code")
    student_name = st.text_input("🧒 이름", key="name")
    conversation_title = st.text_input("📘 대화 제목", key="title")
    conversation_goal = st.text_area("🎯 대화 목표", key="goal")

# ──────────────────────────────
# ✅ 자동 새로고침 (승인 대기 중)
# ──────────────────────────────
if st.session_state["status"] == "waiting_for_approval":
    st_autorefresh(interval=10000, key="refresh")

# ──────────────────────────────
# ✅ 시트 접근 함수
# ──────────────────────────────
def get_sheet():
    credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(credentials)
    return gc.open(st.secrets["google"]["sc"]).sheet1

# ──────────────────────────────
# ✅ 승인 여부 확인
# ──────────────────────────────
approved = False
latest_answer = None
sheet = get_sheet()
data = sheet.get_all_records()

for row in reversed(data):
    if (row["코드"] == code and
        row["이름"] == student_name and
        row["질문"] == st.session_state.get("latest_question")):
        approved = row["승인여부"].upper() == "TRUE"
        latest_answer = row["응답"]
        break

if approved and latest_answer:
    if ("assistant", latest_answer) not in st.session_state["conversation"]:
        st.session_state["conversation"].append(("assistant", latest_answer))
        st.session_state["status"] = "idle"
        st.rerun()

# ──────────────────────────────
# ✅ 대화 화면
# ──────────────────────────────
st.title("💬 생성형AI 질문하기")
st.subheader("📚 대화 내용")
with st.container(height=600, border=True):
    for role, msg in st.session_state["conversation"]:
        if role == "user":
            st.chat_message("user").write(msg)
        elif role == "assistant":
            st.chat_message("assistant").write(msg)

    question = st.text_input("✍️ 궁금한 것을 질문해보세요")

    if st.button("질문하기", use_container_width=True) and question:
        st.session_state["conversation"].append(("user", question))
        st.session_state["status"] = "waiting_for_approval"

        # GPT 프롬프트
        system_prompt = f"""
        대화 제목: {conversation_title}
        대화 목표: {conversation_goal}

        학생이 다음과 같이 질문했어요:
        \"{question}\"
        친절하게, 초등학생이 이해할 수 있도록 설명해주세요.
        """

        client.beta.threads.messages.create(
            thread_id=st.session_state["usingthread"],
            role="user",
            content=system_prompt)

        run = client.beta.threads.runs.create(
            thread_id=st.session_state["usingthread"],
            assistant_id=assistant_id)

        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state["usingthread"],
                run_id=run.id)
            if run.status == "completed":
                break
            time.sleep(2)

        response = client.beta.threads.messages.list(st.session_state["usingthread"])
        msg = response.data[0].content[0].text.value

        # 저장
        st.session_state["latest_answer"] = msg
        st.session_state["latest_question"] = question

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [
            code,
            student_name,
            question,
            msg,
            "FALSE",
            now
        ]
        sheet.append_row(new_row)
        st.rerun()
