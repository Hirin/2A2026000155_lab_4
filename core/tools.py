import asyncio
import re
import urllib.parse
import requests
import urllib3
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Tắt cảnh báo InsecureRequestWarning khi dùng verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from langchain_core.tools import tool
from fast_flights import FlightData as FData, Passengers, get_flights
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Config
def get_tavily_key():
    return os.getenv("TAVILY_API_KEY")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

# Ánh xạ mã sân bay phổ biến (Làm bộ nhớ đệm nhanh)
IATA_MAP = {
    "hà nội": "HAN", "hanoi": "HAN", "hn": "HAN", "han": "HAN",
    "hồ chí minh": "SGN", "saigon": "SGN", "tphcm": "SGN", "sg": "SGN", "sgn": "SGN", "sài gòn": "SGN",
    "đà nẵng": "DAD", "da nang": "DAD", "dad": "DAD",
    "nha trang": "CXR", "cxr": "CXR",
    "phú quốc": "PQC", "phu quoc": "PQC", "pqc": "PQC",
    "đà lạt": "DLI", "da lat": "DLI", "dli": "DLI",
    "huế": "HUI", "hue": "HUI", "hui": "HUI"
}

# Cấu hình OpenWeatherMap từ .env
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

# Bảng mã thời tiết WMO (World Meteorological Organization)
WMO_CODES = {
    0: "Trời quang đãng (Clear sky)",
    1: "Trời ít mây (Mainly clear)",
    2: "Trời nhiều mây (Partly cloudy)",
    3: "Trời u ám (Overcast)",
    45: "Sương mù (Fog)",
    48: "Sương giá rải rác (Depositing rime fog)",
    51: "Mưa phùn nhẹ (Light drizzle)",
    53: "Mưa phùn vừa (Moderate drizzle)",
    55: "Mưa phùn nặng (Dense drizzle)",
    61: "Mưa nhẹ (Slight rain)",
    63: "Mưa vừa (Moderate rain)",
    65: "Mưa to (Heavy rain)",
    71: "Tuyết rơi nhẹ (Slight snow fall)",
    73: "Tuyết rơi vừa (Moderate snow fall)",
    75: "Tuyết rơi mạnh (Heavy snow fall)",
    80: "Mưa rào nhẹ (Slight rain showers)",
    81: "Mưa rào vừa (Moderate rain showers)",
    82: "Mưa rào mạnh (Violent rain showers)",
    95: "Dông nhẹ (Thunderstorm slight)",
    96: "Dông có mưa đá (Thunderstorm with hail)"
}

def _http_get_with_retry(url: str, params: Dict[str, Any] = None, timeout: int = 10, retries: int = 2) -> requests.Response:
    """Helper: Gửi yêu cầu HTTP GET với cơ chế tự động thử lại khi gặp lỗi mạng/SSL (tối đa 2 lần)."""
    last_exception = None
    for i in range(retries + 1):
        try:
            response = requests.get(url, params=params, verify=False, timeout=timeout)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, Exception) as e:
            last_exception = e
            if i < retries:
                import time
                time.sleep(1) # Chờ 1 giây trước khi thử lại
    raise last_exception

