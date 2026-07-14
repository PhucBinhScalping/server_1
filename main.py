import datetime as dt
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import sys
import traceback
import plotly.graph_objects as io_go
import plotly.io as pio
from user_agent import random_user

# Cấu hình User-Agent
global head
head = {"User-Agent": random_user()}

# Danh sách các mã thuộc nhóm Vingroup
MA_VINGROUP = ["VIC", "VRE", "VHM", "VPL"]
FILE_DANH_SACH = "danh_sach_cong_ty.xlsx"

# Biến toàn cục để gom toàn bộ Log in ra màn hình và ghi vào HTML
debug_logs = []

def log(msg):
    """Hàm in log ra console đồng thời lưu lại để xuất ra HTML"""
    print(msg)
    debug_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def download_all_market_history():
    try:
        tz_vn = timezone(timedelta(hours=7))
        todate = datetime.now(tz_vn)
        fromdate = todate - timedelta(days=150)
        fdate = fromdate.strftime('%Y-%m-%d')

        log(f"Bắt đầu tải dữ liệu lịch sử từ API (150 ngày gần nhất, từ ngày: {fdate})...")
        url = f"https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=100000&page=1"
        r = requests.get(url, headers=head, timeout=30)
        
        log(f"Kết quả phản hồi từ API: Status Code = {r.status_code}")
        if r.status_code == 200 and 'data' in r.json():
            df = pd.DataFrame(r.json()['data'])
            if df.empty:
                log("CẢNH BÁO: Dữ liệu API trả về trống rỗng!")
                return pd.DataFrame()
                
            log(f"Tải thành công. Tổng số dòng dữ liệu lịch sử thô: {len(df)}")
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
            log(f"Đã chuẩn hóa dữ liệu RAM thành công. Số lượng mã duy nhất: {df['symbol'].nunique()}")
            return df
        else:
            log(f"LỖI PHẢN HỒI API: {r.text[:300]}")
    except Exception as e:
        log(f"LỖI KHI GỌI API: {str(e)}")
    return pd.DataFrame()

def tinh_du_lieu_cp_from_ram(symbol, market_df):
    try:
        data = market_df[market_df['symbol'] == symbol.upper()].copy()
        if data.empty or len(data) < 21:
            return None
            
        volume_trung_binh_100 = data['volume'].tail(100).mean()
        if pd.isna(volume_trung_binh_100) or volume_trung_binh_100 <= 10000:
            # Ghi nhận log các mã bị loại vì thanh khoản thấp (chỉ in trong log terminal để đỡ rác)
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

