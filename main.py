import datetime as dt
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import plotly.graph_objects as io_go
import plotly.io as pio
from user_agent import random_user

# Cấu hình User-Agent toàn cục tránh bị chặn khi gọi API từ GitHub server
global head
head = {"User-Agent": random_user()}

# Danh sách các mã thuộc nhóm Vingroup sẽ được tách riêng
MA_VINGROUP = ["VIC", "VRE", "VHM", "VPL"]

# File excel nguồn tại thư mục gốc của Repo
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

def download_all_market_history():
    """
    Tải toàn bộ dữ liệu lịch sử thị trường của tất cả các mã trong vòng 150 ngày gần nhất.
    150 ngày lịch để đảm bảo có tối thiểu ~100 phiên giao dịch thực tế (trừ thứ 7, chủ nhật, lễ).
    """
    try:
        tz_vn = timezone(timedelta(hours=7))
        todate = datetime.now(tz_vn)
        fromdate = todate - timedelta(days=150)
        fdate = fromdate.strftime('%Y-%m-%d')

        print(f"[LOG] 1. Tải dữ liệu lịch sử thị trường từ API từ ngày: {fdate}...")
        url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=100000&page=1"
        r = requests.get(url, headers=head, timeout=30)
        
        print(f"[LOG] Phản hồi API VNDIRECT: Status Code = {r.status_code}")
        if r.status_code == 200 and 'data' in r.json():
            df = pd.DataFrame(r.json()['data'])
            if df.empty:
                print("[LOG CẢNH BÁO] API trả về dữ liệu rỗng!")
                return pd.DataFrame()
                
            print(f"[LOG] Tải dữ liệu thành công. Số dòng thô: {len(df)}")
            df.rename(columns={
                'code': 'symbol', 'nmVolume': 'klgd_khop_lenh', 'nmValue': 'gtgd_khop_lenh',
                'ptVolume': 'klgd_thoa_thuan', 'ptValue': 'gtgd_thoa_thuan',
                'change': '+/-', 'pctChange': '+/-%'
            }, inplace=True)

            # Tính tổng volume
            df['volume'] = pd.to_numeric(df['klgd_khop_lenh'], errors='coerce').fillna(0) + \
                            pd.to_numeric(df['klgd_thoa_thuan'], errors='coerce').fillna(0)
            
            df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True)
            
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', '+/-%']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
                
            # Sắp xếp theo thứ tự thời gian tăng dần để phục vụ việc tính toán các chỉ số
            df = df.sort_values(by=['symbol', 'date'], ascending=[True, True])
            print(f"[LOG] Hoàn tất chuẩn hóa. Số lượng mã giao dịch: {df['symbol'].nunique()}")
            return df
        else:
            print(f"[LOG LỖI API]: {r.text[:200]}")
    except Exception as e:
        print(f"[LOG LỖI HỆ THỐNG] Lỗi tải dữ liệu: {e}")
    return pd.DataFrame()

def tinh_du_lieu_cp_from_ram(symbol, market_df):
    """
    Tính toán các chỉ số kỹ thuật trực tiếp trên RAM thay vì đọc file CSV cục bộ.
    Đồng thời áp dụng bộ lọc khối lượng giao dịch trung bình 100 phiên > 10.000 cổ phiếu.
    """
    try:
        data = market_df[market_df['symbol'] == symbol.upper()].copy()
        if data.empty or len(data) < 21:
            return None
            
        # Lọc điều kiện: Tính Volume trung bình của 100 phiên giao dịch gần nhất
        volume_trung_binh_100 = data['volume'].tail(100).mean()
        if pd.isna(volume_trung_binh_100) or volume_trung_binh_100 <= 10000:
            # Bỏ qua cổ phiếu không đạt điều kiện thanh khoản
            return None

        last_row = data.iloc[-1]
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

        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, 0, 0, 0, 0, 0]
    except Exception:
        return None

def get_data_index():
    """Lấy dữ liệu chỉ số thị trường từ CaféF làm phụ trợ"""
    try:
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', headers=head, timeout=15)
        results_vni = json.loads(re_vni_url.text)
        results_vni[0]['name'] = 'HNX'
        results_vni[3]['name'] = 'UPCOM'
        df = pd.DataFrame([results_vni[1], results_vni[4], results_vni[0], results_vni[2], results_vni[3]])
        df['change'] = df['change'].apply(pd.to_numeric, errors='coerce')
        df['percent'] = df['percent'].apply(pd.to_numeric, errors='coerce') / 100
        df['value'] = df['value'].str.replace(',', '').astype(float)
        return df[['name', 'change', 'index', 'percent', 'volume', 'value']]
    except Exception as e:
        print(f"[LOG CẢNH BÁO] Không lấy được thông tin phụ index: {e}")
        return pd.DataFrame()

