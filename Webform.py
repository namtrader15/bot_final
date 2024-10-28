from Entry_Super import get_final_trend  # Import hàm phân tích xu hướng tổng thể
from binance.client import Client
from flask import Flask, request, jsonify, render_template
import time
import threading
import pytz
from datetime import datetime
from PNL_Check import extract_pnl_and_position_info, get_pnl_percentage, get_pnl_usdt  # Sử dụng hàm từ PNL_Check
from trade_history import save_trade_history  # Import từ trade_history.py
import socket
#from playsound import playsound
from atr_check import atr_stop_loss_finder  # Gọi hàm từ file atr_calculator.py
from TPO_POC import calculate_poc_value
from binance.exceptions import BinanceAPIException, BinanceRequestException

# Biến toàn cục để lưu trữ client và thông tin giao dịch
client = None
last_order_status = None  # Biến lưu trữ trạng thái lệnh cuối cùng
stop_loss_price = None  # Biến toàn cục để lưu giá trị stop-loss

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Biến toàn cục để lưu API key, Secret key, Client và điều khiển vòng lặp
api_key = ""
secret_key = ""
client = None
trading_thread = None
running = False  # Điều khiển vòng lặp

# Hàm kiểm tra kết nối Internet
def is_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), 2)
        return True
    except OSError:
        return False

def alert_sound():
    try:
        print(f"Lỗi phát âm thanh: {str(e)}")
        #playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
    except Exception as e:
        print(f"Lỗi phát âm thanh: {str(e)}")

def check_internet_and_alert():
    try:
        if not is_connected():
            print("Mất kết nối internet. Đang phát cảnh báo...")
         #   playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
            time.sleep(5)
            return False
    except Exception as e:
        print(f"Lỗi khi kiểm tra kết nối: {str(e)}")
        #playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
        time.sleep(5)
        return False
    return True

# Thêm giao diện để hiển thị form nhập API key, Secret key và các nút điều khiển
@app.route('/')
def index():
    return render_template('index.html')
#set_api
@app.route('/set_api', methods=['POST'])
def set_api():
    global api_key, secret_key, client
    data = request.json
    api_key = data.get('api_key')
    secret_key = data.get('secret_key')
    client = Client(api_key, secret_key)
    return jsonify({"status": "API keys set successfully!"})

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global running, trading_thread
    if not running:
        running = True
        trading_thread = threading.Thread(target=trading_bot)
        trading_thread.start()
        return jsonify({"status": "Bot started"})
    else:
        return jsonify({"status": "Bot is already running"})

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global running
    if running:
        running = False
        return jsonify({"status": "Bot stopped"})
    else:
        return jsonify({"status": "Bot is not running"})


# Route để trả về thông tin trạng thái của bot cho giao diện
@app.route('/status', methods=['GET'])
def status():
    if not running:
        return jsonify({"status": "Bot chưa chạy"})
    
    try:
        # Lấy thông tin từ API
        current_balance = get_account_balance(client)
        extract_pnl_and_position_info(client, 'BTCUSDT')
        
        pnl_percentage = get_pnl_percentage()
        if pnl_percentage is None:
            pnl_percentage = 0.0  # Giá trị mặc định nếu cần
        
        pnl_color = 'green' if pnl_percentage >= 0 else 'red'
        pnl_display = f"{pnl_percentage:.2f}%"
        pnl_width = abs(pnl_percentage)

        # Lấy thông tin vị thế
        position_info = client.futures_position_information(symbol='BTCUSDT')
        entry_price = float(position_info[0]['entryPrice'])
        mark_price = float(position_info[0]['markPrice'])
        qty = float(position_info[0]['positionAmt'])
        position_type = "Long" if qty > 0 else "Short" if qty < 0 else "Không có vị thế"

        return jsonify({
            "current_balance": f"{current_balance:.2f} USDT",
            "entry_price": f"{entry_price:.2f} USDT",
            "mark_price": f"{mark_price:.2f} USDT",
            "position_type": position_type,
            "pnl_display": pnl_display,
            "pnl_color": pnl_color,
            "pnl_width": pnl_width,
            "last_order_status": last_order_status,
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": None  # Không có lỗi
        })
    
    except BinanceAPIException as e:
        # Lấy thông tin chi tiết từ lỗi BinanceAPIException
        error_message = f"Lỗi khi gọi API hoặc xử lý giao dịch: {str(e)}"
        request_ip = None
        if "request ip" in str(e):
            request_ip = str(e).split("request ip:")[-1].strip()  # Tách phần IP từ chuỗi lỗi
        
        print(error_message)
        return jsonify({
            "error": error_message,
            "request_ip": request_ip  # Thêm thông tin request IP vào JSON
        })
    except Exception as e:
        # Xử lý các lỗi không xác định khác
        error_message = f"Lỗi không xác định: {str(e)}"
        print(error_message)
        return jsonify({
            "error": error_message,
            "request_ip": None
        })



