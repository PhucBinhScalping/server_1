import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime, timedelta

# Cấu hình
head = {"User-Agent": "Mozilla/5.0"} # Có thể thay bằng user_agent thật của bạn
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

def tinh_du_lieu_cp(symbol, ngay_moi_nhat, day_end, df_old):
    # 1. Đảm bảo dữ liệu cũ đúng định dạng
    df_old['date'] = pd.to_datetime(df_old['date'], format='mixed', dayfirst=True)
    
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_moi_nhat}~date:lte:{day_end}&size=100000&page=1'
    try:
        r = requests.get(url, headers=head, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df_new = pd.DataFrame(data)
        df_new.rename(columns={'code':'symbol', 'nmVolume': 'klgd_khop_lenh', 'nmValue': 'gtgd_khop_lenh', 
                               'ptVolume': 'klgd_thoa_thuan', 'ptValue': 'gtgd_thoa_thuan', 
                               'change': '+/-', 'pctChange': '+/-%'}, inplace=True)
        
        df_new['volume'] = df_new['klgd_khop_lenh'].fillna(0) + df_new['klgd_thoa_thuan'].fillna(0)
        df_new['date'] = pd.to_datetime(df_new['date'], format='mixed', dayfirst=True)
        
        # Gộp và xử lý
        df_combined = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=['date', 'close', 'volume'], keep='first')
        df_combined = df_combined.sort_values(by='date').reset_index(drop=True)
        
        last_row = df_combined.iloc[-1]
        
        # Tính toán các chỉ số
        gia_close = float(last_row['close'])
        KL1000 = float(last_row['volume']) / 1000
        BD_gia = float(last_row['+/-%'])
        
        # Trung bình khối lượng 21 phiên
        KLGD_KLTB21_mean = df_combined['volume'].tail(21).mean()
        KLTB_KLTB21 = float(last_row['volume']) / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0
        
        # Trung bình giá 5/21 phiên
        close_mean_5 = df_combined['close'].tail(5).mean()
        close_mean_21 = df_combined['close'].tail(21).mean()
        gia_tbgia5 = close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0
        
        # Khối lượng 5 phiên
        KL_KLTB5_mean = df_combined['volume'].tail(5).mean()
        KL_KLTB5 = float(last_row['volume']) / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0
        
        # Đỉnh đáy 60 ngày
        data_60 = df_combined.tail(60)
        day2t, dinh2t = data_60['close'].min(), data_60['close'].max()
        dinh_day = (dinh2t - day2t) / day2t if day2t > 0 else 0
        giam_sdinh = (gia_close - dinh2t) / dinh2t if dinh2t != 0 else 0
        tang_sday = (gia_close - day2t) / day2t if day2t != 0 else 0
        
        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, day2t, dinh2t, tang_sday, giam_sdinh]
    except: return None

def main():
    df = pd.read_excel(FILE_DANH_SACH)
    
    # 1. Tách Vingroup
    vingroup = ['VIC', 'VRE', 'VHM', 'VPL']
    df.loc[df['Ticker'].isin(vingroup), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    nganh_list = df['Ngành Cấp 2'].unique()
    
    for nganh in nganh_list:
        tickers = df[df['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        data_nganh = []
        
        for ma in tickers:
            # Giả định: bạn có hàm load_database_old(ma) để lấy data cũ
            # Nếu chưa có, bạn cần nạp dữ liệu lịch sử vào đây
            df_old = pd.DataFrame({'date': [], 'close': [], 'volume': []}) # Thay thế bằng logic load file của bạn
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

    fig.update_layout(title=f"Biểu đồ biến động giá các ngành - {datetime.now().strftime('%d-%m-%Y %H:%M')}",
                      paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
                      yaxis=dict(title='BĐ giá', gridcolor='#555'),
                      yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right', gridcolor='#555'),
                      xaxis=dict(tickangle=-45))
    
    fig.show()

if __name__ == "__main__":
    main()
