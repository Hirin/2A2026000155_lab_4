import sys
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, trim_messages

# Import config & tools
from config.settings import MODEL_CHOICE, PROMPT_MODE
from core.prompts import SYSTEM_PROMPT
from core.prompts_basic import SYSTEM_PROMPT_BASIC
from core.tools import (
    search_flights, search_hotels, calculate_budget, 
    get_weather_forecast, get_air_quality, get_current_location,
    get_airport_code, get_current_date
)

# 1. Khai báo State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

def initialize_graph():
    tools_list = [
        search_flights, search_hotels, calculate_budget,
        get_weather_forecast, get_air_quality, get_current_location,
        get_airport_code, get_current_date
    ]
    
    # 2. Khởi tạo LLM & Trimmer
    try:
        if "gpt" in MODEL_CHOICE.lower():
            llm = ChatOpenAI(model=MODEL_CHOICE, temperature=0.2)
        elif "gemini" in MODEL_CHOICE.lower():
            llm = ChatGoogleGenerativeAI(model=MODEL_CHOICE, temperature=0.2)
        else:
            llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    except Exception as e:
        print(f"Lỗi khởi tạo model {MODEL_CHOICE}: {e}")
        sys.exit(1)
        
    llm_with_tools = llm.bind_tools(tools_list)

    # Cấu hình Trimmer: Giữ 10 tin nhắn cuối (last_n), luôn giữ System Message
    trimmer = trim_messages(
        strategy="last",
        max_tokens=10, 
        token_counter=len, # Đếm theo số lượng tin nhắn thay vì token
        include_system=True,
        allow_partial=False,
        start_on="human",
    )

    # Lựa chọn Prompt dựa trên cấu hình
    active_prompt = SYSTEM_PROMPT if PROMPT_MODE == "hardened" else SYSTEM_PROMPT_BASIC
    print(f"[*] Khởi tạo Agent với Prompt Mode: {PROMPT_MODE}")

    # 3. Agent Node
    def agent_node(state: AgentState):
        messages = state["messages"]
        # Chèn SystemPrompt và thực hiện cắt tỉa (trimming) context
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=active_prompt)] + messages
            
        # Áp dụng Trimming để giới hạn Token/Messages gửi lên LLM
        trimmed_messages = trimmer.invoke(messages)
            
        try:
            response = llm_with_tools.invoke(trimmed_messages)
            
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tc in response.tool_calls:
                    print(f"\n[Core] LLM quyết định gọi công cụ: {tc['name']}({tc['args']})")
                    
            return {"messages": [response]}
        except Exception as e:
            from langchain_core.messages import AIMessage
            error_msg = f"Đã xảy ra lỗi hệ thống: {e}"
            return {"messages": [AIMessage(content=error_msg)]}

    # 4. Xây dựng Graph
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    
    # Custom Tool Node to log results
    base_tool_node = ToolNode(tools_list)
    def tool_node_with_logging(state: AgentState):
        result = base_tool_node.invoke(state)
        for msg in result.get("messages", []):
            print(f"\n[Tools] Phản hồi từ công cụ:\n{msg.content}")
            print("-" * 30)
        return result

    builder.add_node("tools", tool_node_with_logging)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    # Kích hoạt Checkpointer để lưu ký ức hội thoại
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    return graph

# Expose instance
agent_graph = initialize_graph()
