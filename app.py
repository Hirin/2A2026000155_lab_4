import streamlit as st
import pandas as pd
import time
from core.agent import agent_graph
from config.settings import MODEL_CHOICE, PROMPT_MODE
from langchain_core.messages import HumanMessage, AIMessage

# --- Cấu hình trang ---
st.set_page_config(
    page_title="TravelBuddy AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS tùy chỉnh để làm giao diện premium hơn ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stChatMessage {
        border-radius: 15px;
        margin-bottom: 15px;
        padding: 10px;
    }
    .st-emotion-cache-12w0qpk { 
        background-color: #1a1c24; 
    }
    .stTable {
        border: 1px solid #30363d;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Khởi tạo Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "web_session_" + str(int(time.time()))

# --- Sidebar điều khiển ---
with st.sidebar:
    st.title("🧳 Cấu hình Agent")
    st.info(f"Đang chạy Model: **{MODEL_CHOICE}**")
    
    st.divider()
    
    # Cho phép chuyển đổi Prompt Mode (Đề xuất của Antigravity)
    new_prompt_mode = st.selectbox(
        "Chế độ Prompt:",
        options=["hardened", "basic"],
        index=0 if PROMPT_MODE == "hardened" else 1,
        help="Hardened: Nghiêm ngặt & Im lặng khi gọi tool. Basic: Thân thiện hơn nhưng dễ ngắt luồng."
    )
    
    if new_prompt_mode != PROMPT_MODE:
        st.warning("⚠️ Bạn đã đổi Mode. Hãy khởi động lại app để áp dụng.")
        
    st.divider()
    st.write(f"ID Hội thoại: `{st.session_state.thread_id}`")
    
    if st.button("Xóa lịch sử Chat"):
        st.session_state.messages = []
        st.session_state.thread_id = "web_session_" + str(int(time.time()))
        st.rerun()

# --- Giao diện chính ---
st.title("✈️ TravelBuddy: Trợ lý Du lịch Thông minh")
st.caption("Khám phá thế giới với dữ liệu thực tế về Chuyến bay, Khách sạn và Thời tiết.")

# Hiển thị lịch sử chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Luồng xử lý Chat ---
if prompt := st.chat_input("Hành trình tiếp theo của bạn là đâu?"):
    # Lưu tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        status_container = st.container()
        
        # Biến lưu trữ logs từ tools
        tool_logs = []
        
        # Cấu hình thread_id
        config = {"configurable": {"thread_id": st.session_state.thread_id}, "recursion_limit": 20}
        
        # Thực thi Agent qua stream để bắt được quá trình gọi Tool
        with st.status("TravelBuddy đang xử lý...", expanded=True) as status:
            final_response = ""
            
            for event in agent_graph.stream({"messages": [HumanMessage(content=prompt)]}, config):
                # Kiểm tra tool call logs
                if "agent" in event:
                    msg = event["agent"]["messages"][0]
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            st.write(f"🔍 **Đang gọi công cụ:** `{tc['name']}`")
                
                if "tools" in event:
                    for msg in event["tools"]["messages"]:
                        st.write(f"✅ **Dữ liệu trả về từ:** `{msg.name}`")
                        # (Có thể hiển thị preview dữ liệu ở đây)
            
            # Sau khi xong các bước, lấy tin nhắn cuối cùng
            state = agent_graph.get_state(config)
            final_response = state.values["messages"][-1].content
            status.update(label="Xử lý hoàn tất!", state="complete", expanded=False)

        # Hiển thị phản hồi cuối cùng
        message_placeholder.markdown(final_response)
        st.session_state.messages.append({"role": "assistant", "content": final_response})

# --- Footer ---
st.divider()
st.caption("Dự án được phát triển trong khuôn khổ Lab 4 - AI Thực Chiến.")
