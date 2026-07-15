import pandas as pd
import requests
import plotly.graph_objects as io_go
import plotly.io as pio
from datetime import datetime
from user_agent import random_user

# Cấu hình
head = {"User-Agent": random_user()}
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

# 1. Hàm tính toán cho từng cổ phiếu
def tinh_du_lieu_cp(symbol, ngay_moi_nhat, day_end, df_old):
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_moi_nhat}~date:lte:{day_end}&size=100000&page=1'
    try:
        r = requests.get(url, headers=head, timeout=30)
        data = r.json().get('data', [])
        if not data: return None
        
        df_new = pd.DataFrame(data)
        df_new.rename(columns={'nmVolume': 'klgd_khop_lenh', 'ptVolume': 'klgd_thoa_thuan', 'pctChange': '+/-%'}, inplace=True)
        df_new['volume'] = df_new['klgd_khop_lenh'] + df_new['klgd_thoa_thuan']
        df_new['date'] = pd.to_datetime(df_new['date'], format='mixed', dayfirst=True)
        
        # Gộp và xử lý trùng lặp
        df_updated = pd.concat([df_old, df_new]).drop_duplicates(subset=['date', 'close', 'volume'], keep='first')
        last_row = df_updated.iloc[-1]
        
        # Tính toán các chỉ số
        gia_close = float(last_row['close'])
        BD_gia = float(last_row['+/-%'])
        KLGD_KLTB21_mean = df_updated['volume'].tail(21).mean()
        KLTB_KLTB21 = float(last_row['volume']) / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0
        
        return [gia_close, BD_gia, KLTB_KLTB21]
    except:
        return None

# 2. Hàm xử lý trung bình ngành
def ham_tinh_tb_nganh(ten_nganh, list_ds_cp):
    results = []
    day_end = datetime.now().strftime("%Y-%m-%d")
    
    for ma in list_ds_cp:
        # Giả sử bạn có hàm load_database_old để lấy data cũ
        df_ma = load_database_old(ma) 
        if df_ma is not None:
            ngay_moi_nhat = pd.to_datetime(df_ma['date'].iloc[-1]).strftime("%Y-%m-%d")
            kq = tinh_du_lieu_cp(ma, ngay_moi_nhat, day_end, df_ma)
            if kq: results.append(kq)
    
    if not results: return None
    
    df_temp = pd.DataFrame(results, columns=['gia', 'percent_change', 'volume_ratio'])
    return pd.Series({'name': ten_nganh, 'percent_change': df_temp['percent_change'].mean(), 'volume_ratio': df_temp['volume_ratio'].mean()})

# 3. Hàm chính và Vẽ biểu đồ
def main():
    # Giả sử danhsach_theo_nganh là dict đã load từ Excel
    danh_sach_kq = []
    for nganh, df_raw in danhsach_theo_nganh.items():
        row = ham_tinh_tb_nganh(nganh, df_raw['Ticker'].tolist())
        if row is not None: danh_sach_kq.append(row)
    
    df_final = pd.DataFrame(danh_sach_kq)
    df_final['updated_at'] = datetime.now().strftime("%H:%M %d/%m/%Y")
    
    # Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='#ffc107')))
    
    fig.update_layout(
        title=f"Phân tích các ngành (Cập nhật: {df_final['updated_at'].iloc[0]})",
        paper_bgcolor='#212529', plot_bgcolor='#2b3035', font_color="white"
    )
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(pio.to_html(fig, full_html=True))

if __name__ == "__main__":
    main()
