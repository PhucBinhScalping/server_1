import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
from user_agent import random_user

# 1. Cấu hình
head = {"User-Agent": random_user()}

def get_market_data():
    """Tải 60-90 phiên gần nhất cho toàn bộ thị trường để tính toán"""
    # Lấy dữ liệu 90 ngày để đảm bảo có đủ 60 phiên giao dịch (trừ thứ 7, CN)
    fdate = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    url = f"https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=50000"
    try:
        r = requests.get(url, headers=head, timeout=60)
        df = pd.DataFrame(r.json().get('data', []))
        df['date'] = pd.to_datetime(df['date'])
        # Đổi tên cột cho khớp logic
        df.rename(columns={'code': 'symbol', 'nmVolume': 'volume', 'pctChange': 'pctChange'}, inplace=True)
        return df
    except:
        return pd.DataFrame()

def main():
    # 2. Tải dữ liệu toàn thị trường
    market_df = get_market_data()
    if market_df.empty: return
    
    df_company = pd.read_excel("danh_sach_cong_ty.xlsx")
    
    # 3. Tách nhóm Vingroup trong code
    vingroup = ['VIC', 'VHM', 'VRE', 'VPL']
    df_company['Nhom_Hien_Thi'] = df_company.apply(
        lambda row: 'VINGROUP' if row['Ticker'] in vingroup else row['Ngành Cấp 2'], axis=1
    )

    results = []
    for nhom, group in df_company.groupby('Nhom_Hien_Thi'):
        symbols = group['Ticker'].unique()
        # Lọc dữ liệu của các mã trong nhóm
        group_data = market_df[market_df['symbol'].isin(symbols)]
        
        # Chỉ lấy 60 phiên gần nhất cho mỗi mã
        latest_60 = group_data.groupby('symbol').tail(60)
        
        # Lấy dữ liệu của phiên mới nhất (hàng cuối cùng của từng mã)
        last_session = latest_60.groupby('symbol').tail(1)
        
        # Lọc bỏ các mã không có thanh khoản (volume <= 0) để tránh làm sai màu ngành
        clean_data = last_session[last_session['volume'] > 0]
        
        if not clean_data.empty:
            avg_pct = clean_data['pctChange'].mean()
            # Tính trung bình volume (chia 100k để làm tròn đơn vị)
            avg_vol = clean_data['volume'].mean() / 100000
            results.append({'name': nhom, 'percent_change': avg_pct, 'volume_ratio': avg_vol})

    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)
    
    # 4. Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    # Cột biến động
    fig.add_trace(io_go.Bar(
        x=df_final['name'], y=df_final['percent_change'], name='BĐ giá',
        marker_color=colors, text=[f'{x:.2f}%' for x in df_final['percent_change']], textposition='auto'
    ))
    # Đường thanh khoản
    fig.add_trace(io_go.Scatter(
        x=df_final['name'], y=df_final['volume_ratio'], name='KL/TBKL21',
        yaxis='y2', line=dict(color='red', width=2), mode='lines+markers'
    ))

    fig.update_layout(
        title=f"Biểu đồ biến động giá các ngành - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        paper_bgcolor='#333', plot_bgcolor='#333', font=dict(color='white'),
        yaxis=dict(title='BĐ giá', gridcolor='#555'),
        yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right', gridcolor='#555'),
        xaxis=dict(tickangle=-45)
    )
    
    fig.write_html("index.html")
    print("Đã tạo file index.html thành công!")

if __name__ == "__main__":
    main()
