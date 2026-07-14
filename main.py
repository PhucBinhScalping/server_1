import datetime as dt
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import plotly.graph_objects as io_go
import plotly.io as pio
from user_agent import random_user

# Cấu hình User-Agent toàn cục tránh bị chặn
global head
head = {"User-Agent": random_user()}

# Danh sách các mã thuộc nhóm Vingroup
MA_VINGROUP = ["VIC", "VRE", "VHM", "VPL"]

# =====================================================================
# 1. TỰ ĐỘNG TẢI DANH SÁCH NGÀNH VÀ CỔ PHIẾU TỪ API (THAY THẾ EXCEL)
# =====================================================================
def get_industry_and_tickers():
    """Tự động tải danh sách nhóm ngành cấp 2 và các mã cổ phiếu từ API"""
    try:
        print("-> Đang tự động tải danh sách cổ phiếu và nhóm ngành từ API...")
        # Sử dụng API nội bộ của VNDIRECT để lấy danh sách hồ sơ doanh nghiệp gồm ngành cấp 2 công ty niêm yết
        url = "https://finfo-api.vndirect.com.vn/v4/industry_classification?size=2000"
        r = requests.get(url, headers=head, timeout=15)
        
        nhom_nganh_dict = {"VINGROUP": []}
        
        if r.status_code == 200 and 'data' in r.json():
            for item in r.json()['data']:
                # Lấy mã cổ phiếu và tên ngành cấp 2 (ví dụ: Bất động sản, Ngân hàng...)
                ma = item.get('code', '').strip().upper()
                nganh_goc = item.get('industryLevel2GroupName', '').strip()
                
                if not ma or not nganh_goc or len(ma) != 3: # Chỉ lấy các mã cổ phiếu thường 3 ký tự
                    continue
                
                # Phân tách logic nhóm Vingroup
                if ma in MA_VINGROUP:
                    if ma not in nhom_nganh_dict["VINGROUP"]:
                        nhom_nganh_dict["VINGROUP"].append(ma)
                else:
                    if nganh_goc not in nhom_nganh_dict:
                        nhom_nganh_dict[nganh_goc] = []
                    if ma not in nhom_nganh_dict[nganh_goc]:
                        nhom_nganh_dict[nganh_goc].append(ma)
                        
            return nhom_nganh_dict
    except Exception as e:
        print(f"[Cảnh báo] Lỗi tự động tải danh sách ngành: {e}. Chuyển sang danh mục dự phòng...")
    
    # Danh mục dự phòng cơ bản nếu API ngành bị lỗi
    return {"VINGROUP": ["VIC", "VHM", "VRE"], "Ngân hàng": ["VCB", "BID", "CTG", "TCB", "MBB"], "Bất động sản": ["DXG", "DIG", "PDR", "NLG"]}

# =====================================================================
# 2. TẢI TOÀN BỘ DỮ LIỆU LỊCH SỬ 60 PHIÊN CỦA TOÀN THỊ TRƯỜNG
# =====================================================================
def download_all_market_history():
    try:
        tz_vn = timezone(timedelta(hours=7))
        todate = datetime.now(tz_vn)
        fromdate = todate - timedelta(days=90)
        fdate = fromdate.strftime('%Y-%m-%d')

        print(f"-> Đang tải dữ liệu lịch sử thị trường từ ngày: {fdate}...")
        url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=50000&page=1"
        r = requests.get(url, headers=head, timeout=20)
        
        if r.status_code == 200 and 'data' in r.json():
            df = pd.DataFrame(r.json()['data'])
            if df.empty:
                return pd.DataFrame()
                
            df.rename(columns={
                'code': 'symbol', 'nmVolume': 'klgd_khop_lenh', 'nmValue': 'gtgd_khop_lenh',
                'ptVolume': 'klgd_thoa_thuan', 'ptValue': 'gtgd_thoa_thuan',
                'change': '+/-', 'pctChange': '+/-%'
            }, inplace=True)

            df['volume'] = pd.to_numeric(df['klgd_khop_lenh'], errors='coerce').fillna(0) + \
                            pd.to_numeric(df['klgd_thoa_thuan'], errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True)
            
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', '+/-%']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
                
            df = df.sort_values(by=['symbol', 'date'], ascending=[True, True])
            return df
    except Exception as e:
        print(f"[Lỗi] Không thể tải dữ liệu lịch sử thị trường: {e}")
    return pd.DataFrame()

