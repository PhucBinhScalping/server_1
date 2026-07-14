import pandas as pd
import requests
import time
import os
import plotly.graph_objects as io_go
import plotly.io as pio
from datetime import datetime, timedelta
from user_agent import random_user

# --- CẤU HÌNH ---
head = {"User-Agent": random_user()}
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"
DATA_FOLDER = "Database2026" # Đảm bảo thư mục này nằm cùng cấp với file main.py
MA_VINGROUP = ["VIC", "VRE", "VHM", "VPL"]

def fetch_and_calculate(symbol):
    """Hàm lấy dữ liệu và tính toán tuần tự để đảm bảo an toàn IP"""
    file_path = os.path.join(DATA_FOLDER, f"{symbol}.csv")
    if not os.path.exists(file_path): 
        print(f"Cảnh báo: Không tìm thấy file {file_path}")
        return None
    
    try:
        df_old = pd.read_csv(file_path)
        day_end = datetime.now().strftime("%Y-%m-%d")
        ngay_moi_nhat = pd.to_datetime(df_old['date'].iloc[-1]).strftime("%Y-%m-%d")
        
        url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_moi_nhat}~date:lte:{day_end}&size=1000&page=1'
        r = requests.get(url, headers=head, timeout=20)
        
        if r.status_code != 200: return None
        json_data = r.json()
        if 'data' not in json_data or not json_data['data']: return None
        
        df_new = pd.DataFrame(json_data['data'])
        df_new.rename(columns={'nmVolume': 'klgd_khop_lenh', 'ptVolume': 'klgd_thoa_thuan', 'pctChange': '+/-%'}, inplace=True)
        df_new['volume'] = df_new['klgd_khop_lenh'] + df_new['klgd_thoa_thuan']
        
        df_combined = pd.concat([df_old, df_new]).drop_duplicates(subset=['date', 'close', 'volume'], keep='first')
        last = df_combined.sort_values(by='date').iloc[-1]
        
        return {
            'pct': float(last['+/-%']),
            'vol': float(last['volume']) / df_combined['volume'].tail(21).mean()
        }
    except Exception as e:
        print(f"Lỗi xử lý {symbol}: {e}")
        return None

def main():
    if not os.path.exists(FILE_DANH_SACH):
        print(f"LỖI: Không tìm thấy file {FILE_DANH_SACH}")
        return
        
    df_company = pd.read_excel(FILE_DANH_SACH)
    
    # --- PHÂN NHÓM ---
    nhom_danh_sach = {"VINGROUP": []}
    for _, row in df_company.iterrows():
        t = str(row['Ticker']).strip().upper()
        n = str(row['Ngành Cấp 2']).strip()
        if t in MA_VINGROUP: nhom_danh_sach["VINGROUP"].append(t)
        else: nhom_danh_sach.setdefault(n, []).append(t)

    # --- TÍNH TOÁN TUẦN TỰ (AN TOÀN CHO GITHUB) ---
    results = []
    print("Đang xử lý dữ liệu...")
    
    for group_name, tickers in nhom_danh_sach.items():
        pct_vals, vol_vals = [], []
        for symbol in tickers:
            res = fetch_and_calculate(symbol)
            if res:
                pct_vals.append(res['pct'])
                vol_vals.append(res['vol'])
            time.sleep(0.5) # Dừng 0.5s để bảo vệ IP GitHub
            
        if pct_vals:
            results.append({
                'name': group_name,
                'percent_change': pd.Series(pct_vals).mean(),
                'volume_ratio': pd.Series(vol_vals).mean()
            })

    # --- VẼ BIỂU ĐỒ ---
    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)
    fig = io_go.Figure()
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='Biến động (%)', marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='Thanh khoản', yaxis='y2', line=dict(color='#ffc107', width=3)))

    fig.update_layout(
        title="Phân tích diễn biến các ngành & Vingroup",
        paper_bgcolor='#212529', plot_bgcolor='#2b3035',
        font=dict(color="#ffffff"),
        yaxis=dict(title="Biến động (%)"),
        yaxis2=dict(title="Thanh khoản (x100k)", overlaying='y', side='right')
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(pio.to_html(fig, full_html=True))
    
    print("ĐÃ XONG! Mở file 'index.html' để xem kết quả.")

if __name__ == "__main__":
    main()
