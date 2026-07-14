import pandas as pd
import requests
import time
import os
import plotly.graph_objects as io_go
import plotly.io as pio
from datetime import datetime, timedelta
from user_agent import random_user

# Cấu hình
head = {"User-Agent": random_user()}
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

def get_data_for_symbol(symbol):
    """Lấy dữ liệu cho 1 mã cụ thể với tham số symbol chuẩn"""
    fdate = (datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d')
    # URL có chứa tham số symbol như bạn yêu cầu
    url = f"https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{fdate}&size=1000&page=1"
    
    try:
        r = requests.get(url, headers=head, timeout=20)
        if r.status_code == 200:
            data = r.json().get('data', [])
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        print(f"Lỗi tải mã {symbol}: {e}")
    return pd.DataFrame()

def main():
    # 1. Đọc danh sách mã từ file Excel
    if not os.path.exists(FILE_DANH_SACH):
        print(f"Không tìm thấy file {FILE_DANH_SACH}")
        return
        
    df_company = pd.read_excel(FILE_DANH_SACH)
    results = []

    # 2. Vòng lặp lấy dữ liệu từng mã
    for nganh, group in df_company.groupby('Ngành Cấp 2'):
        print(f"Đang xử lý ngành: {nganh}")
        pct_list = []
        vol_list = []
        
        for symbol in group['Ticker'].astype(str).tolist():
            df_symbol = get_data_for_symbol(symbol)
            if not df_symbol.empty:
                # Lấy phiên mới nhất
                latest = df_symbol.iloc[-1]
                pct_list.append(pd.to_numeric(latest.get('pctChange', 0), errors='coerce'))
                vol_list.append(pd.to_numeric(latest.get('nmVolume', 0), errors='coerce'))
            
            # Dừng 0.3s để tránh bị chặn IP
            time.sleep(0.3)
        
        # 3. Tính toán trung bình cho ngành
        if pct_list:
            results.append({
                'name': nganh,
                'percent_change': sum(pct_list) / len(pct_list),
                'volume_ratio': (sum(vol_list) / len(vol_list)) / 100000
            })

    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)

    # 4. Vẽ biểu đồ
    fig = io_go.Figure()
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='Biến động (%)', marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='Thanh khoản', yaxis='y2', line=dict(color='#ffc107', width=3)))

    fig.update_layout(
        title=dict(text="Phân tích diễn biến các ngành", font=dict(color="#ffffff")),
        paper_bgcolor='#212529', plot_bgcolor='#2b3035',
        yaxis=dict(title=dict(text="Biến động (%)", font=dict(color="#ffffff")), tickfont=dict(color="#ffffff")),
        yaxis2=dict(title=dict(text="Thanh khoản", font=dict(color="#ffffff")), tickfont=dict(color="#ffffff"), overlaying='y', side='right'),
        legend=dict(font=dict(color="#ffffff"))
    )

    # 5. Xuất HTML
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(pio.to_html(fig, full_html=True))
    
    print("Đã hoàn tất! File index.html đã được cập nhật.")

if __name__ == "__main__":
    main()
