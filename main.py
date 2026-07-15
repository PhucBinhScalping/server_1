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
    """Chỉ tính toán đúng 2 chỉ số: BD_gia và KLTB_KLTB21"""
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    day_end = datetime.now(vn_tz).strftime("%Y-%m-%d")
    ngay_start = (datetime.now(vn_tz) - timedelta(days=90)).strftime("%Y-%m-%d")
    
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}~date:lte:{day_end}&size=100&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        # Tính khối lượng
        df['volume'] = df['nmVolume'].fillna(0) + df['ptVolume'].fillna(0)
        
        # Lấy giá trị phiên mới nhất
        last = df.iloc[-1]
        
        # Chỉ số 1: Biến động giá (%)
        bd_gia = float(last.get('pctChange', 0))
        
        # Chỉ số 2: Khối lượng / TB 21 phiên
        KLTB21_mean = df['volume'].tail(21).mean()
        kl_tb21 = float(last['volume']) / KLTB21_mean if KLTB21_mean > 0 else 0
        
        return [bd_gia, kl_tb21]
        
    except Exception:
        return None

def main():
    # 1. Đọc danh sách và xử lý Ticker
    df_config = pd.read_excel(FILE_DANH_SACH)
    # Đảm bảo Ticker là dạng chuỗi sạch sẽ
    df_config['Ticker'] = df_config['Ticker'].astype(str).str.strip()
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    
    # 2. Xử lý theo ngành
    for nganh in df_config['Ngành Cấp 2'].unique():
        if pd.isna(nganh): continue
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            # Lấy trung bình ngành cho 2 chỉ số này
            avg = np.mean(data_nganh, axis=0)
            results.append({'name': nganh, 'percent_change': avg[0], 'volume_ratio': avg[1]})

    df_final = pd.DataFrame(results)
    
    # 3. Vẽ biểu đồ tinh gọn
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    # Bar chart Biến động giá
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='BĐ giá', marker_color=colors))
    # Line chart KL/TBKL21
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='KL/TBKL21', yaxis='y2', line=dict(color='#FFD700', width=3), mode='lines+markers'))
    
    fig.update_layout(
        title=f"Biến động giá & Khối lượng ngành - {datetime.now().strftime('%d-%m-%Y')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        yaxis=dict(title='BĐ giá (%)', gridcolor='#555'),
        yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right', showgrid=False),
        xaxis=dict(tickangle=-45, gridcolor='#555'),
        margin=dict(l=60, r=60, t=80, b=150)
    )
    
    # 4. Lưu file
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', chart_html)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Cập nhật biểu đồ thành công với 2 chỉ số!")

if __name__ == "__main__":
    main()
