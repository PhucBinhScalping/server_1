import pandas as pd
import requests
import os
import plotly.graph_objects as io_go
import plotly.io as pio
from datetime import datetime, timedelta
from user_agent import random_user

# 1. Cấu hình ban đầu
head = {"User-Agent": random_user()}
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

def download_data():
    """Tải dữ liệu toàn sàn để tránh bị chặn IP khi gọi từng mã"""
    print("Đang tải dữ liệu toàn thị trường...")
    # Lấy dữ liệu 30 ngày gần nhất
    fdate = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    url = f"https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=50000&page=1"
    
    try:
        r = requests.get(url, headers=head, timeout=60)
        if r.status_code == 200:
            df = pd.DataFrame(r.json().get('data', []))
            df.rename(columns={'code': 'symbol', 'nmVolume': 'volume', 'pctChange': 'pctChange'}, inplace=True)
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            df['pctChange'] = pd.to_numeric(df['pctChange'], errors='coerce')
            return df
    except Exception as e:
        print(f"Lỗi tải dữ liệu: {e}")
    return pd.DataFrame()

def main():
    # 2. Tải và xử lý dữ liệu
    market_df = download_data()
    if market_df.empty:
        print("Không có dữ liệu, kiểm tra lại kết nối!")
        return

    df_company = pd.read_excel(FILE_DANH_SACH)
    
    # 3. Tính toán dữ liệu ngành (gom nhóm)
    results = []
    for nganh, group in df_company.groupby('Ngành Cấp 2'):
        symbols = group['Ticker'].astype(str).tolist()
        data_nganh = market_df[market_df['symbol'].isin(symbols)]
        
        if not data_nganh.empty:
            # Tính trung bình % thay đổi và trung bình khối lượng
            pct_mean = data_nganh.groupby('symbol')['pctChange'].last().mean()
            vol_mean = data_nganh.groupby('symbol')['volume'].last().mean() / 100000
            results.append({'name': nganh, 'percent_change': pct_mean, 'volume_ratio': vol_mean})

    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)

    # 4. Vẽ biểu đồ (Sửa lỗi titlefont)
    fig = io_go.Figure()
    
    # Bar cho biến động
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='Biến động (%)', marker_color=colors))
    
    # Line cho thanh khoản
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='Thanh khoản', yaxis='y2', line=dict(color='#ffc107', width=3)))

    fig.update_layout(
        title=dict(text="Phân tích diễn biến các ngành", font=dict(color="#ffffff")),
        paper_bgcolor='#212529', plot_bgcolor='#2b3035',
        yaxis=dict(title=dict(text="Biến động (%)", font=dict(color="#ffffff")), tickfont=dict(color="#ffffff")),
        yaxis2=dict(title=dict(text="Thanh khoản (x100k)", font=dict(color="#ffffff")), tickfont=dict(color="#ffffff"), overlaying='y', side='right'),
        legend=dict(font=dict(color="#ffffff"))
    )

    # 5. Xuất ra file index.html
    html_content = pio.to_html(fig, full_html=True)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("Đã hoàn thành! Mở file index.html để xem biểu đồ.")

if __name__ == "__main__":
    main()
