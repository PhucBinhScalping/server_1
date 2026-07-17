from update_index_only import get_world_index_html, get_gold_index_html
from index_service import get_data_index
import pandas as pd
import requests
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
    # Lấy dữ liệu 150 ngày
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
        
        # Lọc thanh khoản trung bình 100000 phiên (giảm xuống 1000 để lấy nhiều mã hơn)
        if df['volume'].tail(100).mean() < 100000:
            return None

        # Lấy dữ liệu phiên gần nhất thay vì bắt buộc phải là "hôm nay" để tránh lỗi cuối tuần
        last = df.iloc[-1]
        
        vol_mean_21 = df['volume'].tail(21).mean()
        kl_tb21 = (last['volume'] / vol_mean_21) if vol_mean_21 > 0 else 0
        
        return {'bd_gia': last['pctChange'], 'kl_tb21': kl_tb21}
    except:
        return None

def main():
    # 1. Xử lý dữ liệu bảng Chỉ số VN
    try:
        df_vni = get_data_index()
        # Đổi tên cột cho đẹp
        df_vni.columns = ['Chỉ số', 'Thay đổi', '%', 'KL Khớp', 'GT Khớp', 'Thanh khoản']
        # Format số để hiển thị dễ đọc
        df_vni['%'] = df_vni['%'].map('{:.2%}'.format)
        table_vietnam_html = df_vni.to_html(classes='world-index-table', border=0, justify='center', index=False)
    except Exception as e:
        table_vietnam_html = f"<p>Lỗi tải dữ liệu VNI: {e}</p>"
        
    df_config = pd.read_excel(FILE_DANH_SACH)
    # Chuẩn hóa tên ngành để tránh lỗi sai sót dữ liệu
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
        print("Không có dữ liệu.")
        return

    df_final = pd.DataFrame(results).sort_values('percent_change', ascending=False)
    vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    # Vẽ biểu đồ
    colors = ['#198754' if x > 0 else '#dc3545' for x in df_final['percent_change']]
    
    fig = io_go.Figure()
    fig.add_trace(io_go.Bar(x=df_final['name'], y=df_final['percent_change'], marker_color=colors, name='BĐ giá', texttemplate='%{y:.1f}%', textposition='outside'))
    fig.add_trace(io_go.Scatter(x=df_final['name'], y=df_final['volume_ratio'], yaxis='y2', line=dict(color='#FFD700', width=3), name='KL/TB21'))
    
    fig.update_layout(
        title=f"Biến động ngành {vn_now.strftime('%d-%m-%Y %H:%M:%S')}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        height=500, margin=dict(l=20, r=20, t=50, b=120),
        yaxis=dict(title='BĐ giá (%)'),
        yaxis2=dict(title='KL/TB21', overlaying='y', side='right'),
        xaxis=dict(tickangle=-45) # Nghiêng nhãn ngành
    )
    
    # Ghi file
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    html = html.replace('{{CHART_DIEN_BIEN}}', fig.to_html(full_html=False, include_plotlyjs='cdn'))
    html = html.replace('{{TABLE_VIETNAM}}', table_vietnam_html)
    time_str = vn_now.strftime('%d-%m-%Y %H:%M:%S')
    
    world_html = get_world_index_html()
    gold_html = get_gold_index_html()
    
    market_tables_content = f"""
    <!-- Dòng thời gian cập nhật chung cho cả 2 bảng -->
    <div style="text-align: right; font-size: 13px; color: #666; margin-bottom: 15px; font-style: italic;">
        Cập nhật: {time_str}
    </div>
    
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 300px; border-right: 2px dashed #808080; padding-right: 20px;">
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
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Cập nhật thành công!")

if __name__ == "__main__":
    main()
