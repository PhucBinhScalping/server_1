import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
from user_agent import random_user

# 1. Cấu hình
head = {"User-Agent": random_user()}
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

def tinh_du_lieu_cp(symbol, ngay_moi_nhat, day_end, df_old):
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_moi_nhat}~date:lte:{day_end}&size=100000&page=1'
    try:
        r = requests.get(url, headers=head, timeout=30)
        data = r.json().get('data', [])
        if not data: return None
        
        df_new = pd.DataFrame(data)
        df_new.rename(columns={'nmVolume': 'klgd_khop_lenh', 'ptVolume': 'klgd_thoa_thuan', 'pctChange': '+/-%'}, inplace=True)
        df_new['volume'] = df_new['klgd_khop_lenh'].fillna(0) + df_new['klgd_thoa_thuan'].fillna(0)
        
        last_row = df_new.iloc[-1]
        
        # Lấy giá trị số sạch
        BD_gia = pd.to_numeric(last_row.get('+/-%', 0), errors='coerce')
        KL_current = pd.to_numeric(last_row['volume'], errors='coerce')
        
        # Tính TB 21 phiên cũ (dựa trên df_old)
        KLTB21 = pd.to_numeric(df_old['volume'].tail(21).mean(), errors='coerce')
        ratio = KL_current / KLTB21 if KLTB21 > 0 else 0
        
        return BD_gia, ratio
    except:
        return None

def main():
    # Load danh sách và chạy qua các ngành
    df_company = pd.read_excel(FILE_DANH_SACH)
    results = []
    
    for nganh, group in df_company.groupby('Ngành Cấp 2'):
        symbols = group['Ticker'].unique()
        nganh_bd = []
        nganh_ratio = []
        
        for ma in symbols:
            # Giả định df_old load từ file hoặc bộ nhớ
            # Ở đây bạn cần thay hàm load_database_old bằng logic của bạn
            # Hoặc đơn giản hóa bằng cách dùng API lấy 30 ngày cho mã đó
            data_cp = tinh_du_lieu_cp(ma, (datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d"), pd.DataFrame({'volume': [1000]*21}))
            
            if data_cp:
                nganh_bd.append(data_cp[0])
                nganh_ratio.append(data_cp[1])
        
        if nganh_bd:
            # Loại bỏ giá trị lỗi (NaN) trước khi tính trung bình ngành
            bd_tb = np.nanmean(nganh_bd)
            ratio_tb = np.nanmean(nganh_ratio)
            results.append({'name': nganh, 'percent_change': bd_tb, 'volume_ratio': ratio_tb})

    df_final = pd.DataFrame(results)
    
    # Vẽ biểu đồ
    colors = ['#198754' if x >= 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    
    # Cột
    fig.add_trace(io_go.Bar(
        x=df_final['name'], y=df_final['percent_change'], name='BĐ giá',
        marker_color=colors, text=[f'{x:.2f}%' for x in df_final['percent_change']], textposition='auto'
    ))
    
    # Đường
    fig.add_trace(io_go.Scatter(
        x=df_final['name'], y=df_final['volume_ratio'], name='KL/TBKL21',
        yaxis='y2', line=dict(color='red', width=2), mode='lines+markers'
    ))

    fig.update_layout(
        title=f"Biểu đồ biến động giá các ngành - {datetime.now().strftime('%d-%m-%Y %H:%M')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        yaxis=dict(title='BĐ giá', gridcolor='#555'),
        yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right', gridcolor='#555'),
        xaxis=dict(tickangle=-45)
    )
    
    fig.write_html("index.html")
    print("Hoàn thành!")

if __name__ == "__main__":
    main()
