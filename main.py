import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
from user_agent import random_user

# Cấu hình để lấy dữ liệu
head = {"User-Agent": random_user()}

def get_market_data():
    fdate = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    url = f"https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=50000"
    try:
        r = requests.get(url, headers=head, timeout=60)
        df = pd.DataFrame(r.json().get('data', []))
        df['date'] = pd.to_datetime(df['date'])
        df.rename(columns={'code': 'symbol', 'nmVolume': 'volume', 'pctChange': 'pctChange'}, inplace=True)
        return df
    except:
        return pd.DataFrame()

def main():
    # 1. Lấy và tính toán dữ liệu
    market_df = get_market_data()
    if market_df.empty: return
    
    df_company = pd.read_excel("danh_sach_cong_ty.xlsx")
    vingroup_list = ['VIC', 'VHM', 'VRE', 'VPL']
    df_company['Nhom'] = df_company.apply(lambda row: 'VINGROUP' if row['Ticker'] in vingroup_list else row['Ngành Cấp 2'], axis=1)

    results = []
    for nhom, group in df_company.groupby('Nhom'):
        symbols = group['Ticker'].unique()
        group_data = market_df[market_df['symbol'].isin(symbols)]
        latest_60 = group_data.groupby('symbol').tail(60)
        last_session = latest_60.groupby('symbol').tail(1)
        clean_data = last_session[last_session['volume'] > 0]
        if not clean_data.empty:
            results.append({'name': nhom, 'percent_change': clean_data['pctChange'].mean(), 'volume_ratio': clean_data['volume'].mean()/100000})

    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)
    
    # 2. Vẽ biểu đồ Diễn biến thị trường (Chart 1)
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig1 = io_go.Figure()
    fig1.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors))
    fig1.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='yellow', width=2)))
    fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), margin=dict(l=20, r=20, t=30, b=50), height=400)
    
    # 3. Vẽ biểu đồ Lãi suất (Chart 2 - Bạn có thể thay đổi logic ở đây)
    fig2 = fig1 
    
    # Chuyển đổi biểu đồ thành HTML để nhúng
    chart_html1 = fig1.to_html(full_html=False, include_plotlyjs='cdn')
    chart_html2 = fig2.to_html(full_html=False, include_plotlyjs='cdn')

    # 4. Đọc file template và thay thế
    try:
        with open("template.html", "r", encoding="utf-8") as f:
            template = f.read()

        final_html = template.replace("{{CHART_DIEN_BIEN}}", chart_html1)
        final_html = final_html.replace("{{CHART_LAI_SUAT}}", chart_html2)

        # 5. Ghi kết quả ra index.html
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(final_html)
        print("Đã tạo thành công index.html từ template!")
    except Exception as e:
        print(f"Lỗi khi tạo file: {e}")

if __name__ == "__main__":
    main()
