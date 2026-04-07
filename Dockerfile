# ── Build Stage: Dùng uv để cài dependencies ──────────────────────────────
FROM python:3.12-slim AS builder

# Cài uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project metadata trước (để tận dụng Docker layer cache)
COPY pyproject.toml uv.lock* ./

# Cài dependencies vào thư mục cố định, không vào hệ thống
RUN uv sync --frozen --no-editable --no-dev

# ── Runtime Stage: Image nhỏ gọn ──────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy virtual environment đã cài từ builder
COPY --from=builder /app/.venv /app/.venv

# Copy toàn bộ source code
COPY . .

# Cài Playwright browsers (cần cho web scraper Booking.com)
RUN /app/.venv/bin/python -m playwright install chromium --with-deps

# Đảm bảo dùng Python từ venv
ENV PATH="/app/.venv/bin:$PATH"

# Mở cổng cho Streamlit
EXPOSE 8501

# Chạy ứng dụng Web
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
