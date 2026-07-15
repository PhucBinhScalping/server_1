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
    # Lấy dữ liệu 120 phiên (đủ cho 100 phiên giao dịch + dự phòng)
    ngay_start = (datetime.now(vn_tz) - timedelta(days=150)).strftime("%Y-%m-%d")
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}&size=120&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if len(data) < 20: return None # Không đủ dữ liệu
        
        df = pd.DataFrame(data)
        df['pctChange'] = pd.to_numeric(df['pctChange'], errors='coerce')
        df['volume'] = pd.to_numeric(df['nmVolume'], errors='coerce').fillna(0) + \
                       pd.to_numeric(df['ptVolume'], errors='coerce').fillna(0)
        
        # --- LỌC THANH KHOẢN (ĐIỀU KIỆN MỚI) ---
        volume_tb100 = df['volume'].tail(100).mean()
        if volume_tb100 <= 10000:
            print(f"DEBUG: {symbol} bị loại (Volume TB100: {volume_tb100:,.0f})")
            return None
        # ---------------------------------------
        
        last = df.iloc[-1]
        bd_gia = last['pctChange']
        
        # Tính KL/TB21
        vol_mean_21 = df['volume'].tail(21).mean()
        kl_tb21 = (last['volume'] / vol_mean_21) if vol_mean_21 > 0 else 0
        
        print(f"DEBUG: {symbol} | OK (Volume TB100: {volume_tb100:,.0f}) | BĐ giá: {bd_gia}%")
        return {'bd_gia': bd_gia, 'kl_tb21': kl_tb21}
    except Exception as e:
        print(f"Lỗi {symbol}: {e}")
        return None

def main():
    df_config = pd.read_excel(FILE_DANH_SACH)
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    ds_nganh = df_config['Ngành Cấp 2'].dropna().unique()
    
    for nganh in ds_nganh:
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        # Chạy lọc thanh khoản song song
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            df_nganh = pd.DataFrame(data_nganh)
            
            # Tính trung bình cộng (đã lọc các mã thanh khoản thấp ở bước trước)
            final_bd = df_nganh['bd_gia'].mean()
            final_kl = df_nganh['kl_tb21'].mean()
            
            results.append({'name': nganh, 'percent_change': final_bd, 'volume_ratio': final_kl})

    # [PHẦN VẼ BIỂU ĐỒ GIỮ NGUYÊN]
    if not results:
        print("Không còn cổ phiếu nào thỏa mãn điều kiện.")
        return
        
    df_final = pd.DataFrame(results)
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors, texttemplate='%{y:.2f}%', textposition='outside'))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='#FFD700', width=3)))
    
    fig.update_layout(title="Biến động ngành (Lọc thanh khoản > 10,000)", 
                      paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
                      yaxis=dict(title='BĐ giá (%)'), yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right'))
    
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', fig.to_html(full_html=False, include_plotlyjs='cdn'))
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Cập nhật biểu đồ thành công!")

if __name__ == "__main__":
    main()
