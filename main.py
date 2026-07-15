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
    """Lấy dữ liệu 90 ngày gần nhất từ API, không phụ thuộc file cũ"""
    # Tính ngày bắt đầu là 90 ngày trước
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    day_end = datetime.now(vn_tz).strftime("%Y-%m-%d")
    ngay_start = (datetime.now(vn_tz) - timedelta(days=90)).strftime("%Y-%m-%d")
    
    # URL lấy trọn vẹn 90 ngày
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}~date:lte:{day_end}&size=100&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        # Chuẩn hóa tên cột
        df.rename(columns={
            'code': 'symbol', 'nmVolume': 'klgd_khop_lenh', 'nmValue': 'gtgd_khop_lenh',
            'ptVolume': 'klgd_thoa_thuan', 'ptValue': 'gtgd_thoa_thuan',
            'change': '+/-', 'pctChange': '+/-%'
        }, inplace=True)
        
        df['date'] = pd.to_datetime(df['date'])
        df['volume'] = df['klgd_khop_lenh'].fillna(0) + df['klgd_thoa_thuan'].fillna(0)
        
        # Ép kiểu số
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Sắp xếp theo ngày tăng dần để tính trung bình trượt chuẩn
        df = df.sort_values(by='date').reset_index(drop=True)
        
        # --- TÍNH TOÁN CÁC CHỈ SỐ ---
        last_row = df.iloc[-1]
        
        gia_close = last_row['close']
        KL1000 = last_row['volume'] / 1000
        BD_gia = last_row['+/-%']
        
        # TB 21 phiên
        KLTB21_mean = df['volume'].tail(21).mean()
        KLTB_KLTB21 = last_row['volume'] / KLTB21_mean if KLTB21_mean > 0 else 0
        
        # TB giá 5/21
        close_mean_5 = df['close'].tail(5).mean()
        close_mean_21 = df['close'].tail(21).mean()
        gia_tbgia5 = close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0
        
        # TB KL 5 phiên
        KL_KLTB5_mean = df['volume'].tail(5).mean()
        KL_KLTB5 = last_row['volume'] / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0
        
        # Đỉnh đáy 60 phiên
        data_60 = df.tail(60)
        day2t = data_60['close'].min()
        dinh2t = data_60['close'].max()
        
        dinh_day = (dinh2t - day2t) / day2t if day2t > 0 else 0
        giam_sdinh = (gia_close - dinh2t) / dinh2t if dinh2t != 0 else 0
        tang_sday = (gia_close - day2t) / day2t if day2t != 0 else 0
        
        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, day2t, dinh2t, tang_sday, giam_sdinh]
        
    except Exception as e:
        print(f"Lỗi khi xử lý mã {symbol}: {e}")
        return None

def main():
    # 1. Đọc danh sách
    df_config = pd.read_excel(FILE_DANH_SACH)
    # Gom nhóm Vingroup
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    
    # 2. Xử lý theo ngành
    for nganh in df_config['Ngành Cấp 2'].unique():
        if pd.isna(nganh): continue
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            avg = np.mean(data_nganh, axis=0)
            results.append({'name': nganh, 'percent_change': avg[0], 'volume_ratio': avg[1]})

    df_final = pd.DataFrame(results)
    
    # 3. Vẽ biểu đồ với cấu hình ép kiểu dữ liệu
    df_final['percent_change'] = pd.to_numeric(df_final['percent_change'], errors='coerce').fillna(0)
    df_final['volume_ratio'] = pd.to_numeric(df_final['volume_ratio'], errors='coerce').fillna(1)
    
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], name='BĐ giá', marker_color=colors))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], name='KL/TBKL21', yaxis='y2', line=dict(color='#FFD700', width=3), mode='lines+markers'))
    
    fig.update_layout(
        title=f"Biểu đồ biến động giá các ngành - {datetime.now().strftime('%d-%m-%Y %H:%M')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        yaxis=dict(title='BĐ giá (%)', gridcolor='#555', zeroline=True, zerolinecolor='white'),
        yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right', showgrid=False),
        xaxis=dict(tickangle=-45, gridcolor='#555'),
        margin=dict(l=60, r=60, t=80, b=150)
    )
    
    # 4. Ghi file
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', chart_html)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Đã hoàn thành cập nhật biểu đồ!")

if __name__ == "__main__":
    main()
