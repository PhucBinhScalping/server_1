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

HEAD = {
    "User-Agent": random_user()
}

def tinh_du_lieu_cp(symbol):
    try:
        clean_symbol = str(symbol).strip().upper()
        
        todate = datetime.now()
        fromdate = todate - timedelta(days=156)

        from_timestamp = int(fromdate.timestamp())
        to_timestamp = int(todate.timestamp())

        # URL gốc truyền trực tiếp symbol không qua tiền tố
        url = f'https://web7.vps.com.vn/trading-view/api/public/history?symbol={clean_symbol}&resolution=1D&from={from_timestamp}&to={to_timestamp}'
        
        r = requests.get(url, headers=HEAD, timeout=10)
        
        if r.status_code != 200:
            return None
            
        res_json = r.json()
        
        if not res_json or res_json.get('s') != 'ok':
            return None
            
        df = pd.DataFrame({
            'timestamp': res_json['t'],
            'close': res_json['c'],
            'volume': res_json['v']
        })
        
        if df.empty:
            return None

        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s') + timedelta(hours=7)
        df['date'] = df['datetime'].dt.strftime('%Y-%m-%d')
        df = df.sort_values(by='date').reset_index(drop=True)
        
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['pctChange'] = df['close'].pct_change() * 100
        
        if len(df) < 100:
            return None
            
        if df['volume'].tail(100).mean() < 200000:
            return None

        df_desc = df.sort_values(by='date', ascending=False).reset_index(drop=True)
        last = df_desc.iloc[0]
        
        bd_gia = round(float(last['pctChange']), 2) if pd.notnull(last['pctChange']) else 0.0
        
        vol_mean_21 = df_desc['volume'].iloc[:21].mean()
        kl_tb21 = round(float(last['volume'] / vol_mean_21), 2) if vol_mean_21 > 0 else 0.0
        
        return {'symbol': clean_symbol, 'bd_gia': bd_gia, 'kl_tb21': kl_tb21}
        
    except Exception as e:
        return None

def tao_bieu_do_plotly(df, title_prefix, time_str):
    """Hàm vẽ biểu đồ Plotly chung cho cả Ngành và VN30"""
    colors = [
        '#198754' if x > 0 else ('#dc3545' if x < 0 else '#6c757d') 
        for x in df['percent_change']
    ]
    
    fig = io_go.Figure()
    
    fig.add_trace(io_go.Bar(
        x=df['name'], 
        y=df['percent_change'], 
        marker_color=colors, 
        marker_line_color='white',
        marker_line_width=1.2,
        name='BĐ giá', 
        texttemplate='%{y:.1f}%', 
        textposition='outside',
        cliponaxis=False
    ))
    
    fig.add_trace(io_go.Scatter(
        x=df['name'], 
        y=df['volume_ratio'], 
        yaxis='y2', 
        line=dict(color='#FFD700', width=3), 
        name='KL/TB21'
    ))
    
    fig.update_layout(
        title=f"{title_prefix} {time_str}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        height=500, margin=dict(l=20, r=20, t=50, b=120),
        yaxis=dict(title='BĐ giá (%)', zeroline=True, zerolinecolor='white', zerolinewidth=1),
        yaxis2=dict(title='KL/TB21', overlaying='y', side='right'),
        xaxis=dict(tickangle=-45, type='category'), 
        autosize=True              
    )
    return fig

