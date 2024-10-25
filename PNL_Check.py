# PNL_Check.py
from binance.client import Client

# Biến toàn cục để lưu trữ PNL%
pnl_percentage = None
pnl_usdt = None  # Thêm biến toàn cục để lưu trữ PNL (USDT)

# Hàm trích xuất và tính toán PNL
def extract_pnl_and_position_info(client, symbol):
    global pnl_percentage, pnl_usdt  # Khai báo biến toàn cục

    # Lấy thông tin vị thế hiện tại từ Binance API
    position_info = client.futures_position_information(symbol=symbol)
    position_amt = float(position_info[0]['positionAmt'])  # Số lượng vị thế, bao gồm cả âm hoặc dương
    entry_price = float(position_info[0]['entryPrice'])
    mark_price = float(position_info[0]['markPrice'])
    leverage = float(position_info[0]['leverage'])

    # Kiểm tra vị thế (long hoặc short)
    if position_amt > 0:  # Vị thế mua (long)
        pnl_usdt = (mark_price - entry_price) * abs(position_amt)
    elif position_amt < 0:  # Vị thế bán (short)
        pnl_usdt = (entry_price - mark_price) * abs(position_amt)
    else:
        pnl_usdt = 0  # Không có vị thế mở

    # Thêm dấu + hoặc - cho PNL (USDT)
    pnl_usdt_display = f"+{pnl_usdt:.2f}" if pnl_usdt > 0 else f"{pnl_usdt:.2f}"
    print(f"PNL hiện tại (USDT): {pnl_usdt_display} USDT")

    # Tính Position Value (USDT)
    position_value_usdt = (entry_price * abs(position_amt)) / leverage
    print(f"Giá trị vị thế (Position Value) (USDT): {position_value_usdt:.2f} USDT")

    # Tính PNL (%) nếu giá trị Position Value không phải 0
    if position_value_usdt != 0:
        pnl_percentage = (pnl_usdt / position_value_usdt) * 100

        # Thêm dấu + hoặc - cho PNL%
        pnl_percentage_display = f"+{pnl_percentage:.2f}" if pnl_percentage > 0 else f"{pnl_percentage:.2f}"
        print(f"PNL hiện tại (%): {pnl_percentage_display}%")
    else:
        pnl_percentage = None
        print("Không thể tính toán PNL% do Position Value bằng 0.")

# Hàm trả về giá trị của pnl_percentage
def get_pnl_percentage():
    global pnl_percentage  # Khai báo biến toàn cục để đảm bảo truy cập được
    return pnl_percentage

# Hàm trả về giá trị của pnl_usdt
def get_pnl_usdt():
    global pnl_usdt  # Khai báo biến toàn cục để đảm bảo truy cập được
    return pnl_usdt
