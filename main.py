from Entry_Super import get_final_trend  # Import hàm phân tích xu hướng tổng thể 
from binance.client import Client
from flask import Flask
import time
import threading
import pytz
from datetime import datetime
from PNL_Check import extract_pnl_and_position_info, get_pnl_percentage, get_pnl_usdt  # Sử dụng hàm từ PNL_Check
from trade_history import save_trade_history  # Import từ trade_history.py
import socket
from playsound import playsound
from atr_check import atr_stop_loss_finder  # Gọi hàm từ file atr_calculator.py
from TPO_POC import calculate_poc_value  

# Biến toàn cục để lưu trữ client và thông tin giao dịch
client = None
last_order_status = None  # Biến lưu trữ trạng thái lệnh cuối cùng
stop_loss_price = None  # Biến toàn cục để lưu giá trị stop-loss

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Hàm kiểm tra kết nối Internet
def is_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), 2)
        return True
    except OSError:
        return False

def alert_sound():
    try:
        playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
    except Exception as e:
        print(f"Lỗi phát âm thanh: {str(e)}")

def check_internet_and_alert():
    try:
        if not is_connected():
            print("Mất kết nối internet. Đang phát cảnh báo...")
            playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
            time.sleep(5)
            return False
    except Exception as e:
        print(f"Lỗi khi kiểm tra kết nối: {str(e)}")
        playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
        time.sleep(5)
        return False
    return True

@app.route('/')
def home():
    global last_order_status
    current_balance = get_account_balance(client)
    extract_pnl_and_position_info(client, 'BTCUSDT')
    pnl_percentage = get_pnl_percentage()
    position_info = client.futures_position_information(symbol='BTCUSDT')
    entry_price = float(position_info[0]['entryPrice'])
    mark_price = float(position_info[0]['markPrice'])
    qty = float(position_info[0]['positionAmt'])
    position_type = "Long" if qty > 0 else "Short" if qty < 0 else "Không có vị thế"
    
    # Kiểm tra nếu pnl_percentage là None
    if pnl_percentage is None:
        pnl_percentage = 0.0  # Hoặc có thể gán một giá trị khác nếu cần
        pnl_display = "PNL chưa có giá trị"
    else:
        pnl_display = f"{pnl_percentage:.2f}%"
    
    pnl_color = 'green' if pnl_percentage >= 0 else 'red'
    pnl_width = abs(pnl_percentage)

    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    return f'''
    <html>
    <head>
        <title>Binance Bot Status</title>
        <meta http-equiv="refresh" content="300">
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                text-align: center;
                font-family: 'Roboto', sans-serif;
                background: #f7f9fc;
                color: #333;
            }}
            .container {{
                width: 50%;
                background: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                animation: fadeIn 1s ease-in-out;
            }}
            h1 {{
                color: #ff9f00;
            }}
            p {{
                font-size: 1.2em;
                margin: 10px 0;
            }}
            .pnl {{
                font-weight: bold;
                color: {pnl_color};
            }}
            .progress-container {{
                width: 100%;
                background-color: #ddd;
                border-radius: 5px;
                overflow: hidden;
                height: 20px;
                margin: 15px 0;
            }}
            .progress-bar {{
                height: 100%;
                width: {pnl_width}%;
                background-color: {pnl_color};
                text-align: center;
                color: white;
                line-height: 20px;
            }}
            footer {{
                margin-top: 20px;
                font-size: 0.9em;
                color: #888;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; }}
                to {{ opacity: 1; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Namtrader BTCUSDT.P Status</h1>
            <p>💵 Giá trị tài khoản hiện tại: {current_balance:.2f} USDT</p>
            <p>📈 Entry Price: {entry_price:.2f} USDT</p>
            <p>💰 Mark Price: {mark_price:.2f} USDT</p>
            <p>📉 Vị thế hiện tại: {position_type}</p>
            <p class="pnl">PNL hiện tại: <span class="progress-container"><span class="progress-bar">{pnl_display}</span></span></p>
            <p>Trạng thái lệnh cuối cùng: {last_order_status}</p>
            <p>🕒 Thời gian hiện tại (UTC+7): {current_time}</p>
            <footer>
                <p>&copy; 2024 NamTrading Bot</p>
            </footer>
        </div>
    </body>
    </html>
    '''


# Hàm lấy giá trị tài khoản Futures
def get_account_balance(client):
    account_info = client.futures_account()
    usdt_balance = float(account_info['totalWalletBalance'])
    return usdt_balance

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
    global client, loop_count
    api_key = 'TdpPYSNVLCUhzSq9lBSzVobpPK6qGIPQ53dM47qupsohOUZUw1XdqOterDZewWC0'
    api_secret = 'DIUWX1CHUIpKNhbmp0GEIgAHDDth7AeERQCfOAHz7Lk05lbmm31zr1h26tC3BvW9'
    client = Client(api_key, api_secret, tld='com', testnet=False)
    symbol = 'BTCUSDT'

    while True:
        try:
            # Kiểm tra kết nối Internet
            if not check_internet_and_alert():
                continue

            # Kiểm tra điều kiện Stop Loss hoặc Take Profit
            result = check_sl_tp(client, symbol)
            if result == "stop_loss" or result == "take_profit":
                break

            # Lấy thông tin vị thế hiện tại
            position_info = client.futures_position_information(symbol=symbol)
            qty = float(position_info[0]['positionAmt'])

            # Nếu đã có lệnh mở, giảm thời gian vòng lặp xuống 60 giây
            if qty != 0:  # Nếu có vị thế mở cho BTCUSDT
                print("Hiện đã có lệnh mở cho BTCUSDT. Vòng lặp sẽ lặp lại sau 60 giây.")
                time.sleep(60)
                continue  # Tiếp tục vòng lặp để kiểm tra lại sau 60 giây

            # Nếu không có vị thế mở, kiểm tra xu hướng và thực hiện giao dịch
            final_trend = get_final_trend(client)
            print(f"Kết quả xu hướng từ hàm get_final_trend(): {final_trend}")

            # Nếu xu hướng không rõ ràng, nghỉ lâu hơn (600 giây)
            if final_trend == "Xu hướng không rõ ràng":
                print("Xu hướng không rõ ràng. Nghỉ 600 giây.")
                time.sleep(600)
                continue

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
                client = Client(api_key, api_secret, tld='com', testnet=False)  # Reset lại client nếu cần

        except Exception as e:
            print(f"Lỗi khi gọi API hoặc xử lý giao dịch: {str(e)}")
            playsound(r"C:\Users\DELL\Desktop\GPT train\noconnect.mp3")
            time.sleep(5)

if __name__ == "__main__":
    trading_thread = threading.Thread(target=trading_bot)
    trading_thread.start()
    app.run(host='0.0.0.0', port=8080)
