import datetime as dt
import pandas as pd
from datetime import date, datetime, timedelta
import requests
import time
from user_agent import random_user
import RStockvn as rpv
from bs4 import BeautifulSoup
import json
import html5lib
import openpyxl
import plotly.express as px
import plotly.io as pio

# Khởi tạo User-Agent toàn cục để tránh bị chặn
global head
head = {"User-Agent": random_user()}

# =====================================================================
# CÁC HÀM CÀO DỮ LIỆU CHỈ SỐ VÀ THỊ TRƯỜNG CHÍNH
# =====================================================================

def dau_thau_thi_truong_mo():
    try:
        url_2 = 'https://www.sbv.gov.vn/webcenter/portal/vi/menu/trangchu/hdtttt'
        response2 = requests.get(url_2, allow_redirects=True, headers=head, timeout=15)
        tables = pd.read_html(response2.text)
        if not tables or len(tables) == 0:
            return pd.DataFrame()
        df4 = tables[0][9:13]
        df = df4.iloc[:, :4]
        df.columns = df.iloc[0]
        df = df[1:]
        if 'Lãi suất trúng thầu (%/năm)' in df.columns:
            df['Lãi suất trúng thầu (%/năm)'] = (df['Lãi suất trúng thầu (%/năm)'].str.replace('%', '').astype(float)) / 100
        return df.set_index(df.columns[0])
    except:
        return pd.DataFrame()

def gia_vang_24money():
    try:
        url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
        r = requests.get(url, headers=head, timeout=15)
        data = r.json()['data']['gold_price']
        df = pd.DataFrame(data)[['Last', 'footer', 'text', 'Percent', 'change', 'symbol', 'extra_name']].assign(
            change=lambda x: pd.to_numeric(x['change'], errors='coerce'),
            Percent=lambda x: pd.to_numeric(x['Percent'].str.replace('%', '').str.strip(), errors='coerce') / 100,
            Last=lambda x: x['Last'].str.replace('N', '').str.strip()
        )
        return df
    except:
        return pd.DataFrame()

def get_PE_PB_vnindex():
    try:
        url = 'https://s.cafef.vn/Ajax/PageNew/FinanceData/GetDataChartPE.ashx'
        r = requests.get(url, headers=head, timeout=15)
        data = pd.DataFrame([r.json()['Data']['NowDataFinance'], r.json()['Data']['PastDataFinance']]).T
        data.columns = ['Hiện tại', 'Năm trước']
        return data.apply(pd.to_numeric, errors='coerce').reindex(['PE', 'PB', 'ROA', 'ROE', 'MaketCap'])
    except:
        return pd.DataFrame()

def get_index_stock_world():
    try:
        url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
        r = requests.get(url, headers=head, timeout=15)
        df = pd.DataFrame(r.json()['data']['world_stock'])[['name', 'last_price', 'change_price', 'change_percent']]
        df['change_percent'] = pd.to_numeric(df['change_percent']) / 100
        return df
    except:
        return pd.DataFrame()