# =====================================================================
# 3. HÀM TÍNH TOÁN DỮ LIỆU CỦA CỔ PHIẾU TRÊN RAM
# =====================================================================
def tinh_du_lieu_cp_from_ram(symbol, market_df):
    try:
        data = market_df[market_df['symbol'] == symbol.upper()].copy()
        if data.empty or len(data) < 21:
            return None
            
        last_row = data.iloc[-1]
        volume_trung_binh = data['volume'].tail(60).mean()
        if pd.isna(volume_trung_binh) or volume_trung_binh <= 10000:
            return None

        gia_close = float(last_row['close'])
        KL1000 = float(last_row['volume']) / 1000
        BD_gia = float(last_row['+/-%']) / 100

        KLGD_KLTB21_mean = data['volume'].tail(21).mean()
        KLTB_KLTB21 = float(last_row['volume']) / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0

        close_mean_5 = data['close'].tail(5).mean()
        close_mean_21 = data['close'].tail(21).mean()
        gia_tbgia5 = close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0

        KL_KLTB5_mean = data['volume'].tail(5).mean()
        KL_KLTB5 = float(last_row['volume']) / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0

        data_60 = data.tail(60)
        close_60 = data_60['close']
        day2t = close_60.min()
        dinh2t = close_60.max()
        
        dinh_day = (dinh2t - day2t) / day2t if day2t > 0 else 0
        giam_sdinh = (gia_close - dinh2t) / dinh2t if dinh2t > 0 else 0
        tang_sday = (gia_close - day2t) / day2t if day2t > 0 else 0

        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, day2t, dinh2t, tang_sday, giam_sdinh]
    except Exception:
        return None

def get_data_index():
    try:
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', headers=head, timeout=10)
        results_vni = json.loads(re_vni_url.text)
        results_vni[0]['name'] = 'HNX'
        results_vni[3]['name'] = 'UPCOM'
        df = pd.DataFrame([results_vni[1], results_vni[4], results_vni[0], results_vni[2], results_vni[3]])
        df['change'] = df['change'].apply(pd.to_numeric, errors='coerce')
        df['percent'] = df['percent'].apply(pd.to_numeric, errors='coerce') / 100
        df['value'] = df['value'].str.replace(',', '').astype(float)
        return df[['name', 'change', 'index', 'percent', 'volume', 'value']]
    except Exception:
        return pd.DataFrame()

