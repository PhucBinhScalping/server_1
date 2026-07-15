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
        df.rename(columns={'nmVolume': 'klgd_khop_lenh', 'ptVolume': 'klgd_thoa_thuan', 'pctChange': '+/-%', 'close': 'close'}, inplace=True)
        df['volume'] = df['klgd_khop_lenh'].fillna(0) + df['klgd_thoa_thuan'].fillna(0)
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        
        last = df.iloc[-1]
        
        # Chỉ số
        gia_close = float(last['close'])
        BD_gia = float(last['+/-%'])
        
        # Trung bình 21 phiên
        KLTB21 = df['volume'].tail(21).mean()
        volume_ratio = float(last['volume']) / KLTB21 if KLTB21 > 0 else 0
        
        return [0, 0, BD_gia, volume_ratio, 0, 0, 0, 0, 0, 0, 0] # Trả về list đúng định dạng
    except: return None

def main():
    df = pd.read_excel(FILE_DANH_SACH)
    # Tách Vingroup
    df.loc[df['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    nganh_list = df['Ngành Cấp 2'].unique()
    
    for nganh in nganh_list:
        if pd.isna(nganh): continue
        tickers = df[df['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        # Chạy song song 15 luồng để lấy dữ liệu ngành
        with ThreadPoolExecutor(max_workers=15) as executor:
            data_nganh = list(executor.map(tinh_du_lieu_cp, tickers))
            
        data_nganh = [x for x in data_nganh if x is not None]
        
        if data_nganh:
            avg = np.mean(data_nganh, axis=0)
            results.append({'name': nganh, 'percent_change': avg[2], 'volume_ratio': avg[3]})

    df_final = pd.DataFrame(results)
    
    # Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='BĐ giá', marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='KL/TBKL21', yaxis='y2', line=dict(color='yellow', width=3)))
    
    fig.update_layout(paper_bgcolor='#333', font=dict(color='white'), yaxis2=dict(overlaying='y', side='right'))
    
    # Xuất ra file
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', chart_html)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Hoàn thành!")

if __name__ == "__main__":
    main()
