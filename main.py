from update_index_only import get_world_index_html
from update_index_only import get_gold_index_html
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
    today = datetime.now(vn_tz).strftime("%Y-%m-%d")
    # Lấy dữ liệu 150 ngày để tính TB 100 phiên
    ngay_start = (datetime.now(vn_tz) - timedelta(days=150)).strftime("%Y-%m-%d")
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}&size=150&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        df = df.sort_values(by='date')
        df['pctChange'] = pd.to_numeric(df['pctChange'], errors='coerce')
        df['volume'] = pd.to_numeric(df['nmVolume'], errors='coerce').fillna(0) + pd.to_numeric(df['ptVolume'], errors='coerce').fillna(0)
        
        # 1. Lọc thanh khoản (TB 100 phiên > 100,000)
        volume_tb100 = df['volume'].tail(100).mean()
        if volume_tb100 <= 10000:
            return None

        # 2. Lọc dữ liệu của ngày hôm nay (Bắt buộc)
        df_today = df[df['date'] == today]
        if df_today.empty:
            return None
            
        last = df_today.iloc[-1]
        bd_gia = pd.to_numeric(last['pctChange'], errors='coerce')
        
        # Tính KL/TB21
        vol_mean_21 = pd.to_numeric(df['volume'].tail(21).mean(), errors='coerce')
        kl_tb21 = pd.to_numeric(last['volume'] / vol_mean_21, errors='coerce') if vol_mean_21 > 0 else 0
        
        return {'bd_gia': bd_gia, 'kl_tb21': kl_tb21}
    except Exception as e:
        return None

def main():
    df_config = pd.read_excel(FILE_DANH_SACH)
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'Vingroup'
    
    results = []
    ds_nganh = df_config['Ngành Cấp 2'].dropna().unique()
    
    for nganh in ds_nganh:
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            df_nganh = pd.DataFrame(data_nganh)
            
            # Tính trung bình các mã có giao dịch ngày hôm nay
            final_bd = df_nganh['bd_gia'].mean()
            final_kl = df_nganh['kl_tb21'].mean()
            
            results.append({'name': nganh, 'percent_change': final_bd, 'volume_ratio': final_kl})

    if not results:
        print("Không có dữ liệu thỏa mãn.")
        return
        
    df_final = pd.DataFrame(results)
    
    # Tạo biến thời gian theo múi giờ Việt Nam
    vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
     
    # Vẽ biểu đồ
    colors = ['#198754' if x > 0.0001 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    
    # Thêm tham số name="BĐ_giá"
    fig.add_trace(io_go.Bar(
        x=df_final['name'], 
        y=df_final['percent_change'], 
        marker_color=colors, 
        name='BĐ_giá', 
        texttemplate='%{y:.2f}%', 
        textposition='outside'
    ))
    
    # Thêm tham số name="KL/KLTB21"
    fig.add_trace(io_go.Scatter(
        x=df_final['name'], 
        y=df_final['volume_ratio'], 
        yaxis='y2', 
        line=dict(color='#FFD700', width=3), 
        name='KL/KLTB21'
    ))
    
    fig.update_layout(
            title=f"Biến động ngành - {vn_now.strftime('%d-%m-%Y %H:%M:%S')}", 
            paper_bgcolor='#333333', 
            plot_bgcolor='#333333', 
            font=dict(color='white'),
            height=600, 
            yaxis=dict(title='BĐ giá (%)'), 
            yaxis2=dict(title='KL/TBKL21', overlaying='y', side='right'),
            margin=dict(l=60, r=60, t=80, b=150)
        )
    
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read().replace('{{CHART_DIEN_BIEN}}', fig.to_html(full_html=False, include_plotlyjs='cdn'))
        
    world_html = get_world_index_html()
    gold_html = get_gold_index_html()
    
    market_tables_content = f"""
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 300px;">
            <h3 style="text-align:center;">Thị trường Thế giới</h3>
            {world_html}
        </div>
        <div style="flex: 1; min-width: 300px;">
            <h3 style="text-align:center;">Giá Vàng</h3>
            {gold_html}
        </div>
    </div>
    """
    
    # Thay thế Bảng chỉ số thế giới
    html = html.replace('{{TABLE_WORLD}}', market_tables_content)
    
    # Ghi đè ra file index.html
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Cập nhật thành công!")

if __name__ == "__main__":
    main()
