# TravelBuddy — Trợ lý Du lịch Thông minh (Nâng cấp Lab 4)

Ứng dụng trợ lý du lịch được xây dựng bằng **LangGraph** và **LangChain**, tích hợp các công cụ thu thập dữ liệu giá vé máy bay, khách sạn, thời tiết và chất lượng không khí thực tế.

## 🌟 Chức năng nổi bật
1. **Ký ức hội thoại (Memory)**: Lưu trữ lịch sử trò chuyện qua `thread_id`, giúp bot nhớ tên người dùng và các chi tiết thảo luận trước đó.
2. **Thời tiết & Không khí (Độ tin cậy cao)**: 
   - Tích hợp **Open-Meteo** (Chính) và tự động **Fallback sang OpenWeatherMap** nếu nguồn chính lỗi.
   - Cơ chế **HTTP Retry (2 lần)** cho mọi yêu cầu mạng để xử lý lỗi SSL/Timeout tạm thời.
3. **Tự động xác định vị trí**: Sử dụng IP-API để phát hiện vị trí hiện tại của người dùng (Thành phố/Tọa độ) mà không cần nhập liệu thủ công.
4. **Tìm chuyến bay & Khách sạn thực tế**: Cào dữ liệu từ Google Flights (qua `fast-flights`) và Booking.com (qua Playwright).
5. **Siết chặt Persona & Bảo mật**:
   - **KIỂM TRA LOGIC**: Tự động chặn và giải thích khi người dùng tìm vé máy bay trong cùng 1 thành phố (VD: HN đi HN).
   - **Out-of-Scope**: Chặn các câu hỏi ngoài lề (Toán học, Lập trình, Chính trị...).
   - **Jailbreak Protection**: Duy trì nhân vật trợ lý du lịch ngay cả khi bị yêu cầu bỏ qua hướng dẫn gốc.
6. **Giám sát (LangSmith)**: Tích hợp sẵn LangSmith để theo dõi chi tiết từng bước suy luận và Tool call của Agent.

## 🛠️ Chi tiết các công cụ (Tools)
Hệ thống sở hữu bộ công cụ mạnh mẽ để hỗ trợ người dùng:
- **`get_airport_code`**: Tự động tra cứu mã IATA 3 chữ cái của bất kỳ thành phố nào trên thế giới thông qua tìm kiếm Internet (Tavily Search). Giúp Agent làm việc với cả các địa danh lạ/mới.
- **`search_flights`**: Tra cứu thông tin vé máy bay thực tế (hãng bay, giờ bay, giá vé) dựa trên mã IATA đầu vào. (Sử dụng `fast-flights`)
- **`search_hotels`**: Cào dữ liệu khách sạn trực tiếp từ Booking.com theo thành phố và ngân sách tối đa. (Sử dụng Playwright)
- **`calculate_budget`**: Tự động tính toán và tổng hợp chi phí chuyến đi, cảnh báo nếu vượt ngân sách dự kiến.
- **`get_weather_forecast`**: Cung cấp nhiệt độ và tình trạng thời tiết thời gian thực. (Open-Meteo + Fallback OpenWeatherMap)
- **`get_air_quality`**: Kiểm tra các chỉ số ô nhiễm (AQI, PM2.5, PM10) để đưa ra lời khuyên du lịch an toàn.
- **`get_current_location`**: Tự động nhận diện vị trí của người dùng qua địa chỉ IP để cá nhân hóa tư vấn.

## 📁 Cấu trúc thư mục
```text
AI_Thuc_Chien_lab_4/
├── core/
│   ├── agent.py         # Logic khởi tạo LangGraph + Checkpointer (Memory)
│   ├── prompts.py       # System prompt & Persona rules (Logic check #7)
│   └── tools.py         # Công cụ: Search, Weather (Fallback OWM), AQI, Retry logic
├── config/
│   └── settings.py      # Quản lý cấu hình & API Keys
├── tests/
│   ├── test_agent.py    # Test logic Agent, Ký ức & Sanity Check
│   └── test_tools.py    # Test Unit từng công cụ đơn lẻ (Mocking)
├── run_tests.py         # Script chạy End-to-End test toàn bộ kịch bản
├── main.py              # Giao diện Chat Terminal
└── README.md            # Tài liệu dự án
```

## 🚀 Cài đặt & Sử dụng (với `uv`)

### 1. Chuẩn bị biến môi trường
Tạo file `.env` tại thư mục gốc với các khóa sau:
```env
OPENAI_API_KEY=sk-xxx...
# Cấu hình Fallback (Thời tiết)
OPENWEATHERMAP_API_KEY=your_key_here
# Cấu hình Giám sát (LangSmith)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_xxx...
LANGCHAIN_PROJECT="TravelBuddy"
```

### 2. Cài đặt nhanh
```bash
# Cài đặt môi trường và toàn bộ dependencies (bao gồm langsmith, playwright)
uv sync --extra dev

# Cài đặt Browser engine cho Playwright
uv run playwright install chromium
```

### 3. Khởi chạy
```bash
# Chat trực tiếp với Agent
uv run python main.py

# Chạy End-to-End Test (Kết quả lưu tại test_results.md)
uv run python run_tests.py
```

## 🧪 Kiểm thử & Giám sát
- **Unit Test**: `uv run pytest tests/ -v`
- **Tracing**: Truy cập [smith.langchain.com](https://smith.langchain.com/) để xem chi tiết luồng xử lý (Graph Flow).

## 🔐 Các giới hạn an toàn
- **Logic Sanity**: Hệ thống từ chối các yêu cầu vô lý (vé máy bay nội đô) và giải thích lý do (chỉ có vé máy bay/khách sạn, không hỗ trợ taxi/xe buýt).
- **Network Resilience**: Tự động thử lại khi gặp lỗi SSL protocol hoặc API bận (Max 2 retries).
- **Fallback**: Luôn có nguồn dữ liệu thay thế nếu Open-Meteo bị treo/giới hạn IP.