def tao_html_fallback(now_dt, message):
    """Sinh file HTML dự phòng tránh lỗi hệ thống khi API bị nghẽn đột ngột"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Hệ Thống Phân Tích Diễn Biến Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head>
    <body style="background-color: #121416; color: #ffffff; padding: 50px;">
        <div class="container text-center card p-5 bg-dark border-secondary">
            <h2 class="text-warning fw-bold mb-4">HỆ THỐNG PHÂN TÍCH BIẾN ĐỘNG NGÀNH</h2>
            <div class="alert alert-info">{message}</div>
            <p class="text-secondary">Cập nhật lần cuối: {now_dt.strftime('%d/%m/%Y %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("[LOG FALLBACK] Đã tạo thành công trang thái chờ index.html.")

def main():
    print("=== HỆ THỐNG PHÂN TÍCH DIỄN BIẾN NGÀNH SONG TRỤC ===")
    tz_vn = timezone(timedelta(hours=7))
    now_dt = datetime.now(tz_vn)
    
    if not os.path.exists(FILE_DANH_SACH):
        print(f"[LOG LỖI] Không thấy file excel {FILE_DANH_SACH} tại thư mục gốc.")
        tao_html_fallback(now_dt, f"Lỗi: Thiếu file cấu trúc ngành '{FILE_DANH_SACH}' trên GitHub.")
        return

    market_df = download_all_market_history()
    if market_df.empty:
        print("[LOG LỖI] Dữ liệu tải về từ API trống.")
        tao_html_fallback(now_dt, "Hệ thống đang chờ API VNDIRECT khởi tạo và cấp dữ liệu cho phiên giao dịch tiếp theo.")
        return

    print(f"[LOG] 2. Đọc file cấu trúc ngành: {FILE_DANH_SACH}")
    try:
        df_company = pd.read_excel(FILE_DANH_SACH)
        df_company.columns = df_company.columns.str.strip()
    except Exception as e:
        print(f"[LOG LỖI ĐỌC EXCEL] Lỗi: {e}")
        tao_html_fallback(now_dt, f"Lỗi định dạng cấu trúc file Excel: {e}")
        return
    
    # Đồng bộ hóa cột đầu vào của file excel mới
    col_ticker = 'Ticker' if 'Ticker' in df_company.columns else df_company.columns[0]
    col_nganh = 'Ngành' if 'Ngành' in df_company.columns else df_company.columns[6]

    df_company[col_ticker] = df_company[col_ticker].astype(str).str.strip().str.upper()
    df_company[col_nganh] = df_company[col_nganh].astype(str).str.strip()

    # Khởi tạo dictionary chứa danh sách mã theo ngành, định nghĩa sẵn nhóm VINGROUP
    nhom_nganh_dict = {"VINGROUP": []}

    for index, row in df_company.iterrows():
        ma = row[col_ticker]
        nganh_goc = row[col_nganh]
        
        if nganh_goc == 'nan' or not ma or len(ma) != 3:
            continue
            
        # NẾU CỔ PHIẾU THUỘC VINGROUP: Tách và gom vào nhóm "VINGROUP" riêng biệt
        if ma in MA_VINGROUP:
            if ma not in nhom_nganh_dict["VINGROUP"]:
                nhom_nganh_dict["VINGROUP"].append(ma)
        else:
            # Các cổ phiếu khác xếp vào nhóm ngành quy định trong Excel
            if nganh_goc not in nhom_nganh_dict:
                nhom_nganh_dict[nganh_goc] = []
            if ma not in nhom_nganh_dict[nganh_goc]:
                nhom_nganh_dict[nganh_goc].append(ma)

    danh_sach_kq_nganh = []
    
    # Duyệt tính toán trung bình từng ngành
    for nganh, list_ticker in nhom_nganh_dict.items():
        if not list_ticker or nganh == "":
            continue
            
        list_ds_tb = {}
        for ma in list_ticker:
            # Hàm tính toán đã tích hợp sẵn bộ lọc volume 100 phiên > 10.000
            res = tinh_du_lieu_cp_from_ram(ma, market_df)
            if res is not None:
                list_ds_tb[ma] = res
                
        if not list_ds_tb:
            continue

        df_dict = pd.DataFrame.from_dict(list_ds_tb, orient='index')
        df_dict.columns = ['gia_close', 'KL1000', 'BD_gia', 'KLTB_KLTB21', 'gia_tbgia5', 'KL_KLTB5', 'dinh_day', 'day2t', 'dinh2t', 'tang_sday', 'giam_sdinh']
        
        # Tính trung bình đại diện cho ngành
        result_series = df_dict[['BD_gia', 'KLTB_KLTB21', 'gia_tbgia5', 'KL_KLTB5']].mean()
        df_nganh_final = result_series.to_frame().T
        df_nganh_final.insert(0, 'Ngành', nganh)
        danh_sach_kq_nganh.append(df_nganh_final)

    if not danh_sach_kq_nganh:
        print("[LOG CẢNH BÁO] Không có mã nào thỏa mãn điều kiện thanh khoản > 10.000.")
        tao_html_fallback(now_dt, "Tất cả các ngành hiện tại không có cổ phiếu nào vượt mốc thanh khoản trung bình 100 phiên lớn hơn 10.000.")
        return

    # Gộp bảng tổng hợp
    df_tong_hop_nganh = pd.concat(danh_sach_kq_nganh, ignore_index=True)
    df_tong_hop_nganh.rename(columns={'Ngành': 'name', 'BD_gia': 'percent_change', 'KLTB_KLTB21': 'volume_ratio'}, inplace=True)
    
    df_dash = df_tong_hop_nganh.copy()
    df_dash['percent_change'] = df_dash['percent_change'] * 100
    df_dash = df_dash.sort_values(by="percent_change", ascending=False)

    # 3. Tiến hành vẽ đồ thị biểu diễn biến động bằng Plotly (Dark Theme)
    fig = io_go.Figure()
    colors_bar = ['#198754' if x >= 0 else '#dc3545' for x in df_dash['percent_change']]
    
    fig.add_trace(io_go.Bar(
        x=df_dash['name'], y=df_dash['percent_change'],
        name='Biến động giá (%)', marker_color=colors_bar,
        text=df_dash['percent_change'].apply(lambda x: f"{x:.2f}%"),
        textposition='auto', yaxis='y1'
    ))
    
    fig.add_trace(io_go.Scatter(
        x=df_dash['name'], y=df_dash['volume_ratio'],
        name='KL/TBKL21 (Lần)', mode='lines+markers',
        line=dict(color='#ffc107', width=3),
        marker=dict(size=8, color='#d63384'), yaxis='y2'
    ))

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
    html_table = df_dash[['name', 'percent_change', 'volume_ratio']].to_html(classes='table table-dark table-striped text-center table-bordered', index=False, float_format=lambda x: f"{x:.2f}")
    
    df_idx = get_data_index()
    html_idx = df_idx.to_html(classes='table table-dark text-center table-bordered table-striped', index=False) if not df_idx.empty else "<p>Đang tải thông số chỉ số...</p>"

    # 4. Xuất cấu trúc mã nguồn HTML hoàn thiện
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Biến Động Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #121416; color: #ffffff; }}
            .card {{ background-color: #212529; border: 1px solid #343a40; }}
            .card-header {{ background-color: #2b3035; color: #fff; border-bottom: 1px solid #343a40; }}
        </style>
    </head>
    <body>
        <div class="container-fluid px-4 my-4">
            <h2 class="text-center text-warning fw-bold mb-2 text-uppercase">HỆ THỐNG PHÂN TÍCH BIẾN ĐỘNG NGÀNH TỰ ĐỘNG</h2>
            <p class="text-center text-secondary mb-4">Cập nhật phiên mới nhất: <span class="badge bg-danger">{now_dt.strftime('%d/%m/%Y %H:%M:%S')}</span></p>
            <div class="card mb-4">
                <div class="card-header fw-bold text-center text-info">📊 BIỂU ĐỒ DIỄN BIẾN GIÁ & THANH KHOẢN KHỐI LƯỢNG SONG TRỤC</div>
                <div class="card-body p-1" style="min-height: 530px;">{html_charts}</div>
            </div>
            <div class="row">
                <div class="col-xl-5 mb-4">
                    <div class="card h-100">
                        <div class="card-header fw-bold text-center text-success">📋 CHI TIẾT SỐ LIỆU THỐNG KÊ NGÀNH</div>
                        <div class="card-body table-responsive">{html_table}</div>
                    </div>
                </div>
                <div class="col-xl-7 mb-4">
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
    print("=== HOÀN TẤT: FILE INDEX.HTML MỚI ĐÃ ĐƯỢC TẠO THÀNH CÔNG ===")

if __name__ == "__main__":
    main()