def get_data_index():
    try:
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', headers=head, timeout=15)
        results_vni = json.loads(re_vni_url.text)
        results_vni[0]['name'] = 'HNX'
        results_vni[3]['name'] = 'UPCOM'
        df = pd.DataFrame([results_vni[1], results_vni[4], results_vni[0], results_vni[2], results_vni[3]])
        
        df['change'] = df['change'].apply(pd.to_numeric, errors='coerce')
        df['percent'] = df['percent'].apply(pd.to_numeric, errors='coerce') / 100
        df['value'] = df['value'].str.replace(',', '').astype(float)
        
        urls = {
            'vni': 'https://api-finance-t19.24hmoney.vn/v1/ios/stock/statistic-investor-history?device_id=web1747788dm3nzyfiwaqk6wgut1kk3pusmaejn91n403710&symbol=10',
            'vn30': 'https://api-finance-t19.24hmoney.vn/v1/web/indices/trading-compare-daily?code=11',
            'hnx': 'https://api-finance-t19.24hmoney.vn/v1/web/indices/trading-compare-daily?code=02',
            'upcom': 'https://api-finance-t19.24hmoney.vn/v1/web/indices/trading-compare-daily?code=03',
            'hn30': 'https://s.cafef.vn/Ajax/PageNew/DataHistory/PriceHistory.ashx?Symbol=HNX30-INDEX&StartDate=&EndDate=&PageIndex=1&PageSize=20'
        }
        
        data_frames = {}
        for key, url in urls.items():
            try:
                response = requests.get(url, headers=head, timeout=15)
                data = response.json()
                if key == 'hn30':
                    df_key = pd.DataFrame(data['Data']['Data'])[['Ngay', 'GiaDieuChinh', 'GiaTriKhopLenh', 'GtThoaThuan']][1:2]
                    df_key['value'] = df_key['GiaTriKhopLenh']
                    df_key[['value']] = round(df_key[['value']].apply(pd.to_numeric, errors='coerce') / 1000000000, 2)
                else:
                    df_key = pd.DataFrame(data['data'][1]['data'])[-1:]
                data_frames[key] = df_key
            except:
                data_frames[key] = pd.DataFrame()
        
        def safe_get_value(df_target, col_name):
            if df_target is not None and not df_target.empty and col_name in df_target.columns:
                try:
                    return round(float(df_target[col_name].iloc[0]), 2)
                except:
                    return 0
            return 0

        list_data = [
            ('VNINDEX', safe_get_value(data_frames.get('vni'), 'total_value_traded')),
            ('VN30', safe_get_value(data_frames.get('vn30'), 'total_value_traded')),
            ('HNX', safe_get_value(data_frames.get('hnx'), 'total_value_traded')),
            ('HNX30', safe_get_value(data_frames.get('hn30'), 'value')),
            ('UPCOM', safe_get_value(data_frames.get('upcom'), 'total_value_traded'))
        ]
        
        df_t = pd.DataFrame(list_data, columns=['name', 'value_2'])
        df_t['value_2'] = pd.to_numeric(df_t['value_2'], errors='coerce')
        
        result_df = pd.merge(df, df_t, on='name')
        result_df['value/value'] = ((result_df['value'] - result_df['value_2']) / result_df['value_2'])
        
        data = result_df[['name', 'change', 'index', 'percent', 'volume', 'value', 'value/value']]
        return data.set_index('name')
    except:
        return pd.DataFrame()

# =====================================================================
# HÀM LOGIC CÀO DỮ LIỆU TỪNG MÃ CỔ PHIẾU
# =====================================================================

def tinh_du_lieu_cp(symbol):
    try:
        todate = datetime.now()
        fromdate = todate - timedelta(days=200)
        fdate = fromdate.strftime('%Y-%m-%d')
        tdate = todate.strftime('%Y-%m-%d')

        url = f'https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{fdate}~date:lte:{tdate}&size=100000&page=1'
        r = requests.get(url, headers=head, timeout=15)
        
        if r.status_code != 200 or 'data' not in r.json() or len(r.json()['data']) == 0:
            return None

        data = pd.DataFrame(r.json()['data'])
        data['volumn'] = pd.to_numeric(data['nmVolume'], errors='coerce') + pd.to_numeric(data['ptVolume'], errors='coerce')

        first_row = data.iloc[0]
        gia_close = pd.to_numeric(first_row['close'], errors='coerce')
        BD_gia = pd.to_numeric(first_row['pctChange'], errors='coerce') / 100

        KLGD_KLTB21_mean = pd.to_numeric(data['volumn'].iloc[:22].mean(), errors='coerce')
        KLTB_KLTB21 = pd.to_numeric(first_row['volumn'], errors='coerce') / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0

        close_60 = pd.to_numeric(data['close'].iloc[:60], errors='coerce')
        day2t = close_60.min()
        dinh2t = close_60.max()
        tang_sday = (gia_close - day2t) / day2t if day2t > 0 else 0

        return {
            "Mã CP": symbol.upper(),
            "Giá Close": gia_close,
            "Biến động giá": BD_gia,
            "KLTB/KLTB21": KLTB_KLTB21,
            "Tăng so với Đáy": tang_sday
        }
    except:
        return None

# =====================================================================
# HÀM XỬ LÝ 1000 MÃ TỪ EXCEL, TÍNH TRUNG BÌNH & TẠO BIỂU ĐỒ DASHBOARD
# =====================================================================