# Hàm lấy giá trị tài khoản Futures + retry
def get_account_balance(client, retries=5, delay=2):
    attempt = 0
    while attempt < retries:
        try:
            account_info = client.futures_account()
            usdt_balance = float(account_info['totalWalletBalance'])
            return usdt_balance
        except (BinanceAPIException, BinanceRequestException) as e:
            # Các lỗi khác từ API của Binance (không phải lỗi timeout)
            print(f"Lỗi Binance API: {str(e)}")
            break
        except requests.exceptions.ReadTimeout as e:
            # Xử lý lỗi ReadTimeout
            attempt += 1
            print(f"Lỗi ReadTimeout khi lấy dữ liệu. Thử lại ({attempt}/{retries}) sau {delay} giây...")
            time.sleep(delay)
        except Exception as e:
            # Các lỗi khác (bắt lỗi chung)
            print(f"Lỗi không xác định: {str(e)}")
            break
    print("Không thể lấy số dư sau nhiều lần thử.")
    return None  # Hoặc giá trị mặc định nếu không lấy được số dư

# Hàm cài đặt đòn bẩy cho giao dịch Futures
def set_leverage(client, symbol, leverage):
    try:
        response = client.futures_change_leverage(symbol=symbol, leverage=leverage)
        print(f"Đã cài đặt đòn bẩy {response['leverage']}x cho {symbol}.")
    except Exception as e:
        print(f"Lỗi khi cài đặt đòn bẩy: {str(e)}")

# Hàm kiểm tra nếu có lệnh nào đang mở
def check_open_position(client, symbol):
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])
    return qty != 0

def place_order(client, order_type):
    global last_order_status, stop_loss_price
    symbol = 'BTCUSDT'
    
    # Gọi hàm atr_stop_loss_finder để lấy các giá trị ATR
    atr_short_stop_loss, atr_long_stop_loss = atr_stop_loss_finder(client, symbol)
    
    usdt_balance = get_account_balance(client)
    klines = client.futures_klines(symbol=symbol, interval='1h', limit=1)  # Lấy nến hiện tại
    mark_price = float(klines[0][4])

    # Tính percent_change dựa trên kiểu lệnh (buy/sell)
    percent_change = None
    if order_type == "buy":
        percent_change = ((atr_long_stop_loss - mark_price) / mark_price) * 100
        stop_loss_price = atr_long_stop_loss  # Đặt Stop Loss cho lệnh Buy
    elif order_type == "sell":
        percent_change = ((mark_price - atr_short_stop_loss) / mark_price) * 100
        stop_loss_price = atr_short_stop_loss  # Đặt Stop Loss cho lệnh Sell

    if percent_change is not None and percent_change != 0:
        leverage = 100 / abs(percent_change)
        leverage = max(1, min(round(leverage), 125))  # Đảm bảo leverage nằm trong khoảng 1-125
        set_leverage(client, symbol, leverage)

    trading_balance = 20 * leverage  # Sử dụng R:R để tính số lượng giao dịch - Risk=20$
    ticker = client.get_symbol_ticker(symbol=symbol)
    btc_price = float(ticker['price'])
    quantity = round(trading_balance / btc_price, 3)

    if quantity <= 0:
        print("Số lượng giao dịch không hợp lệ. Hủy giao dịch.")
        return

    if order_type == "buy":
        client.futures_create_order(symbol=symbol, side='BUY', type='MARKET', quantity=quantity)
        last_order_status = f"Đã mua {quantity} BTC. Stop-loss đặt tại: {stop_loss_price:.2f} USDT."
        print(f"Giá trị stop-loss cho lệnh Buy: {stop_loss_price:.2f} USDT")
    elif order_type == "sell":
        client.futures_create_order(symbol=symbol, side='SELL', type='MARKET', quantity=quantity)
        last_order_status = f"Đã bán {quantity} BTC. Stop-loss đặt tại: {stop_loss_price:.2f} USDT."
        print(f"Giá trị stop-loss cho lệnh Sell: {stop_loss_price:.2f} USDT")



# Hàm kiểm tra điều kiện Stop Loss/Take Profit (Chỉ giữ điều kiện dựa trên PNL)
def check_sl_tp(client, symbol):
    global last_order_status, stop_loss_price
    extract_pnl_and_position_info(client, symbol)  # Lấy thông tin PNL và vị thế
    pnl_percentage = get_pnl_percentage()  # Giá trị PNL hiện tại (%)
    pnl_usdt = get_pnl_usdt()  # Giá trị PNL hiện tại (USDT)

    # Kiểm tra nếu PNL là None để tránh lỗi
    if pnl_percentage is None:
        print("Lỗi: PNL không có giá trị hợp lệ.")
        return None

    # Nếu PNL <= -100% (Stop Loss) hoặc PNL >= 175% (Take Profit)
    if pnl_percentage <= -100:
        print(f"Điều kiện StopLoss đạt được (PNL <= -100%). Đóng lệnh.")
        close_position(client, pnl_percentage, pnl_usdt)
    #    return "stop_loss"
    elif pnl_percentage >= 175:
        print(f"Điều kiện TakeProfit đạt được (PNL >= 175%). Đóng lệnh.")
        close_position(client, pnl_percentage, pnl_usdt)
    #   return "take_profit"

    return None