def get_coordinates(location: str) -> Optional[Dict[str, Any]]:
    """Helper: Tìm tọa độ từ tên địa điểm."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": location, "count": 1, "language": "en", "format": "json"}
    try:
        response = _http_get_with_retry(url, params=params)
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            return {
                "lat": result["latitude"], 
                "lon": result["longitude"], 
                "name": result.get("name", location), 
                "country": result.get("country", "")
            }
    except Exception:
        pass
    return None

@tool
def get_airport_code(location: str) -> str:
    """
    Tìm mã sân bay IATA 3 chữ cái cho một địa danh/thành phố. 
    Hãy gọi công cụ này TRƯỚC khi gọi search_flights nếu bạn chưa biết mã IATA của thành phố đó.
    Tham số:
    - location: tên thành phố hoặc địa danh (VD: 'Pleiku', 'Phú Quốc', 'Paris')
    """
    def remove_accents(input_str):
        import unicodedata
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

    loc_clean = location.lower().strip()
    loc_no_accents = remove_accents(loc_clean)
    
    # 1. Kiểm tra cache địa phương (chấp nhận cả có dấu và không dấu)
    if loc_clean in IATA_MAP:
        return IATA_MAP[loc_clean]
    if loc_no_accents in IATA_MAP:
        return IATA_MAP[loc_no_accents]
    
    # 2. Tra cứu từ mã (nếu chính nó là mã)
    if len(loc_clean) == 3 and loc_clean.upper() in IATA_MAP.values():
        return loc_clean.upper()

    # 3. Tra cứu từ Internet qua Tavily
    api_key = get_tavily_key()
    if not api_key:
        return f"Lỗi: Chưa cấu hình TAVILY_API_KEY để tra cứu mã '{location}'."

    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": f"3-letter IATA airport code for {location} city",
            "search_depth": "basic",
            "max_results": 3
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Tìm mã 3 chữ cái viết hoa trong kết quả search
            import re
            all_content = " ".join([r.get("content", "") for r in data.get("results", [])])
            # Ưu tiên các mã 3 chữ cái viết hoa nằm trong ngoặc hoặc đứng cạnh từ 'IATA'
            codes = re.findall(r'\b([A-Z]{3})\b', all_content)
            if codes:
                # Trả về mã đầu tiên tìm thấy (thường là mã chính xác nếu search tốt)
                # Loại bỏ các mã không phải sân bay (hàng rào đơn giản)
                potential_code = codes[0]
                return potential_code
    except Exception:
        pass
    
    return f"Không thể xác định mã IATA cho '{location}'. Vui lòng thử tên thành phố lớn phổ biến."

@tool
def search_flights(origin: str, destination: str) -> str:
    """
    Tìm kiếm các chuyến bay thực tế giữa hai địa điểm bằng mã sân bay IATA.
    Bạn PHẢI cung cấp mã IATA 3 chữ cái (VD: 'HAN', 'SGN', 'DAD'). 
    Nếu chưa biết mã, hãy gọi 'get_airport_code' trước.
    Tham số:
    - origin: mã IATA điểm đi (3 chữ cái, VD: 'HAN')
    - destination: mã IATA điểm đến (3 chữ cái, VD: 'SGN')
    """
    origin_iata = origin.upper().strip()
    dest_iata = destination.upper().strip()

    if len(origin_iata) != 3 or len(dest_iata) != 3:
        return "Lỗi: search_flights yêu cầu mã IATA 3 ký tự. Hãy dùng 'get_airport_code' để tìm mã nếu cần."

    if origin_iata == dest_iata:
        return f"Lỗi: Điểm đi và điểm đến giống nhau ({origin_iata})."

    target_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        flight_data = [FData(date=target_date, from_airport=origin_iata, to_airport=dest_iata)]
        result = get_flights(
            flight_data=flight_data,
            trip="one-way",
            passengers=Passengers(adults=1),
            seat="economy"
        )
        
        flights = result.flights[:5]
        if not flights:
            return f"Không tìm thấy chuyến bay thực tế nào từ {origin} đến {destination} vào ngày {target_date}."

        res = f"Danh sách chuyến bay THỰC TẾ từ {origin} đi {destination} (ngày {target_date}):\n"
        for idx, f in enumerate(flights, 1):
            price_val = str(f.price).replace(',', '').replace('.', '').replace(' ', '').replace('VNĐ', '').replace('₫', '').strip()
            price_val = price_val if price_val.isdigit() else "0"
            price_str = f"{int(price_val):,}".replace(",", ".") + "đ"
            
            airline_name = getattr(f, 'name', '').strip() or "Hãng hàng không"
            dep_time = getattr(f, 'departure', '').strip() or "Theo lịch"
            
            res += f"{idx}. Hãng: {airline_name} | Giờ bay: {dep_time} - {f.arrival} | Giá vé: {price_str} (hạng ghế: economy)\n"
        return res

    except Exception as e:
        return f"Không thể tra cứu chuyến bay trực tuyến lúc này từ {origin} đi {destination}. Lỗi hệ thống: {str(e)}"

async def _scrape_booking_async(city: str) -> list:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale='vi-VN',
            timezone_id='Asia/Ho_Chi_Minh'
        )
        page = await context.new_page()
        
        def remove_accents(input_str):
            import unicodedata
            nfkd_form = unicodedata.normalize('NFKD', input_str)
            return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
            
        clean_city = remove_accents(city)
        # Sử dụng urllib parse để chống URL injection 
        city_slug = urllib.parse.quote_plus(clean_city)
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        search_url = f"https://www.booking.com/searchresults.vi.html?ss={city_slug}&checkin={tomorrow}&checkout={day_after}"
        
        try:
            # Chặn tải các resource không cần thiết để scraper lướt nhanh và nhẹ
            async def handle_route(route):
                try:
                    if route.request.resource_type in ["document", "script", "xhr", "fetch"]:
                        await route.continue_()
                    else:
                        await route.abort()
                except Exception:
                    pass

            await page.route("**/*", handle_route)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector('div[data-testid="property-card"]', timeout=15000)
        except Exception as e:
            if browser:
                await browser.close()
            return []

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select('div[data-testid="property-card"]')
        results = []
        
        for card in cards[:5]:
            name_elem = card.select_one('div[data-testid="title"], h3')
            price_elem = card.select_one('span[data-testid="price-and-discounted-price"]') or card.select_one('div[data-testid="price-and-discounted-price"]') or card.select_one('[data-testid="price-and-discounted-price"]')
            area_elem = card.select_one('span[data-testid="address-line-element-location-details"], [data-testid="location"]')
            rating_elem = card.select_one('div[data-testid="review-score"]')

            if name_elem:
                name = name_elem.get_text(strip=True).replace('Opens in new window', '')
                price = 0
                if price_elem:
                    raw_price_text = price_elem.get_text(strip=True)
                    all_numbers = re.findall(r'\d+', raw_price_text.replace(',', '').replace('.',''))
                    if all_numbers:
                        price = int(all_numbers[-1])
                
                area = area_elem.get_text(strip=True) if area_elem else "Không rõ khu vực"
                rating_text = rating_elem.get_text(strip=True) if rating_elem else "Chưa đánh giá"
                
                results.append({
                    "name": name,
                    "stars": 4, 
                    "price_per_night": price,
                    "area": area,
                    "rating": rating_text
                })

        await browser.close()
        return results

@tool
def search_hotels(city: str, max_price_per_night: int = 99999999) -> str:
    """
    Tìm kiếm khách sạn tại một thành phố.
    Tham số:
    - city: tên thành phố.
    - max_price_per_night: giá tối đa mỗi đêm.
    """
    try:
        # Ép kiểu max_price_per_night an toàn
        max_price = int(max_price_per_night)
    except (ValueError, TypeError):
        max_price = 99999999

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            
        real_hotels = loop.run_until_complete(_scrape_booking_async(city))
        
        if not real_hotels:
            return f"Kết quả Scraper: Đã cào Booking.com nhưng không lấy được khách sạn hoặc bị chặn. Hãy nhắc người dùng đổi địa điểm hoặc cung cấp gợi ý chung."
            
        valid_hotels = [h for h in real_hotels if 0 < h['price_per_night'] <= max_price]
        
        if not valid_hotels:
            return f"Kết quả Scraper: Tìm thấy khách sạn tại {city} nhưng không có cái nào giá dưới {max_price:,}đ/đêm."
            
        res = f"Kết quả Scraper (Booking.com): Khách sạn tại {city} (Giá dưới {max_price:,}đ/đêm):\n".replace(",", ".")
        for idx, h in enumerate(valid_hotels, 1):
            price_str = f"{h['price_per_night']:,}".replace(",", ".") + "đ"
            res += f"{idx}. Khách sạn: {h['name']} | Khu vực: {h['area']} | Đánh giá: {h['rating']} | Giá: {price_str}/đêm\n"
        return res

    except Exception as e:
        return f"Lỗi hệ thống khi tìm phòng: {str(e)}"

@tool
def calculate_budget(total_budget: int, expenses: str) -> str:
    """
    Tính toán ngân sách còn lại sau khi trừ các khoản chi phí.
    Tham số:
    - total_budget: tổng ngân sách ban đầu (VNĐ)
    - expenses: chuỗi mô tả các khoản chi. Định dạng 'tên_khoản:số_tiền' (VD: 'vé_máy_bay:890000,khách_sạn:650000')
    """
    try:
        total_budget = int(total_budget)
        total_expense = 0
        expense_list = []
        
        # Xử lý input rác hoặc có khoảng trắng
        items = [x for x in expenses.split(',') if x.strip()]
        if not items:
            return "Lỗi: Tham số expenses không đúng format hoặc bị rỗng."

        for item in items:
            parts = item.split(':')
            if len(parts) != 2:
                continue # Skip những item lỗi
            
            name = parts[0].strip()
            amount_str = parts[1].strip()
            
            # Extract numbers only to prevent crashes
            numbers = re.findall(r'\d+', amount_str)
            if not numbers:
                continue
            
            amount = int("".join(numbers))
            total_expense += amount
            expense_list.append((name.replace('_', ' ').capitalize(), amount))
            
        if not expense_list:
            return "Lỗi: Không parsing được chi phí nào hợp lệ. Vui lòng thử lại với định dạng 'tên:số'."

        remaining = total_budget - total_expense
        
        res = "Bảng chi phí:\n"
        for name, amount in expense_list:
            res += f"- {name}: {amount:,}đ\n".replace(",", ".")
        res += "---\n"
        res += f"Tổng chi: {total_expense:,}đ\n".replace(",", ".")
        res += f"Ngân sách ban đầu: {total_budget:,}đ\n".replace(",", ".")
        if remaining < 0:
            res += f"Vượt quá ngân sách {abs(remaining):,}đ! Cần điều chỉnh lại khách sạn hoặc chuyến bay.\n".replace(",", ".")
        else:
            res += f"Còn lại dư: {remaining:,}đ\n".replace(",", ".")
        return res
    except Exception as e:
        return f"Lỗi tính toán ngân sách: {str(e)}. Tham số đưa vào không đúng định dạng."

@tool
def get_weather_forecast(location: str) -> str:
    """
    Lấy thông tin thời tiết hiện tại cho một địa điểm (Thành phố).
    Tham số:
    - location: Tên thành phố muốn xem thời tiết.
    """
    coords = get_coordinates(location)
    if not coords:
        return f"Không tìm thấy tọa độ cho địa điểm: {location}."

    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": coords["lat"], "longitude": coords["lon"], "current_weather": "true", "timezone": "auto"}

    try:
        response = _http_get_with_retry(url, params=params)
        data = response.json()
        if "current_weather" in data:
            cw = data["current_weather"]
            weather_desc = WMO_CODES.get(cw["weathercode"], "Không xác định")
            return (f"🌤️ THỜI TIẾT TẠI {coords['name'].upper()}, {coords['country']}:\n"
                    f"- Nhiệt độ: {cw['temperature']}°C\n"
                    f"- Tình trạng: {weather_desc}\n"
                    f"- Tốc độ gió: {cw['windspeed']} km/h")
    except Exception as e:
        # Fallback to OpenWeatherMap
        if OPENWEATHERMAP_API_KEY:
            owm_url = "https://api.openweathermap.org/data/2.5/weather"
            owm_params = {
                "lat": coords["lat"],
                "lon": coords["lon"],
                "appid": OPENWEATHERMAP_API_KEY,
                "units": "metric",
                "lang": "vi"
            }
            try:
                owm_res = _http_get_with_retry(owm_url, params=owm_params)
                owm_data = owm_res.json()
                temp = owm_data["main"]["temp"]
                desc = owm_data["weather"][0]["description"].capitalize()
                wind = owm_data["wind"]["speed"] * 3.6 # m/s to km/h
                return (f"🌤️ THỜI TIẾT TẠI {coords['name'].upper()} (Nguồn: OpenWeatherMap):\n"
                        f"- Nhiệt độ: {temp}°C\n"
                        f"- Tình trạng: {desc}\n"
                        f"- Tốc độ gió: {wind:.1f} km/h")
            except Exception as owm_e:
                return f"Lỗi thời tiết: Cả Open-Meteo ({str(e)}) và OpenWeatherMap ({str(owm_e)}) đều không khả dụng."
        return f"Lỗi khi lấy dữ liệu thời tiết: {str(e)}"
    return f"Không có dữ liệu thời tiết cho {location}."

@tool
def get_air_quality(location: str) -> str:
    """
    Kiểm tra chỉ số chất lượng không khí (AQI) và mức độ ô nhiễm tại một địa điểm (Thành phố).
    """
    coords = get_coordinates(location)
    if not coords:
        return f"Không tìm thấy tọa độ để kiểm tra không khí tại: {location}."

    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "current": "european_aqi,pm10,pm2_5",
        "timezone": "auto"
    }

    try:
        response = _http_get_with_retry(url, params=params)
        data = response.json()

        if "current" in data:
            curr = data["current"]
            aqi = curr["european_aqi"]
            pm10 = curr["pm10"]
            pm25 = curr["pm2_5"]

            # Phân loại mức độ AQI (Chuẩn Châu Âu)
            if aqi <= 20: status = "Rất tốt (Great)"
            elif aqi <= 40: status = "Tốt (Good)"
            elif aqi <= 60: status = "Trung bình (Fair)"
            elif aqi <= 80: status = "Kém (Poor)"
            elif aqi <= 100: status = "Rất kém (Very Poor)"
            else: status = "Cực kỳ kém (Extremely Poor)"

            return (f"🌬️ CHẤT LƯỢNG KHÔNG KHÍ TẠI {coords['name'].upper()}:\n"
                    f"- Chỉ số AQI: {aqi} ({status})\n"
                    f"- Bụi mịn PM2.5: {pm25} µg/m³\n"
                    f"- Bụi mịn PM10: {pm10} µg/m³")
    except Exception as e:
        # Fallback to OpenWeatherMap Air Pollution
        if OPENWEATHERMAP_API_KEY:
            owm_url = "http://api.openweathermap.org/data/2.5/air_pollution"
            owm_params = {
                "lat": coords["lat"],
                "lon": coords["lon"],
                "appid": OPENWEATHERMAP_API_KEY
            }
            try:
                owm_res = _http_get_with_retry(owm_url, params=owm_params)
                owm_data = owm_res.json()
                
                if "list" in owm_data and len(owm_data["list"]) > 0:
                    curr = owm_data["list"][0]
                    aqi_level = curr["main"]["aqi"] # 1=Good, 2=Fair, 3=Moderate, 4=Poor, 5=Very Poor
                    comp = curr["components"]
                    
                    status_map = {1: "Tốt (Good)", 2: "Khá (Fair)", 3: "Trung bình (Moderate)", 4: "Kém (Poor)", 5: "Rất kém (Very Poor)"}
                    status = status_map.get(aqi_level, "Không xác định")
                    
                    return (f"🌬️ CHẤT LƯỢNG KHÔNG KHÍ TẠI {coords['name'].upper()} (Nguồn: OpenWeatherMap):\n"
                            f"- Chỉ số AQI (1-5): {aqi_level} ({status})\n"
                            f"- Bụi mịn PM2.5: {comp['pm2_5']} µg/m³\n"
                            f"- Bụi mịn PM10: {comp['pm10']} µg/m³")
            except Exception as owm_e:
                return f"Lỗi không khí: Cả Open-Meteo ({str(e)}) và OpenWeatherMap ({str(owm_e)}) đều không khả dụng."
        return f"Lỗi khi kiểm tra chất lượng không khí: {str(e)}"
    return f"Không có dữ liệu không khí cho {location}."

@tool
def get_current_location() -> str:
    """
    Tự động xác định vị trí hiện tại của người dùng dựa trên địa chỉ IP.
    Trả về: Tên thành phố và tọa độ (vĩ độ, kinh độ).
    """
    try:
        # Sử dụng dịch vụ ip-api.com
        response = _http_get_with_retry("http://ip-api.com/json/", timeout=5)
        data = response.json()
        if data.get("status") == "success":
            city = data.get("city")
            lat = data.get("lat")
            lon = data.get("lon")
            country = data.get("country")
            return f"Vị trí phát hiện qua IP: {city}, {country} (Tọa độ: {lat}, {lon})"
        else:
            return "Không thể tự động xác định vị trí qua IP thành công."
    except Exception as e:
        return f"Lỗi khi xác định vị trí IP: {e}"