def main():
    log("=== KHỞI CHẠY TIẾN TRÌNH DEBUG LỖI ===")
    tz_vn = timezone(timedelta(hours=7))
    now_dt = datetime.now(tz_vn)
    
    html_table = "<p class='text-danger'>Chưa tính toán được bảng dữ liệu.</p>"
    html_charts = "<p class='text-danger'>Chưa có biểu đồ.</p>"
    error_traceback = ""

    try:
        # 1. Kiểm tra sự tồn tại của file cấu hình excel
        if not os.path.exists(FILE_DANH_SACH):
            raise FileNotFoundError(f"Không tìm thấy file '{FILE_DANH_SACH}' tại thư mục gốc của repository! Thư mục hiện tại chứa các file: {os.listdir('.')}")
        
        log(f"Đã phát hiện file excel cấu hình: '{FILE_DANH_SACH}'")

        # 2. Tải dữ liệu API
        market_df = download_all_market_history()
        if market_df.empty:
            raise ValueError("Không thể chạy tính toán vì dữ liệu tải về từ API lịch sử bị rỗng hoặc lỗi kết nối.")

        # 3. Đọc dữ liệu excel
        log("Đang tiến hành mở và kiểm tra các cột trong file Excel...")
        df_company = pd.read_excel(FILE_DANH_SACH)
        df_company.columns = df_company.columns.str.strip()
        log(f"Đọc file Excel thành công! Các cột tìm thấy: {list(df_company.columns)}")
        
        # Ánh xạ cột
        col_ticker = 'Ticker' if 'Ticker' in df_company.columns else df_company.columns[0]
        col_nganh = 'Ngành' if 'Ngành' in df_company.columns else df_company.columns[6]
        log(f"Sử dụng cột Mã cổ phiếu: '{col_ticker}' và cột Tên ngành: '{col_nganh}'")

        df_company[col_ticker] = df_company[col_ticker].astype(str).str.strip().str.upper()
        df_company[col_nganh] = df_company[col_nganh].astype(str).str.strip()

        # Phân nhóm ngành
        nhom_nganh_dict = {"VINGROUP": []}
        for index, row in df_company.iterrows():
            ma = row[col_ticker]
            nganh_goc = row[col_nganh]
            if nganh_goc == 'nan' or not ma or len(ma) != 3:
                continue
            if ma in MA_VINGROUP:
                if ma not in nhom_nganh_dict["VINGROUP"]:
                    nhom_nganh_dict["VINGROUP"].append(ma)
            else:
                if nganh_goc not in nhom_nganh_dict:
                    nhom_nganh_dict[nganh_goc] = []
                if ma not in nhom_nganh_dict[nganh_goc]:
                    nhom_nganh_dict[nganh_goc].append(ma)

        log(f"Tổng số nhóm ngành tách được: {len(nhom_nganh_dict)}")

        # Tính toán dữ liệu ngành
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
            df_dict.columns = ['gia_close', 'KL1000', 'BD_gia', 'KLTB_KLTB21', 'gia_tbgia5', 'KL_KLTB5', 'dinh_day', 'day2t', 'dinh2t', 'tang_sday', 'giam_sdinh']
            
            # Tính trung bình đại diện
            result_series = df_dict[['BD_gia', 'KLTB_KLTB21', 'gia_tbgia5', 'KL_KLTB5']].mean()
            df_nganh_final = result_series.to_frame().T
            df_nganh_final.insert(0, 'Ngành', nganh)
            danh_sach_kq_nganh.append(df_nganh_final)

        if not danh_sach_kq_nganh:
            raise ValueError("Không có mã cổ phiếu nào đạt đủ điều kiện thanh khoản trung bình 100 phiên > 10.000 để tổng hợp dữ liệu ngành!")

        df_tong_hop_nganh = pd.concat(danh_sach_kq_nganh, ignore_index=True)
        df_tong_hop_nganh.rename(columns={'Ngành': 'name', 'BD_gia': 'percent_change', 'KLTB_KLTB21': 'volume_ratio'}, inplace=True)
        
        df_dash = df_tong_hop_nganh.copy()
        df_dash['percent_change'] = df_dash['percent_change'] * 100
        df_dash = df_dash.sort_values(by="percent_change", ascending=False)
        
        log("Tính toán dữ liệu bảng tính thành công! Đang tiến hành tạo đồ thị Plotly...")

        # Tạo bảng HTML
        html_table = df_dash[['name', 'percent_change', 'volume_ratio']].to_html(
            classes='table table-dark table-striped text-center table-bordered', 
            index=False, 
            float_format=lambda x: f"{x:.2f}"
        )

        # Vẽ đồ thị
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
            paper_bgcolor='#212529', plot_bgcolor='#2b3035',
            xaxis=dict(tickangle=45, tickfont=dict(color="#ffffff"), gridcolor="#495057"),
            yaxis=dict(title="Biến động giá (%)", titlefont=dict(color="#ffffff"), tickfont=dict(color="#ffffff"), ticksuffix="%", gridcolor="#495057"),
            yaxis2=dict(title="Tỷ lệ KL/TBKL21 (Lần)", titlefont=dict(color="#ffffff"), tickfont=dict(color="#ffffff"), overlaying='y', side='right', showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#ffffff")),
            margin=dict(l=50, r=50, t=50, b=120)
        )
        html_charts = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        log("Tạo biểu đồ Plotly thành công!")

    except Exception as e:
        # Ghi nhận dấu vết lỗi chi tiết (Traceback) nếu bị sập giữa chừng
        error_traceback = traceback.format_exc()
        log(f"HỆ THỐNG GẶP LỖI NẶNG: {str(e)}")

    # Gộp toàn bộ log để hiển thị trên web
    logs_html = "<br>".join(debug_logs)
    
    # 4. Xuất file index.html đặc biệt chứa cả log và bảng số liệu
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Debug Hệ Thống Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #121416; color: #ffffff; padding: 20px; }}
            .card {{ background-color: #212529; border: 1px solid #343a40; margin-bottom: 20px; }}
            .card-header {{ background-color: #2b3035; color: #fff; font-weight: bold; }}
            pre {{ background-color: #1a1d20; color: #ffc107; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <h2 class="text-center text-warning fw-bold mb-4">TRANG GHI LOG VÀ KIỂM TRA BẢNG TÍNH NGÀNH</h2>
            <p class="text-center text-secondary">Cập nhật lúc: {now_dt.strftime('%d/%m/%Y %H:%M:%S')}</p>

            <div class="card">
                <div class="card-header text-info">📑 LOG TIẾN TRÌNH CHẠY (DEBUG LOGS)</div>
                <div class="card-body">
                    <div style="font-family: monospace; font-size: 14px; line-height: 1.6; max-height: 300px; overflow-y: auto; background: #1a1d20; padding: 15px; border-radius: 5px;">
                        {logs_html}
                    </div>
                </div>
            </div>

            {f'''<div class="card border-danger">
                <div class="card-header text-danger">⚠️ CHI TIẾT LỖI HỆ THỐNG (TRACEBACK ERROR)</div>
                <div class="card-body">
                    <pre>{error_traceback}</pre>
                </div>
            </div>''' if error_traceback else ''}

            <div class="card">
                <div class="card-header text-success">📊 BIỂU ĐỒ SONG TRỤC DIỄN BIẾN NGÀNH</div>
                <div class="card-body p-1">{html_charts}</div>
            </div>

            <div class="card">
                <div class="card-header text-warning">📋 BẢNG KẾT QUẢ TÍNH TOÁN TRUNG BÌNH CÁC NGÀNH</div>
                <div class="card-body table-responsive">{html_table}</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("=== ĐÃ GHI TOÀN BỘ KẾT QUẢ VÀ LOG RA FILE INDEX.HTML ===")

if __name__ == "__main__":
    main()
