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
MA_VINGROUP = ["VIC", "VRE", "VHM", "VPL"]

def get_data_for_symbol(symbol):
    """Lấy dữ liệu cho 1 mã cụ thể từ VNDIRECT"""
    fdate = (datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d')
    url = f"https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{fdate}&size=1000&page=1"
    
    try:
        r = requests.get(url, headers=head, timeout=20)
        if r.status_code == 200:
            data = r.json().get('data', [])
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        print(f"Lỗi tải mã {symbol}: {e}")
    return pd.DataFrame()

def main():
    if not os.path.exists(FILE_DANH_SACH):
        print(f"LỖI: Không tìm thấy file {FILE_DANH_SACH}")
        return
        
    df_company = pd.read_excel(FILE_DANH_SACH)
    
    # --- PHÂN NHÓM DỮ LIỆU ---
    nhom_danh_sach = {"VINGROUP": []}
    
    for _, row in df_company.iterrows():
        ticker = str(row['Ticker']).strip().upper()
        nganh = str(row['Ngành Cấp 2']).strip()
        
        if ticker in MA_VINGROUP:
            nhom_danh_sach["VINGROUP"].append(ticker)
        else:
            if nganh not in nhom_danh_sach:
                nhom_danh_sach[nganh] = []
            nhom_danh_sach[nganh].append(ticker)

    # --- TÍNH TOÁN ---
    results = []
    print("Đang bắt đầu tải và tính toán dữ liệu...")
    
    for group_name, tickers in nhom_danh_sach.items():
        if not tickers: continue
        
        pct_list = []
        vol_list = []
        
        for symbol in tickers:
            df_symbol = get_data_for_symbol(symbol)
            if not df_symbol.empty:
                latest = df_symbol.iloc[-1]
                pct_list.append(pd.to_numeric(latest.get('pctChange', 0), errors='coerce'))
                vol_list.append(pd.to_numeric(latest.get('nmVolume', 0), errors='coerce'))
            
            time.sleep(0.2) # Nghỉ để tránh bị chặn
            
        if pct_list:
            results.append({
                'name': group_name,
                'percent_change': sum(pct_list) / len(pct_list),
                'volume_ratio': (sum(vol_list) / len(vol_list)) / 100000
            })

    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)

    # --- VẼ BIỂU ĐỒ ---
    fig = io_go.Figure()
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], 
                            name='Biến động (%)', marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], 
                                name='Thanh khoản', yaxis='y2', 
                                line=dict(color='#ffc107', width=3)))

    fig.update_layout(
        title=dict(text="Phân tích diễn biến các ngành & Vingroup", font=dict(color="#ffffff")),
        paper_bgcolor='#212529', plot_bgcolor='#2b3035',
        yaxis=dict(title=dict(text="Biến động (%)", font=dict(color="#ffffff")), tickfont=dict(color="#ffffff")),
        yaxis2=dict(title=dict(text="Thanh khoản (x100k)", font=dict(color="#ffffff")), tickfont=dict(color="#ffffff"), overlaying='y', side='right'),
        legend=dict(font=dict(color="#ffffff")),
        margin=dict(b=100)
    )

    # --- XUẤT FILE ---
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(pio.to_html(fig, full_html=True))
    
    print("ĐÃ XONG! Mở file 'index.html' trong thư mục để xem biểu đồ.")

if __name__ == "__main__":
    main()
