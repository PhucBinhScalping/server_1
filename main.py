import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor

# Cấu hình
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"
TEMPLATE_FILE = "template.html"
OUTPUT_FILE = "index.html"
HEAD = {"User-Agent": "Mozilla/5.0"}
session = requests.Session()

def tinh_du_lieu_cp(symbol):
    """Lấy dữ liệu trực tiếp từ API cho 1 mã cổ phiếu"""
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    day_now = datetime.now(vn_tz).strftime("%Y-%m-%d")
    ngay_start = (datetime.now(vn_tz) - timedelta(days=60)).strftime("%Y-%m-%d")
    
    # API lấy giá cổ phiếu
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}&size=100&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=True)
        
        # Chỉ lấy dữ liệu ngày mới nhất để tính toán
        df_today = df[df['date'].dt.strftime("%Y-%m-%d") == day_now]
        if df_today.empty: return None
        
        last = df_today.iloc[-1]
        
        # Tính TB 21 phiên trên toàn bộ dữ liệu
        df['volume'] = df['nmVolume'].fillna(0) + df['ptVolume'].fillna(0)
        KLTB21 = df['volume'].tail(21).mean()
        
        volume_ratio = float(last['volume']) / KLTB21 if KLTB21 > 0 else 0
        
        return [float(last['pctChange']), volume_ratio]
    except:
        return None

def main():
    # 1. Đọc file Excel
    df_config = pd.read_excel(FILE_DANH_SACH)
    # Gom nhóm Vingroup
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    
    # 2. Xử lý từng ngành
    for nganh in df_config['Ngành Cấp 2'].unique():
        if pd.isna(nganh): continue
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        # Gọi API đa luồng để nhanh hơn
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            avg = np.mean(data_nganh, axis=0)
            results.append({'name': nganh, 'percent_change': avg[0], 'volume_ratio': avg[1]})

    df_final = pd.DataFrame(results)
    
    # 3. Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    
    fig.add_trace(io_go.Bar(
        x=df_final['name'], y=df_final['percent_change'], 
        marker_color=colors, text=[f'{x:.2f}%' for x in df_final['percent_change']]
    ))
    
    fig.add_trace(io_go.Scatter(
        x=df_final['name'], y=df_final['volume_ratio'], 
        yaxis='y2', line=dict(color='#FFD700', width=3), mode='lines+markers'
    ))
    
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    fig.update_layout(
        title=f"Biểu đồ biến động giá các ngành - {datetime.now(vn_tz).strftime('%d-%m-%Y %H:%M')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        width=1100, height=600, yaxis=dict(title='BĐ giá (%)'),
        yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right'),
        xaxis=dict(tickangle=-45)
    )
    
    # 4. Ghi file
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', chart_html)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Đã cập nhật biểu đồ thành công!")

if __name__ == "__main__":
    main()
