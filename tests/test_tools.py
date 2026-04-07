import pytest
from unittest.mock import patch, MagicMock

from core.tools import (
    search_flights, search_hotels, calculate_budget,
    get_weather_forecast, get_air_quality, get_current_location,
    get_airport_code
)

def test_calculate_budget_success():
    res = calculate_budget.invoke({"total_budget": 5000000, "expenses": "vé máy bay: 1200000, khách sạn: 1500000"})
    assert "Bảng chi phí:" in res
    assert "Vé máy bay" in res
    assert "Khách sạn" in res
    assert "Còn lại dư" in res
    assert "2.300.000đ" in res # 5M - 2M7

def test_calculate_budget_negative():
    res = calculate_budget.invoke({"total_budget": 1000000, "expenses": "vé máy bay: 1200000, khách sạn: 500000"})
    assert "Vượt quá ngân sách" in res
    assert "700.000đ" in res

def test_calculate_budget_malformed_input():
    res = calculate_budget.invoke({"total_budget": 1000000, "expenses": "rác,, vé : aaaaa, test"})
    assert "Lỗi: Không parsing được chi phí nào hợp lệ" in res

def test_search_flights_invalid_format():
    res = search_flights.invoke({"origin": "Hanoi", "destination": "SGN"})
    assert "yêu cầu mã IATA 3 ký tự" in res

def test_search_flights_same_city():
    res = search_flights.invoke({"origin": "HAN", "destination": "HAN"})
    assert "giống nhau" in res
    assert "HAN" in res

@patch('core.tools.get_flights')
def test_search_flights_mocked_success(mock_get_flights):
    # Mocking thư viện external fast_flights
    mock_result = MagicMock()
    mock_flight = MagicMock()
    mock_flight.name = "Vietjet Air"
    mock_flight.departure = "15:00"
    mock_flight.arrival = "17:00"
    mock_flight.price = "1500000"
    mock_result.flights = [mock_flight]
    mock_get_flights.return_value = mock_result

    res = search_flights.invoke({"origin": "HAN", "destination": "DAD"})
    assert "THỰC TẾ" in res
    assert "Vietjet Air" in res
    assert "1.500.000đ" in res

from pydantic import ValidationError

@patch('core.tools._scrape_booking_async')
def test_search_hotels_invalid_price_format_and_mock(mock_scrape):
    # Mock kết quả crawl
    mock_scrape.return_value = [
        {"name": "Hotel A", "stars": 4, "price_per_night": 1200000, "area": "Trung tâm", "rating": "8.5"}
    ]
    
    # max_price_per_night bị vô tình gán thành text/kiểu lạ -> Langchain's `@tool` Pydantic sẽ bắt trước khi tool chạy!
    with pytest.raises(ValidationError):
        search_hotels.invoke({"city": "Đà Lạt", "max_price_per_night": "chuỗi_lỗi_từ_llm"})
    
    # Verify test cào thành công với int chuẩn
    res = search_hotels.invoke({"city": "Đà Lạt", "max_price_per_night": 1500000})
    assert "Hotel A" in res
    assert "1.200.000đ" in res

@patch('requests.get')
def test_get_current_location_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "city": "Hà Nội",
        "lat": 21.0285,
        "lon": 105.8542,
        "country": "Vietnam"
    }
    mock_get.return_value = mock_response

    res = get_current_location.invoke({})
    assert "Hà Nội" in res
    assert "Vietnam" in res

@patch('core.tools.get_coordinates')
@patch('requests.get')
def test_get_weather_forecast_success(mock_get, mock_get_coords):
    mock_get_coords.return_value = {"lat": 10.7627, "lon": 106.6602, "name": "Hồ Chí Minh", "country": "Vietnam"}
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "current_weather": {
            "temperature": 32.5,
            "weathercode": 0,
            "windspeed": 10.2
        }
    }
    mock_get.return_value = mock_response

    res = get_weather_forecast.invoke({"location": "Hồ Chí Minh"})
    assert "☀️ THỜI TIẾT TẠI HỒ CHÍ MINH" in res.replace("🌤️", "☀️") # Match regardless of icon
    assert "32.5°C" in res
    assert "Trời quang đãng" in res

@patch('core.tools.get_coordinates')
@patch('requests.get')
def test_get_air_quality_success(mock_get, mock_get_coords):
    mock_get_coords.return_value = {"lat": 21.0285, "lon": 105.8542, "name": "Hà Nội", "country": "Vietnam"}
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "current": {
            "european_aqi": 45,
            "pm10": 55.2,
            "pm2_5": 25.1
        }
    }
    mock_get.return_value = mock_response

    res = get_air_quality.invoke({"location": "Hà Nội"})
    assert "🌬️ CHẤT LƯỢNG KHÔNG KHÍ TẠI HÀ NỘI" in res
    assert "AQI: 45" in res
    assert "Trung bình" in res

def test_get_airport_code_cache():
    res = get_airport_code.invoke({"location": "Sài Gòn"})
    assert res == "SGN"

@patch('requests.post')
def test_get_airport_code_api_mock(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"content": "The IATA code for Pleiku is (PXU)."}
        ]
    }
    mock_post.return_value = mock_response
    
    with patch('core.tools.get_tavily_key', return_value="test_key"):
        res = get_airport_code.invoke({"location": "Pleiku"})
        assert res == "PXU"
