import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime

# --- CẤU HÌNH ---
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"
TEMPLATE_FILE = "template.html"
OUTPUT_FILE = "index.html"
HEAD = {"User-Agent": "Mozilla/5.0"}

def tinh_du_lieu_cp(symbol, ngay_moi_nhat, day_end, df_old):
    # Logic tính toán chi tiết của bạn
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_moi_nhat}~date:lte:{day_end}&size=100000&page=1'
    try:
        r = requests.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df_new = pd.DataFrame(data)
        # Rename các cột theo logic của bạn
        df_new.rename(columns={'code':'symbol', 'nmVolume': 'klgd_khop_lenh', 'nmValue': 'gtgd_khop_lenh',
                               'ptVolume': 'klgd_thoa_thuan', 'ptValue': 'gtgd_thoa_thuan',
                               'change': '+/-', 'pctChange': '+/-%'}, inplace=True)
        
        df_new['volume'] = df_new['klgd_khop_lenh'].fillna(0) + df_new['klgd_thoa_thuan'].fillna(0)
        df_new['date'] = pd.to_datetime(df_new['date'], format='mixed', dayfirst=True)
        
        # Gộp dữ liệu
        df_old['date'] = pd.to_datetime(df_old['date'], format='mixed', dayfirst=True)
        df_combined = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=['date', 'close', 'volume'], keep='first')
        df_combined = df_combined.sort_values(by='date').reset_index(drop=True)
        
        last_row = df_combined.iloc[-1]
        
        # Các chỉ số tính toán
        gia_close = float(last_row['close'])
        KL1000 = float(last_row['volume']) / 1000
        BD_gia = float(last_row['+/-%'])
        
        # Trung bình 21 phiên
        KLTB21 = df_combined['volume'].tail(21).mean()
        KLTB_KLTB21 = float(last_row['volume']) / KLTB21 if KLTB21 > 0 else 0
        
        # Trung bình giá 5/21
        gia_tbgia5 = df_combined['close'].tail(5).mean() / df_combined['close'].tail(21).mean()
        
        # Khối lượng 5 phiên
        KL_KLTB5 = float(last_row['volume']) / df_combined['volume'].tail(5).mean()
        
        # Đỉnh đáy 60 ngày
        dinh_day = (df_combined.tail(60)['close'].max() - df_combined.tail(60)['close'].min()) / df_combined.tail(60)['close'].min()
        
        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, 0, 0, 0, 0]
    except: return None

def main():
    df = pd.read_excel(FILE_DANH_SACH)
    
    # 1. Tách nhóm Vingroup
    df.loc[df['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    for nganh in df['Ngành Cấp 2'].unique():
        if pd.isna(nganh): continue
        tickers = df[df['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        data_nganh = []
        
        for ma in tickers:
            # Lưu ý: Cần có dữ liệu cũ df_old. Ở đây tạo tạm DataFrame trống
            df_old = pd.DataFrame(columns=['date', 'close', 'volume'])
            res = tinh_du_lieu_cp(ma, "2026-01-01", datetime.now().strftime("%Y-%m-%d"), df_old)
            if res: data_nganh.append(res)
        
        if data_nganh:
            avg_res = np.mean(data_nganh, axis=0)
            results.append({'name': nganh, 'percent_change': avg_res[2], 'volume_ratio': avg_res[3]})

    df_final = pd.DataFrame(results)
    
    # 2. Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='BĐ giá', 
                            marker_color=colors, text=[f'{x:.2f}%' for x in df_final['percent_change']], textposition='auto'))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='KL/TBKL21', 
                                yaxis='y2', line=dict(color='red', width=2), mode='lines+markers'))
    
    fig.update_layout(paper_bgcolor='#333', font=dict(color='white'), yaxis2=dict(overlaying='y', side='right'))
    
    # 3. Chèn vào Template
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(template.replace('{{CHART_DIEN_BIEN}}', chart_html))
    
    print("Cập nhật website thành công!")

if __name__ == "__main__":
    main()
