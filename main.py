import sys
from config.settings import MODEL_CHOICE
from core.agent import agent_graph

def run_chat_loop():
    print("=" * 60)
    print(f"TravelBuddy — Trợ lý Du lịch Thông minh ({MODEL_CHOICE})")
    print("Gõ 'quit' hoặc 'q' để thoát")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\nBạn: ").strip()
            if not sys.stdin.isatty():
                print(user_input)
                
            if user_input.lower() in ("quit", "exit", "q"):
                print("Tạm biệt! Hẹn gặp lại.")
                break
                
            if not user_input:
                continue
                
            print("\nTravelBuddy đang suy nghĩ...")
            # Cấu hình thread_id để Agent nhận diện bộ nhớ hội thoại
            config = {
                "configurable": {"thread_id": "main_session"},
                "recursion_limit": 15
            }
            result = agent_graph.invoke({"messages": [("human", user_input)]}, config)
            final = result["messages"][-1]
            print(f"\nTravelBuddy: {final.content}")
            
        except Exception as e:
            print(f"\n[Lỗi Runtime]: {e}")

if __name__ == "__main__":
    run_chat_loop()
