from update_index_only import get_world_index_html, get_gold_index_html
from get_index_vn import get_data_index
import pandas as pd
import requests
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor

# Cấu hình hệ thống
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"
TEMPLATE_FILE = "template.html"
OUTPUT_FILE = "index.html"
HEAD = {"User-Agent": "Mozilla/5.0"}
session = requests.Session()

def tinh_du_lieu_cp(symbol):
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    ngay_start = (datetime.now(vn_tz) - timedelta(days=150)).strftime("%Y-%m-%d")
    url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{ngay_start}&size=150&page=1'
    
    try:
        r = session.get(url, headers=HEAD, timeout=10)
        data = r.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date')
        
        df['pctChange'] = pd.to_numeric(df['pctChange'], errors='coerce')
        df['volume'] = pd.to_numeric(df['nmVolume'], errors='coerce').fillna(0) + pd.to_numeric(df['ptVolume'], errors='coerce').fillna(0)
        
        if df['volume'].tail(100).mean() < 396000:
            return None

        last = df.iloc[-1]
        vol_mean_21 = df['volume'].tail(21).mean()
        kl_tb21 = (last['volume'] / vol_mean_21) if vol_mean_21 > 0 else 0
        
        return {'bd_gia': last['pctChange'], 'kl_tb21': kl_tb21}
    except:
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