def xu_ly_excel_va_ve_bieu_do():
    file_path = "THONG_KE_VNINDEX_VN30.xlsm"
    try:
        # 1. Đọc file Excel tự động
        xl = pd.ExcelFile(file_path)
        danh_sach_nganh = {}
        
        # Lấy danh sách mã từ các sheet ngành (Bỏ qua sheet Dashboard)
        for name in xl.sheet_names:
            if name.lower() not in ["dashboard", "index", "summary"]:
                df_sheet = xl.parse(name)
                if not df_sheet.empty:
                    # Lấy cột đầu tiên chứa mã cổ phiếu
                    mas = df_sheet.iloc[:, 0].dropna().astype(str).str.strip().str.upper().tolist()
                    # Chỉ lọc các mã hợp lệ (độ dài 3 ký tự)
                    mas = [m for m in mas if len(m) == 3]
                    if mas:
                        danh_sach_nganh[name] = mas

        print(f"--> Tìm thấy {len(danh_sach_nganh)} nhóm ngành trong file Excel.")
        
        # 2. Vòng lặp tự động chạy tính toán cho tất cả các mã phát hiện được
        data_all_nganh = []
        
        for nganh, ds_ma in danh_sach_nganh.items():
            print(f"Đang xử lý ngành: {nganh} ({len(ds_ma)} mã)...")
            tong_bd = 0
            tong_kltb = 0
            count = 0
            
            for ma in ds_ma:
                res = tinh_du_lieu_cp(ma)
                if res:
                    tong_bd += res["Biến động giá"]
                    tong_kltb += res["KLTB/KLTB21"]
                    count += 1
                # Lệnh nghỉ cực kỳ quan trọng! 0.15s giúp tránh bị VNDirect chặn IP
                time.sleep(0.15)
            
            # Tính toán trung bình ngành tương ứng như công thức Excel của bạn
            if count > 0:
                data_all_nganh.append({
                    "Nhóm Ngành": nganh,
                    "Biến động TB (%)": round((tong_bd / count) * 100, 2),
                    "Thanh khoản TB (Lần)": round(tong_kltb / count, 2)
                })

        df_dashboard = pd.DataFrame(data_all_nganh)
        
        if df_dashboard.empty:
            return "<p class='text-danger'>Không có dữ liệu tổng hợp ngành.</p>", ""

        # 3. Vẽ biểu đồ 1: Biến động giá trung bình ngành (Dùng Plotly thay thế Excel)
        fig_price = px.bar(df_dashboard, x='Nhóm Ngành', y='Biến động TB (%)',
                           title="Biến Động Giá Trung Bình Theo Nhóm Ngành (%)",
                           text_auto='.2f', color='Biến động TB (%)',
                           color_continuous_scale='RdYlGn')
        div_chart_price = pio.to_html(fig_price, full_html=False, include_plotlyjs='cdn')

        # Vẽ biểu đồ 2: Thanh khoản trung bình so với 21 phiên
        fig_vol = px.bar(df_dashboard, x='Nhóm Ngành', y='Thanh khoản TB (Lần)',
                         title="Tỷ Lệ Thanh Khoản Hiện Tại / TB 21 Phiên Theo Ngành",
                         text_auto='.2f', color='Thanh khoản TB (Lần)',
                         color_continuous_scale='Blues')
        div_chart_vol = pio.to_html(fig_vol, full_html=False, include_plotlyjs='cdn')

        # Chuyển bảng số liệu tổng hợp ngành thành bảng HTML
        html_table_nganh = df_dashboard.to_html(classes='table table-hover table-bordered text-center', index=False)

        return html_table_nganh, div_chart_price + "<br>" + div_chart_vol

    except Exception as e:
        print(f"Lỗi hệ thống xử lý Excel: {e}")
        return f"<p class='text-danger'>Lỗi xử lý tệp Excel: {e}</p>", ""

# =====================================================================
# HÀM ĐIỀU KHIỂN CHÍNH (MAIN EXECUTOR)
# =====================================================================