# Hàm đóng lệnh
def close_position(client, pnl_percentage, pnl_usdt):
    global last_order_status
    symbol = 'BTCUSDT'
    position_info = client.futures_position_information(symbol=symbol)
    qty = float(position_info[0]['positionAmt'])
    entry_price = float(position_info[0]['entryPrice'])
    entry_type = "Long" if qty > 0 else "Short" if qty < 0 else "Không có vị thế"

    if qty > 0:
        client.futures_create_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
        last_order_status = f"Đã đóng lệnh long {qty} BTC."
    elif qty < 0:
        client.futures_create_order(symbol=symbol, side='BUY', type='MARKET', quantity=abs(qty))
        last_order_status = f"Đã đóng lệnh short {abs(qty)} BTC."
    else:
        last_order_status = "Không có vị thế mở."

    pnl_percentage_display = f"+{pnl_percentage:.2f}%" if pnl_percentage > 0 else f"-{abs(pnl_percentage):.2f}%"
    pnl_usdt_display = f"+{pnl_usdt:.2f} USDT" if pnl_usdt > 0 else f"-{abs(pnl_usdt):.2f} USDT"
    print(f"Đóng lệnh - PNL hiện tại (USDT): {pnl_usdt_display}, PNL hiện tại (%): {pnl_percentage_display}, Entry Price: {entry_price:.2f} USDT, Entry Type: {entry_type}")
    save_trade_history(pnl_percentage, pnl_usdt, entry_price, entry_type)

# Biến toàn cục để theo dõi số vòng lặp
loop_count = 0  # Khởi tạo biến đếm vòng lặp

# Hàm bot giao dịch chạy mỗi 60 giây
def trading_bot():
    global client, loop_count, running  # Sử dụng biến running để điều khiển vòng lặp
    symbol = 'BTCUSDT'
    
    # Khởi tạo vòng lặp chính cho bot
    while running:
        try:
            # Kiểm tra kết nối Internet
            if not check_internet_and_alert():
                continue  # Nếu mất kết nối, tiếp tục vòng lặp để kiểm tra lại

            # Kiểm tra điều kiện Stop Loss hoặc Take Profit
            result = check_sl_tp(client, symbol)
            if result == "stop_loss" or result == "take_profit":
                break  # Nếu đạt điều kiện dừng lệnh, kết thúc vòng lặp

            # Lấy thông tin vị thế hiện tại
            position_info = client.futures_position_information(symbol=symbol)
            qty = float(position_info[0]['positionAmt'])

            # Nếu đã có lệnh mở, tiếp tục lặp lại sau 60 giây
            if qty != 0:  # Nếu có vị thế mở cho BTCUSDT
                print("Hiện đã có lệnh mở cho BTCUSDT. Vòng lặp sẽ lặp lại sau 60 giây.")
                time.sleep(60)
                continue  # Tiếp tục vòng lặp để kiểm tra lại vị thế

            # Nếu không có vị thế mở, kiểm tra xu hướng và thực hiện giao dịch
            final_trend = get_final_trend(client)
            print(f"Kết quả xu hướng từ hàm get_final_trend(): {final_trend}")

            # Nếu xu hướng không rõ ràng, nghỉ lâu hơn (600 giây)
            if final_trend == "Xu hướng không rõ ràng":
                print("Xu hướng không rõ ràng. Nghỉ 600 giây.")
                time.sleep(600)
                continue  # Tiếp tục kiểm tra lại sau thời gian nghỉ

            # Tính toán giá trị POC và kiểm tra điều kiện chênh lệch
            mark_price = float(position_info[0]['markPrice'])
            poc_value = calculate_poc_value(client)
            price_difference_percent = abs((poc_value - mark_price) / mark_price) * 100

            if price_difference_percent <= 0.5:  # Điều kiện chênh lệch không quá 0.5%
                if final_trend == "Xu hướng tăng":
                    print("Xu hướng tăng. POC value gần mark price. Thực hiện lệnh mua.")
                    place_order(client, "buy")
                elif final_trend == "Xu hướng giảm":
                    print("Xu hướng giảm. POC value gần mark price. Thực hiện lệnh bán.")
                    place_order(client, "sell")
            else:
                print(f"Chênh lệch giữa POC và mark price: {price_difference_percent:.2f}%. Không thực hiện lệnh.")

            # Sau khi thực hiện giao dịch, nếu không có vị thế, tiếp tục vòng lặp sau 60 giây
            time.sleep(60)

            # Tăng biến đếm vòng lặp
            loop_count += 1

            # Reset sau 100 vòng lặp
            if loop_count >= 100:
                print("Đã đạt 100 vòng lặp. Reset dữ liệu...")
                last_order_status = None  # Reset trạng thái lệnh cuối cùng
                stop_loss_price = None  # Reset giá trị stop-loss
                loop_count = 0  # Reset lại biến đếm vòng lặp
                # Khởi tạo lại client với API key mới nếu cần
                client = Client(api_key, secret_key, tld='com', testnet=False)

        except Exception as e:
            print(f"Lỗi khi gọi API hoặc xử lý giao dịch: {str(e)}")
            time.sleep(5)

    print("Bot đã dừng.")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

