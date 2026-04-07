# Phân tích System Prompt của TravelBuddy

Tài liệu này phân tích chi tiết cấu trúc và các quy tắc của `SYSTEM_PROMPT` hiện tại để hiểu cách Agent tư vấn và xử lý logic.

## 1. Cấu trúc Prompt
Prompt được chia thành các block XML rõ ràng để mô hình dễ dàng phân tách các loại chỉ dẫn:
- `<persona>`: Định nghĩa tính cách và tông giọng (thân thiện, người thực).
- `<rules>`: Các quy tắc vận hành và xử lý tool (08 quy tắc chính).
- `<tools_instruction>`: Hướng dẫn sử dụng các công cụ cụ thể (phối hợp tool).
- `<response_format>`: Quy định cấu trúc câu trả lời đầu ra (format trình bày).
- `<constraints>`: Các giới hạn tuyệt đối và bảo mật (không gọi 5+3).

## 2. Các quy tắc cốt lõi (Rules)

### Quy tắc #2: Ưu tiên hành động (Proactive Tool Call)
- **Mục đích**: Khắc phục tình trạng Agent hỏi đi hỏi lại hoặc xác nhận dư thừa khi đã có đủ thông tin.
- **Cơ chế**: Yêu cầu gọi tool ngay lập tức nếu có (Thành phố, ngày tháng...).
- **Thông minh**: Tự động ánh xạ các từ viết tắt như "SG", "HN" sang mã IATA chuẩn ("SGN", "HAN") để tool không bị lỗi.

### Quy tắc #6: Xử lý ngoài phạm vi (Out-of-Scope)
- **Mục đích**: Giữ cho Agent tập trung vào du lịch và tiết kiệm token/chi phí.
- **Cơ chế**: Từ chối các câu hỏi về toán học, lập trình, chính trị... bằng một câu trả lời mẫu lịch sự.

### Quy tắc #7: Kiểm tra Logic trùng lặp (Sanity Check)
- **Mục đích**: Tránh các cuộc gọi API vô nghĩa.
- **Cơ chế**: So sánh điểm đi và điểm đến. Nếu trùng nhau, Agent sẽ giải thích lý do không hỗ trợ (chỉ có vé máy bay/khách sạn, không có phương tiện nội đô) thay vì gọi tool.

## 3. Bảo mật và Ràng buộc (Constraints)

### Jailbreak Protection
- Thêm các ràng buộc tuyệt đối để Agent không bị "dụ" bỏ qua system prompt (như kịch bản "5+3=" vừa rồi).
- Agent luôn phải quay lại vai trò trợ lý du lịch sau khi từ chối.

### No Booking
- Quy tắc nghiêm ngặt: Tuyệt đối không dùng từ "đặt" (book) để tránh gây hiểu lầm cho người dùng rằng Agent có thể thanh toán thực tế. Hệ thống chỉ hỗ trợ **Tìm kiếm** và **Tư vấn**.

## 4. Tối ưu hóa Tool Call
- Hướng dẫn Agent cách phối hợp các công cụ: Ví dụ, gọi `get_current_location` trước khi gọi `get_weather_forecast` nếu người dùng hỏi "chỗ tôi".
- Điều này giúp giảm số lượt hội thoại cần thiết để có được thông tin cuối cùng.

## 5. Kết luận
System Prompt hiện tại đã được "hardened" (siết chặt) để:
1. Quyết đoán hơn trong việc gọi tool (đã cải thiện sau khi bổ sung Quy tắc #2).
2. Xử lý lỗi logic ngay từ bước lập luận.
3. Duy trì persona an toàn và chuyên nghiệp, tránh các lỗi phổ biến của AI tổng quát.
