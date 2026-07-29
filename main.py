from update_index_only import get_world_index_html, get_gold_index_html
from get_index_vn import get_data_index
import pandas as pd
import requests
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor
from user_agent import random_user


# Cấu hình hệ thống
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"
TEMPLATE_FILE = "template.html"
OUTPUT_FILE = "index.html"
CHART_ONLY_FILE = "chart_only.png"
session = requests.Session()

import datetime as dt
from datetime import timedelta
import pandas as pd
import requests

HEAD = {
    "User-Agent": random_user()
}

def tinh_du_lieu_cp(symbol):
    try:
        # 1. Bổ sung prefix cho symbol nếu thiếu (mặc định thử HOSE nếu gọi trực tiếp)
        clean_symbol = symbol.strip().upper()
        
        # 2. Thiết lập thời gian (TradingView API sử dụng timestamp giây)
        todate = dt.datetime.now()
        fromdate = todate - timedelta(days=156) # Mở rộng ra 365 ngày để đảm bảo đủ >100 phiên giao dịch (trừ lễ/cuối tuần)
        
        from_timestamp = int(fromdate.timestamp())
        to_timestamp = int(todate.timestamp())

        # 3. URL chuẩn của VPS TradingView
        url = f'https://web7.vps.com.vn/trading-view/api/public/history?symbol={clean_symbol}&resolution=1D&from={from_timestamp}&to={to_timestamp}'
        
        # Sửa lỗi: Dùng HEAD viết hoa
        r = requests.get(url, headers=HEAD, timeout=10)
        
        if r.status_code != 200:
            return None
            
        res_json = r.json()
        
        # Kiểm tra phản hồi từ API
        if not res_json or res_json.get('s') != 'ok':
            return None
            
        # 4. Trích xuất dữ liệu an toàn
        df = pd.DataFrame({
            'timestamp': res_json['t'],
            'close': res_json['c'],
            'volume': res_json['v']
        })
        
        if df.empty:
            return None

        # Quy đổi thời gian & sắp xếp
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s') + timedelta(hours=7)
        df['date'] = df['datetime'].dt.strftime('%Y-%m-%d')
        df = df.sort_values(by='date').reset_index(drop=True)
        
        # Ep kiểu dữ liệu số
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        
        # Tính % thay đổi giá
        df['pctChange'] = df['close'].pct_change() * 100
        
        # 5. Kiểm tra điều kiện thanh khoản (100 phiên gần nhất)
        if len(df) < 100:
            return None
            
        if df['volume'].tail(100).mean() < 200000:
            return None

        # Lấy dữ liệu phiên gần nhất (mới nhất)
        df_desc = df.sort_values(by='date', ascending=False).reset_index(drop=True)
        last = df_desc.iloc[0]
        
        bd_gia = round(float(last['pctChange']), 2) if pd.notnull(last['pctChange']) else 0.0
        
        # Tính khối lượng trung bình 21 phiên
        vol_mean_21 = df_desc['volume'].iloc[:21].mean()
        kl_tb21 = round(float(last['volume'] / vol_mean_21), 2) if vol_mean_21 > 0 else 0.0
        
        return {'bd_gia': bd_gia, 'kl_tb21': kl_tb21}
        
    except Exception as e:
        # Gợi ý: Bỏ comment dòng dưới nếu muốn debug xem lỗi cụ thể là gì
        # print(f"Lỗi mã {symbol}: {e}")
        return None

def main():
    # 1. Gọi và KIỂM TRA dữ liệu nhận từ file get_index_vn.py
    print("\n=== [LOG] TIẾN HÀNH GỌI HÀM GET_DATA_INDEX() ===")
    table_vietnam_html = get_data_index() 
    
    print("=== [LOG] KẾT QUẢ TRẢ VỀ TỪ FILE GET_INDEX_VN.PY ===")
    if table_vietnam_html:
        print(f"Độ dài chuỗi HTML: {len(table_vietnam_html)} ký tự.")
        print("Đoạn code HTML nhận được (1000 ký tự đầu):")
        print(table_vietnam_html[:1000])
    else:
        print("CẢNH BÁO: Hàm get_data_index() trả về giá trị RỖNG (None hoặc Empty String)!")
    print("==================================================\n")
        
    df_config = pd.read_excel(FILE_DANH_SACH)
    df_config['Ngành Cấp 2'] = df_config['Ngành Cấp 2'].astype(str).str.strip().str.upper()
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'VINGROUP'
    
    results = []
    ds_nganh = df_config['Ngành Cấp 2'].dropna().unique()
    
    for nganh in ds_nganh:
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            df_nganh = pd.DataFrame(data_nganh)
            results.append({
                'name': nganh.title(), 
                'percent_change': df_nganh['bd_gia'].mean(), 
                'volume_ratio': df_nganh['kl_tb21'].mean()
            })

    if not results:
        print("Không có dữ liệu cổ phiếu ngành.")
        return

    df_final = pd.DataFrame(results)#.sort_values('percent_change', ascending=False)
    
    vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    time_str = vn_now.strftime('%d-%m-%Y %H:%M:%S')
    
    colors = ['#198754' if x > 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors, name='BĐ giá', texttemplate='%{y:.1f}%', textposition='outside'))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='#FFD700', width=3), name='KL/TB21'))
    
    fig.update_layout(
        title=f"Biến động ngành {time_str}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        height=500, margin=dict(l=20, r=20, t=50, b=120),
        yaxis=dict(title='BĐ giá (%)'),
        yaxis2=dict(title='KL/TB21', overlaying='y', side='right'),
        xaxis=dict(tickangle=-45), 
        autosize=True              
    )

    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    chart_config = {'responsive': True}
    chart_render = fig.to_html(full_html=False, include_plotlyjs='cdn', config=chart_config)

    fig.write_image(CHART_ONLY_FILE, format="png", width=1200, height=600, scale=2)
    
    # 2. Khối HTML Việt Nam (Ăn theo cấu trúc class của template)
    vietnam_block_html = f"""
    <div style="text-align: right; font-size: 13px; color: #666; margin-bottom: 5px; font-style: italic;">
        Cập nhật: {time_str}
    </div>
    {table_vietnam_html}
    """
    
    world_html = get_world_index_html()
    gold_html = get_gold_index_html()
    
    market_tables_content = f"""
    <div style="text-align: right; font-size: 13px; color: #666; margin-bottom: 15px; font-style: italic;">
        Cập nhật: {time_str}
    </div>
    
    <div class="market-section" style="margin-bottom: 30px; width: 100%;">
        <h3 style="text-align:center; margin-bottom: 12px; color: #002060; font-size: 1.5em;">Thị trường Thế giới</h3>
        <div class="content-scroll-wrapper" style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">
            {world_html}
        </div>
    </div>

    <div class="market-section" style="width: 100%;">
        <h3 style="text-align:center; margin-bottom: 12px; color: #002060; font-size: 1.5em;">Giá Vàng</h3>
        <div class="content-scroll-wrapper" style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">
            {gold_html}
        </div>
    </div>
    """
    
    html = html.replace('{{CHART_DIEN_BIEN}}', chart_render)
    html = html.replace('{{TABLE_VIETNAM}}', vietnam_block_html)
    html = html.replace('{{TABLE_WORLD}}', market_tables_content)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
        
    print(f"Cập nhật thành công vào lúc: {time_str}!")

if __name__ == "__main__":
    main()
