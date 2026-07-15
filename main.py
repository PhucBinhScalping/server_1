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

# ĐỊNH NGHĨA MÃ ĐẠI DIỆN CHO CÁC NGÀNH (Để con số khớp bảng giá)
# Nếu không có trong dict này, nó sẽ dùng trung vị (median)
MA_DAI_DIEN = {
    'Vingroup': 'VIC',
    'NGÂN HÀNG': 'VCB',
    'BẤT ĐỘNG SẢN': 'VHM'
}

def tinh_du_lieu_cp(symbol):
    # Sử dụng ngày cụ thể để ép API trả về dữ liệu đúng ngày hôm nay
    today = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%Y-%m-%d")
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{today}&size=10&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        # Ép kiểu dữ liệu an toàn ngay từ đầu
        df['pctChange'] = pd.to_numeric(df['pctChange'], errors='coerce')
        df['nmVolume'] = pd.to_numeric(df['nmVolume'], errors='coerce').fillna(0)
        df['ptVolume'] = pd.to_numeric(df['ptVolume'], errors='coerce').fillna(0)
        
        # Chỉ lấy dữ liệu của ngày hôm nay
        last_row = df[df['date'] == today].iloc[-1]
        
        return {
            'symbol': symbol,
            'bd_gia': last_row['pctChange'],
            'volume': last_row['nmVolume'] + last_row['ptVolume']
        }
    except: return None

def main():
    df_config = pd.read_excel(FILE_DANH_SACH)
    df_config['Ticker'] = df_config['Ticker'].astype(str).str.strip()
    
    results = []
    for nganh in df_config['Ngành Cấp 2'].unique():
        if pd.isna(nganh): continue
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            raw_data = list(executor.map(tinh_du_lieu_cp, tickers))
            data_nganh = [x for x in raw_data if x is not None]
        
        if data_nganh:
            df_nganh = pd.DataFrame(data_nganh)
            
            # LOGIC ĐÚNG: Nếu có mã đại diện, lấy mã đó, không thì lấy trung vị
            if nganh in MA_DAI_DIEN:
                target_symbol = MA_DAI_DIEN[nganh]
                row = df_nganh[df_nganh['symbol'] == target_symbol]
                final_bd = row['bd_gia'].iloc[0] if not row.empty else df_nganh['bd_gia'].median()
            else:
                final_bd = df_nganh['bd_gia'].median()
            
            final_kl = df_nganh['kl_tb21'].mean()
            results.append({'name': nganh, 'percent_change': final_bd, 'volume_ratio': final_kl})

    df_final = pd.DataFrame(results)
    
    # Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors, texttemplate='%{y:.2f}%', textposition='auto'))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='#FFD700', width=3)))
    
    fig.update_layout(
        title=f"Biểu đồ biến động giá ngành - {datetime.now().strftime('%d-%m-%Y')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        yaxis=dict(title='BĐ giá (%)'), yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right'),
        margin=dict(l=60, r=60, t=80, b=150)
    )
    
    # Ghi file
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', fig.to_html(full_html=False, include_plotlyjs='cdn'))
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Đã update thành công!")

if __name__ == "__main__":
    main()