# =====================================================================
# 4. HÀM ĐIỀU PHỐI CHÍNH VÀ XUẤT WEBSITE BIỂU ĐỒ SONG TRỤC NỀN TỐI
# =====================================================================
def main():
    print("=== HỆ THỐNG PHÂN TÍCH DIỄN BIẾN NGÀNH SONG TRỤC TỰ ĐỘNG ===")
    
    # Gọi hàm tự động lấy danh sách ngành từ API
    nhom_nganh_dict = get_industry_and_tickers()
    
    market_df = download_all_market_history()
    if market_df.empty:
        print("[Lỗi] Không có dữ liệu lịch sử thị trường đầu vào.")
        return

    danh_sach_kq_nganh = []

    for nganh, list_ticker in nhom_nganh_dict.items():
        if not list_ticker or nganh == "":
            continue
            
        list_ds_tb = {}
        for ma in list_ticker:
            res = tinh_du_lieu_cp_from_ram(ma, market_df)
            if res is not None:
                list_ds_tb[ma] = res
                
        if not list_ds_tb:
            continue

        df_dict = pd.DataFrame.from_dict(list_ds_tb, orient='index')
        df_dict.columns = [
            'gia_close', 'KL1000', 'BD_gia', 'KLTB_KLTB21', 'gia_tbgia5', 
            'KL_KLTB5', 'dinh_day', 'day2t', 'dinh2t', 'tang_sday', 'giam_sdinh'
        ]
        
        columns_to_mean = ['BD_gia', 'KLTB_KLTB21', 'gia_tbgia5', 'KL_KLTB5']
        result_series = df_dict[columns_to_mean].mean()
        
        df_nganh_final = result_series.to_frame().T
        df_nganh_final.insert(0, 'Ngành', nganh)
        danh_sach_kq_nganh.append(df_nganh_final)
        print(f" -> Xử lý ngành thành công: {nganh} ({len(list_ds_tb)} mã)")

    if not danh_sach_kq_nganh:
        print("Không thể trích xuất số liệu ngành.")
        return

    df_tong_hop_nganh = pd.concat(danh_sach_kq_nganh, ignore_index=True)
    df_tong_hop_nganh.rename(columns={'Ngành': 'name', 'BD_gia': 'percent_change', 'KLTB_KLTB21': 'volume_ratio'}, inplace=True)
    
    tz_vn = timezone(timedelta(hours=7))
    now_dt = datetime.now(tz_vn)
    df_tong_hop_nganh['updated_at'] = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    df_dash = df_tong_hop_nganh.copy()
    df_dash['percent_change'] = df_dash['percent_change'] * 100
    df_dash = df_dash.sort_values(by="percent_change", ascending=False)

    # Khởi tạo Graph Objects cho Biểu đồ Song trục Y
    fig = io_go.Figure()

    # 1. Trục Y1 bên trái: Cột (Bar Chart) biến động giá %
    colors_bar = ['#198754' if x >= 0 else '#dc3545' for x in df_dash['percent_change']]
    fig.add_trace(io_go.Bar(
        x=df_dash['name'],  y=df_dash['percent_change'],
        name='Biến động giá (%)',  marker_color=colors_bar,
        text=df_dash['percent_change'].apply(lambda x: f"{x:.2f}%"),
        textposition='auto', yaxis='y1'
    ))

    # 2. Trục Y2 bên phải: Đường (Line Chart) xu hướng thanh khoản
    fig.add_trace(io_go.Scatter(
        x=df_dash['name'], y=df_dash['volume_ratio'],
        name='KL/TBKL21 (Lần)', mode='lines+markers',
        line=dict(color='#ffc107', width=3),
        marker=dict(size=8, color='#d63384'), yaxis='y2'
    ))

    # Định dạng nền tối chuẩn TradingView chuyên nghiệp
    fig.update_layout(
        title=dict(text=f"Biểu đồ biến động giá và thanh khoản các ngành ({now_dt.strftime('%d-%m-%Y')})", x=0.5, font=dict(size=16, color="#ffffff")),
        paper_bgcolor='#212529', plot_bgcolor='#2b3035',
        xaxis=dict(tickangle=45, tickfont=dict(color="#ffffff"), gridcolor="#495057"),
        yaxis=dict(title="Biến động giá (%)", titlefont=dict(color="#ffffff"), tickfont=dict(color="#ffffff"), ticksuffix="%", gridcolor="#495057"),
        yaxis2=dict(title="Tỷ lệ KL/TBKL21 (Lần)", titlefont=dict(color="#ffffff"), tickfont=dict(color="#ffffff"), overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#ffffff")),
        margin=dict(l=50, r=50, t=80, b=120)
    )

    html_charts = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    
    df_table_show = df_dash[['name', 'percent_change', 'volume_ratio']].copy()
    df_table_show.columns = ['Nhóm Ngành', 'Biến Động Giá (%)', 'Tỷ Lệ Thanh Khoản (Lần)']
    html_table = df_table_show.to_html(classes='table table-dark table-hover table-striped table-bordered text-center', index=False, float_format=lambda x: f"{x:.2f}")

    df_idx = get_data_index()
    html_idx = df_idx.to_html(classes='table table-dark table-bordered text-center table-striped', index=False) if not df_idx.empty else "<p>Không có dữ liệu</p>"

    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Phân Tích Nhóm Ngành Toàn Diện</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #121416; color: #ffffff; }}
            .card {{ background-color: #212529; border: 1px solid #343a40; }}
            .card-header {{ background-color: #2b3035; color: #fff; border-bottom: 1px solid #343a40; }}
        </style>
    </head>
    <body>
        <div class="container-fluid px-4 my-4">
            <div class="text-center mb-4">
                <h2 class="fw-bold text-uppercase text-warning">HỆ THỐNG PHÂN TÍCH BIẾN ĐỘNG NGÀNH TỰ ĐỘNG</h2>
                <p class="text-secondary">Cập nhật phiên mới nhất: <span class="badge bg-danger">{now_dt.strftime('%d/%m/%Y %H:%M:%S')}</span></p>
            </div>
            
            <div class="card mb-4">
                <div class="card-header fw-bold text-center text-info">📊 BIỂU ĐỒ DIỄN BIẾN GIÁ & THANH KHOẢN KHỐI LƯỢNG SONG TRỤC</div>
                <div class="card-body p-1" style="min-height: 550px;">{html_charts}</div>
            </div>
            
            <div class="row">
                <div class="col-xl-5 col-lg-12 mb-4">
                    <div class="card h-100">
                        <div class="card-header fw-bold text-center text-success">📋 CHI TIẾT SỐ LIỆU THỐNG KÊ NGÀNH</div>
                        <div class="card-body table-responsive">{html_table}</div>
                    </div>
                </div>
                <div class="col-xl-7 col-lg-12 mb-4">
                    <div class="card h-100">
                        <div class="card-header fw-bold text-center text-warning">🌐 CHỈ SỐ TOÀN THỊ TRƯỜNG CHUNG</div>
                        <div class="card-body table-responsive">{html_idx}</div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("=== HOÀN THÀNH: FILE WEB MỚI VÀ BIỂU ĐỒ ĐÃ ĐƯỢC TẠO THÀNH CÔNG TỪ API ===")

if __name__ == "__main__":
    main()
