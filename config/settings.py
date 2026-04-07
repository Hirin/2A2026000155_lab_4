import os
import sys
from dotenv import load_dotenv

# Tìm và load file .env từ thư mục hiện tại hoặc thư mục cha
if os.path.exists(".env"):
    load_dotenv(dotenv_path=".env")
elif os.path.exists("../.env"):
    load_dotenv(dotenv_path="../.env")

# Lựa chọn model: LAB4_MODEL > DEFAULT_MODEL > gpt-4o-mini
MODEL_CHOICE = os.getenv("LAB4_MODEL") or os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

def validate_config():
    if "gpt" in MODEL_CHOICE.lower() and "mock" not in MODEL_CHOICE.lower():
        if not os.getenv("OPENAI_API_KEY"):
            print("Lỗi hệ thống: Không tìm thấy OPENAI_API_KEY trong file .env.")
            sys.exit(1)
    elif "gemini" in MODEL_CHOICE.lower() and "mock" not in MODEL_CHOICE.lower():
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Lỗi hệ thống: Không tìm thấy GOOGLE_API_KEY hoặc GEMINI_API_KEY trong file .env.")
            sys.exit(1)
        # Đồng bộ cho langchain-google-genai (nó đọc GOOGLE_API_KEY)
        os.environ["GOOGLE_API_KEY"] = api_key