def main():
    print("\n=== [LOG] TIẾN HÀNH GỌI HÀM GET_DATA_INDEX() ===")
    table_vietnam_html = get_data_index() 
    
    if table_vietnam_html:
        print(f"Độ dài chuỗi HTML: {len(table_vietnam_html)} ký tự.")
    else:
        print("CẢNH BÁO: Hàm get_data_index() trả về giá trị RỖNG!")
    print("==================================================\n")
        
    df_config = pd.read_excel(FILE_DANH_SACH)
    df_config['Ngành Cấp 2'] = df_config['Ngành Cấp 2'].astype(str).str.strip().str.upper()
    df_config.loc[df_config['Ticker'].isin(['VIC', 'VRE', 'VHM', 'VPL']), 'Ngành Cấp 2'] = 'VINGROUP'
    
    # ----------------------------------------------------
    # 1. TÍNH DỮ LIỆU CỔ PHIẾU THEO NGÀNH
    # ----------------------------------------------------
    results_nganh = []
    ds_nganh = df_config['Ngành Cấp 2'].dropna().unique()
    
    for nganh in ds_nganh:
        tickers = df_config[df_config['Ngành Cấp 2'] == nganh]['Ticker'].unique()
        with ThreadPoolExecutor(max_workers=10) as executor:
            data_nganh = [x for x in list(executor.map(tinh_du_lieu_cp, tickers)) if x is not None]
        
        if data_nganh:
            df_nganh = pd.DataFrame(data_nganh)
            results_nganh.append({
                'name': nganh.title(), 
                'percent_change': df_nganh['bd_gia'].mean(), 
                'volume_ratio': df_nganh['kl_tb21'].mean()
            })

    # ----------------------------------------------------
    # 2. TÍNH DỮ LIỆU DANH SÁCH VN30
    # ----------------------------------------------------
    list_vn30 = [
        'ACB', 'BID', 'BSR', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'LPB', 
        'MBB', 'MCH', 'MSN', 'MWG', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 
        'TCX', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VPL', 'VRE'
    ]
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        data_vn30_raw = list(executor.map(tinh_du_lieu_cp, list_vn30))
    
    results_vn30 = []
    for symbol in list_vn30:
        found = next((item for item in data_vn30_raw if item and item.get('symbol') == symbol), None)
        results_vn30.append({
            'name': symbol,
            'percent_change': found['bd_gia'],
            'volume_ratio': found['kl_tb21']})

    vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    time_str = vn_now.strftime('%d-%m-%Y %H:%M:%S')

    # ----------------------------------------------------
    # 3. VẼ BIỂU ĐỒ & CHUYỂN DẠNG HTML (ĐÃ SỬA VỊ TRÍ TẢI JS)
    # ----------------------------------------------------
    chart_config = {'responsive': True}

    # Biểu đồ 1: VN30 (Nằm ĐẦU PAGE -> Phải tải thư viện JS với include_plotlyjs='cdn')
    df_final_vn30 = pd.DataFrame(results_vn30).sort_values('percent_change', ascending=True)
    fig_vn30 = tao_bieu_do_plotly(df_final_vn30, "Biến động danh mục VN30", time_str)
    chart_vn30_html = fig_vn30.to_html(full_html=False, include_plotlyjs='cdn', config=chart_config)

    # Biểu đồ 2: Ngành (Nằm DƯỚI -> Không tải trùng lại JS nên chọn include_plotlyjs=False)
    df_final_nganh = pd.DataFrame(results_nganh)
    fig_nganh = tao_bieu_do_plotly(df_final_nganh, "Biến động ngành", time_str)
    chart_nganh_html = fig_nganh.to_html(full_html=False, include_plotlyjs=False, config=chart_config)
    fig_nganh.write_image(CHART_ONLY_FILE, format="png", width=1200, height=600, scale=2)

    # ----------------------------------------------------
    # 4. NHÚNG HTML VÀO TEMPLATE
    # ----------------------------------------------------
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

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
    
    html = html.replace('{{CHART_DIEN_BIEN}}', chart_nganh_html)
    html = html.replace('{{CHART_DIEN_BIEN_VN30}}', chart_vn30_html)
    html = html.replace('{{TABLE_VIETNAM}}', vietnam_block_html)
    html = html.replace('{{TABLE_WORLD}}', market_tables_content)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
        
    print(f"Cập nhật thành công vào lúc: {time_str}!")

if __name__ == "__main__":
    main()
