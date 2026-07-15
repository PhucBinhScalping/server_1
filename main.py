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
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    # Lấy dữ liệu 50 phiên gần nhất
    ngay_start = (datetime.now(vn_tz) - timedelta(days=70)).strftime("%Y-%m-%d")
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}&size=60&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        # Ép kiểu an toàn
        df['pctChange'] = pd.to_numeric(df['pctChange'], errors='coerce')
        df['nmVolume'] = pd.to_numeric(df['nmVolume'], errors='coerce').fillna(0)
        df['ptVolume'] = pd.to_numeric(df['ptVolume'], errors='coerce').fillna(0)
        df['volume'] = df['nmVolume'] + df['ptVolume']
        
        last = df.iloc[-1]
        bd_gia = last['pctChange']
        
        # Tính KL/TB21
        vol_mean_21 = df['volume'].tail(21).mean()
        kl_tb21 = (last['volume'] / vol_mean_21) if vol_mean_21 > 0 else 0
        
        return {'bd_gia': bd_gia, 'kl_tb21': kl_tb21}
    except: return None

def main():
    df_config = pd.read_excel(FILE_DANH_SACH)
    # Gom nhóm Vingroup
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    for nganh in df_config['Ngành Cấp 2'].dropna().unique():
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        # Thay vì dùng .mean() hoặc .sum()/len() trực tiếp:
        if data_nganh:
            df_nganh = pd.DataFrame(data_nganh)
            
            # 1. Loại bỏ các giá trị lỗi hoặc giá trị 0 không đáng tin cậy
            df_clean = df_nganh[df_nganh['bd_gia'].abs() > 0.0001] 
            
            if not df_clean.empty:
                # 2. Tính thủ công theo ý bạn
                final_bd = df_clean['bd_gia'].sum() / len(df_clean)
                final_kl = df_clean['kl_tb21'].sum() / len(df_clean)
                
                results.append({
                    'name': nganh, 
                    'percent_change': final_bd, 
                    'volume_ratio': final_kl
                })

    df_final = pd.DataFrame(results)
    
    # Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors, name='BĐ giá'))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='#FFD700', width=3), name='KL/TBKL21'))
    
    fig.update_layout(
        title=f"Biến động giá ngành - {datetime.now().strftime('%d-%m-%Y')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        yaxis=dict(title='BĐ giá (%)'), yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right'),
        margin=dict(l=60, r=60, t=80, b=150)
    )
    
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', fig.to_html(full_html=False, include_plotlyjs='cdn'))
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Cập nhật thành công!")

if __name__ == "__main__":
    main()
