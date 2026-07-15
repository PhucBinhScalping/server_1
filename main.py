import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Cấu hình
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"
TEMPLATE_FILE = "template.html"
OUTPUT_FILE = "index.html"
HEAD = {"User-Agent": "Mozilla/5.0"}
session = requests.Session()

def tinh_du_lieu_cp(symbol):
    day_end = datetime.now().strftime("%Y-%m-%d")
    ngay_start = (datetime.now() - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}~date:lte:{day_end}&size=500&page=1'
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        df = pd.DataFrame(data)
        df['volume'] = df['nmVolume'].fillna(0) + df['ptVolume'].fillna(0)
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        last = df.iloc[-1]
        KLTB21 = df['volume'].tail(21).mean()
        return [0, 0, float(last['pctChange']), float(last['volume']) / KLTB21 if KLTB21 > 0 else 0]
    except: return None

def main():
    df = pd.read_excel(FILE_DANH_SACH)
    df.loc[df['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    results = []
    
    for nganh in df['Ngành Cấp 2'].unique():
        if pd.isna(nganh): continue
        tickers = df[df['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        with ThreadPoolExecutor(max_workers=15) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        if data_nganh:
            avg = np.mean(data_nganh, axis=0)
            results.append({'name': nganh, 'percent_change': avg[2], 'volume_ratio': avg[3]})

    df_final = pd.DataFrame(results)
    
    # Vẽ biểu đồ tối ưu kích thước
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    
    # Cột biến động giá
    fig.add_trace(io_go.Bar(
        x=df_final['name'], 
        y=df_final['percent_change'], 
        name='BĐ giá', 
        marker_color=colors, 
        text=[f'{x:.2f}%' for x in df_final['percent_change']]
    ))
    
    # Đường khối lượng (Thay đổi màu tại đây)
    fig.add_trace(io_go.Scatter(
        x=df_final['name'], 
        y=df_final['volume_ratio'], 
        name='KL/TBKL21', 
        yaxis='y2', 
        line=dict(color='#FFD700', width=3), # #FFD700 là màu vàng Gold, width=3 giúp đường đậm hơn
        mode='lines+markers'
    ))
    
    fig.update_layout(
        title=f"Biểu đồ biến động giá các ngành - {datetime.now().strftime('%d-%m-%Y %H:%M')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white', size=14),
        width=1100, height=600, margin=dict(l=50, r=50, t=80, b=150),
        bargap=0.2, yaxis=dict(title='BĐ giá (%)', gridcolor='#555'),
        yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right', gridcolor='#555'),
        xaxis=dict(tickangle=-45)
    )
    
    
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', chart_html)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    main()
