import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
from user_agent import random_user

# Cấu hình
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
    
    # Tạo biểu đồ Plotly
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='yellow', width=2)))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
        yaxis=dict(gridcolor='#555'), yaxis2=dict(overlaying='y', side='right', gridcolor='#555'),
        margin=dict(l=20, r=20, t=30, b=50), height=400
    )

    # Chuyển biểu đồ thành mã HTML để nhúng
    plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # Dùng cấu trúc HTML bạn đã cung cấp, thay phần <img> bằng biến plot_html
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Diễn Biến Thị Trường</title>
        <style>
            body {{ background: linear-gradient(to right, #f9c851, #f15238); font-family: sans-serif; margin: 0; padding: 0; }}
            .navbar {{ background: #002060; padding: 15px; color: white; text-align: center; font-weight: bold; }}
            .container {{ max-width: 1000px; margin: 20px auto; background: rgba(255, 255, 255, 0.2); padding: 20px; border-radius: 20px; }}
            .market-update-box {{ background: #333; padding: 10px; border-radius: 15px; }}
        </style>
    </head>
    <body>
        <div class="navbar">PHÚC BÌNH SCALPING - DIỄN BIẾN THỊ TRƯỜNG</div>
        <div class="container">
            <h2 style="color: white; text-align: center;">Cập nhật lúc: {datetime.now().strftime('%d/%m/%Y %H:%M')}</h2>
            <div class="market-update-box">
                {plot_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)

if __name__ == "__main__":
    main()