def main():
    print("=== BẮT ĐẦU HỆ THỐNG XỬ LÝ 1000 MÃ CỔ PHIẾU TỰ ĐỘNG ===")
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Lấy dữ liệu vĩ mô và chỉ số chính
    df_index = get_data_index()
    df_pe = get_PE_PB_vnindex()
    df_sbv = dau_thau_thi_truong_mo()
    df_vang = gia_vang_24money()
    df_world = get_index_stock_world()

    # Gọi hàm xử lý quét 1000 mã từ tệp Excel Excel
    html_table_nganh, html_dashboard_charts = xu_ly_excel_va_ve_bieu_do()

    # Đóng gói dữ liệu sang định dạng HTML
    html_index = df_index.to_html(classes='table table-bordered table-striped text-center table-info') if not df_index.empty else "<p>Không có dữ liệu</p>"
    html_pe = df_pe.to_html(classes='table table-bordered table-dark') if not df_pe.empty else "<p>Không có dữ liệu</p>"
    html_sbv = df_sbv.to_html(classes='table table-bordered text-center table-success') if not df_sbv.empty else "<p class='text-muted'>Không tìm thấy dữ liệu thị trường mở.</p>"
    html_vang = df_vang.to_html(classes='table table-striped table-hover table-warning') if not df_vang.empty else "<p>Không có dữ liệu</p>"
    html_world = df_world.to_html(classes='table table-striped table-secondary') if not df_world.empty else "<p>Không có dữ liệu</p>"

    # Xây dựng bộ khung giao diện trang web HTML Dashboard hoàn chỉnh
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thống Kê Thị Trường & Dashboard Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #f4f6f9; font-family: 'Segoe UI', Arial, sans-serif; }}
            .card {{ border: none; box-shadow: 0 4px 8px rgba(0,0,0,0.05); margin-bottom: 30px; }}
            .card-header {{ font-weight: bold; font-size: 1.15rem; }}
            .dashboard-title {{ color: #1e3d59; font-weight: 800; text-shadow: 1px 1px 2px rgba(0,0,0,0.05); }}
        </style>
    </head>
    <body>
        <div class="container my-5">
            <div class="text-center mb-5">
                <h1 class="dashboard-title">HỆ THỐNG ĐỒNG BỘ DASHBOARD CHỨNG KHOÁN</h1>
                <p class="text-muted">Đang xử lý >1000 mã từ file Excel | Cập nhật lần cuối: <span class="badge bg-danger">{now_str}</span></p>
            </div>

            <div class="card border-primary">
                <div class="card-header bg-primary text-white">📈 DASHBOARD: BIỂU ĐỒ BÁO CÁO CÁC NHÓM NGÀNH (Thay thế đồ thị Excel)</div>
                <div class="card-body">
                    {html_dashboard_charts}
                </div>
            </div>

            <div class="card">
                <div class="card-header bg-info text-dark">📋 Bảng Tổng Hợp Số Liệu Trung Bình Các Nhóm Ngành</div>
                <div class="card-body table-responsive">
                    {html_table_nganh}
                </div>
            </div>

            <div class="card">
                <div class="card-header bg-dark text-white">1. Chỉ số tổng quan các Sàn Giao Dịch Việt Nam</div>
                <div class="card-body table-responsive">{html_index}</div>
            </div>

            <div class="row">
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header bg-secondary text-white">2. Định giá P/E, P/B toàn bộ VNINDEX</div>
                        <div class="card-body table-responsive">{html_pe}</div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header bg-success text-white">3. Đấu thầu thị trường mở (SBV)</div>
                        <div class="card-body table-responsive">{html_sbv}</div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header bg-warning text-dark">4. Biến động giá vàng thế giới & trong nước</div>
                        <div class="card-body table-responsive">{html_vang}</div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header bg-dark text-white">5. Chỉ số chứng khoán thế giới</div>
                        <div class="card-body table-responsive">{html_world}</div>
                    </div>
                </div>
            </div>

            <footer class="text-center my-4 text-muted small">
                Hệ thống chạy hoàn toàn tự động dựa trên nền tảng GitHub Actions & GitHub Pages.
            </footer>
        </div>
    </body>
    </html>
    """

    # Ghi đè file kết quả tĩnh index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("=== ĐÃ XUẤT FILE DASHBOARD THÀNH CÔNG (INDEX.HTML) ===")

if __name__ == "__main__":
    main()
