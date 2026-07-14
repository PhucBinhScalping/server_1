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

# Khởi tạo User-Agent toàn cục
global head
head = {"User-Agent": random_user()}

# =====================================================================
# CÁC HÀM CÀO DỮ LIỆU GỐC CỦA BẠN (Đã sửa lỗi và bỏ xlwings)
# =====================================================================

def dau_thau_thi_truong_mo():
    try:
        url_2 = 'https://www.sbv.gov.vn/webcenter/portal/vi/menu/trangchu/hdtttt'
        response2 = requests.get(url_2, allow_redirects=True, headers=head, timeout=15)
        df4 = pd.read_html(response2.text)[0][9:13]
        df = df4.iloc[:, :4]
        df.columns = df.iloc[0]
        df = df[1:]
        df['Lãi suất trúng thầu (%/năm)'] = (df['Lãi suất trúng thầu (%/năm)'].str.replace('%', '').astype(float)) / 100
        return df.set_index(df.columns[0])
    except Exception as e:
        print(f"Lỗi hàm dau_thau_thi_truong_mo: {e}")
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
    except Exception as e:
        print(f"Lỗi hàm gia_vang_24money: {e}")
        return pd.DataFrame()

def get_PE_PB_vnindex():
    try:
        url = 'https://s.cafef.vn/Ajax/PageNew/FinanceData/GetDataChartPE.ashx'
        r = requests.get(url, headers=head, timeout=15)
        data = pd.DataFrame([r.json()['Data']['NowDataFinance'], r.json()['Data']['PastDataFinance']]).T
        data.columns = ['Hiện tại', 'Năm trước']
        return data.apply(pd.to_numeric, errors='coerce').reindex(['PE', 'PB', 'ROA', 'ROE', 'MaketCap'])
    except Exception as e:
        print(f"Lỗi hàm get_PE_PB_vnindex: {e}")
        return pd.DataFrame()

def get_index_stock_world():
    try:
        url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
        r = requests.get(url, headers=head, timeout=15)
        df = pd.DataFrame(r.json()['data']['world_stock'])[['name', 'last_price', 'change_price', 'change_percent']]
        df['change_percent'] = pd.to_numeric(df['change_percent']) / 100
        return df
    except Exception as e:
        print(f"Lỗi hàm get_index_stock_world: {e}")
        return pd.DataFrame()

def get_data_cp_vn30():
    todate = datetime.now()
    N = 1
    while N <= 5:
        try:
            fromdate = todate - timedelta(days=N)
            url2 = f"https://s.cafef.vn/Ajax/PageNew/DataGDNN/GDNuocNgoai.ashx?TradeCenter=VN30&Date={fromdate.strftime('%Y-%m-%d')}"
            r2 = requests.get(url2, headers=head, timeout=15)
            df = pd.DataFrame(r2.json()['Data']['ListDataNN'])
            if not df.empty:
                return df[['Symbol']].sort_values(by='Symbol').set_index('Symbol')
            N += 2
        except Exception as e:
            print(f"Lỗi phát sinh tại hàm VN30: {e}")
            N += 1
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
                response.raise_for_status()
                data = response.json()
                if key == 'hn30':
                    df_key = pd.DataFrame(data['Data']['Data'])[['Ngay', 'GiaDieuChinh', 'GiaTriKhopLenh', 'GtThoaThuan']][1:2]
                    df_key['value'] = df_key['GiaTriKhopLenh']
                    df_key[['value']] = round(df_key[['value']].apply(pd.to_numeric, errors='coerce') / 1000000000, 2)
                else:
                    df_key = pd.DataFrame(data['data'][1]['data'])[-1:]
                data_frames[key] = df_key
            except Exception as e:
                print(f"Error fetching data for {key}: {e}")
                data_frames[key] = pd.DataFrame()
        
        # ĐÃ SỬA LỖI ĐOẠN NÀY BẰNG CÁCH BỌC HÀM list() ĐỂ HỢP LỆ VỚI PYTHON 3
        list_data = [
            ('VNINDEX', round(list(data_frames['vni']['total_value_traded'].values)[0], 2) if not data_frames['vni'].empty else 0),
            ('VN30', round(list(data_frames['vn30']['total_value_traded'].values)[0], 2) if not data_frames['vn30'].empty else 0),
            ('HNX', round(list(data_frames['hnx']['total_value_traded'].values)[0], 2) if not data_frames['hnx'].empty else 0),
            ('HNX30', round(list(data_frames['hn30']['value'].values)[0], 2) if not data_frames['hn30'].empty else 0),
            ('UPCOM', round(list(data_frames['upcom']['total_value_traded'].values)[0], 2) if not data_frames['upcom'].empty else 0)
        ]
        
        df_t = pd.DataFrame(list_data, columns=['name', 'value_2'])
        df_t['value_2'] = pd.to_numeric(df_t['value_2'], errors='coerce')
        
        result_df = pd.merge(df, df_t, on='name')
        result_df['value/value'] = ((result_df['value'] - result_df['value_2']) / result_df['value_2'])
        
        data = result_df[['name', 'change', 'index', 'percent', 'volume', 'value', 'value/value']]
        return data.set_index('name')
    except Exception as e:
        print(f"Lỗi hàm get_data_index: {e}")
        return pd.DataFrame()

# =====================================================================
# CÁC HÀM VỀ CỔ PHIẾU VÀ VĨ MÔ DÙNG THƯ VIỆN RSTOCKVN CỦA BẠN
# =====================================================================
def info_company(symbol):
    return rpv.get_info_cp(symbol)

def momentum_ck(symbol):
    return rpv.momentum_ck(symbol)

def CW_info(symbol):
    try:
        url2 = f'https://finance.vietstock.vn/chung-khoan-phai-sinh/{symbol}/cw-tong-quan.htm'
        r = requests.get(url2, headers=head, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        ds = soup.find(class_="table table-hover")
        df = pd.read_html(ds.prettify())[0]
        df.rename(columns={0: 'CW', 1: f'{symbol[1:].upper()}'}, inplace=True)
        return df
    except Exception as e:
        print(f"Lỗi hàm CW_info cho {symbol}: {e}")
        return pd.DataFrame()

def tinh_du_lieu_cp(symbol):
    try:
        todate = datetime.now()
        fromdate = todate - timedelta(days=200)
        fdate = fromdate.strftime('%Y-%m-%d')
        tdate = todate.strftime('%Y-%m-%d')

        url = f'https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{fdate}~date:lte:{tdate}&size=100000&page=1'
        r = requests.get(url, headers=head, timeout=15)
        data = pd.DataFrame(r.json()['data'])

        data.rename(columns={
            'nmVolume': 'KLGD Khớp lệnh',
            'nmValue': 'GTGD Khớp lệnh',
            'ptVolume': 'KLGD Thỏa thuận',
            'ptValue': 'GTGD Thỏa thuận',
            'change': 'tăng/giảm',
            'pctChange': '% tăng/giảm'
        }, inplace=True)

        data['volumn'] = data['KLGD Khớp lệnh'] + data['KLGD Thỏa thuận']

        first_row = data.iloc[0]
        gia_close = pd.to_numeric(first_row['close'], errors='coerce')
        KL1000 = pd.to_numeric(first_row['volumn'], errors='coerce') / 1000
        BD_gia = pd.to_numeric(first_row['% tăng/giảm'], errors='coerce') / 100

        KLGD_KLTB21_mean = pd.to_numeric(data['volumn'].iloc[:22].mean(), errors='coerce')
        KLTB_KLTB21 = pd.to_numeric(first_row['volumn'], errors='coerce') / KLGD_KLTB21_mean

        close_mean_5 = pd.to_numeric(data['close'].iloc[:6].mean(), errors='coerce')
        close_mean_21 = pd.to_numeric(data['close'].iloc[:22].mean(), errors='coerce')
        gia_tbgia5 = close_mean_5 / close_mean_21

        KL_KLTB5_mean = pd.to_numeric(data['volumn'].iloc[:6].mean(), errors='coerce')
        KL_KLTB5 = pd.to_numeric(first_row['volumn'], errors='coerce') / KL_KLTB5_mean

        close_60 = pd.to_numeric(data['close'].iloc[:60], errors='coerce')
        day2t = close_60.min()
        dinh2t = close_60.max()
        dinh_day = (dinh2t - day2t) / day2t
        giam_sdinh = (gia_close - dinh2t) / dinh2t
        tang_sday = (gia_close - day2t) / day2t

        return {
            "Mã CP": symbol.upper(), "Giá Close": gia_close, "KL / 1000": KL1000, "Biến động giá": BD_gia,
            "KLTB/KLTB21": KLTB_KLTB21, "Giá/TB Giá 5": gia_tbgia5, "KL/KLTB5": KL_KLTB5,
            "Đỉnh Đáy 60 ngày": dinh_day, "Đáy 60 ngày": day2t, "Đỉnh 60 ngày": dinh2t,
            "Tăng so với Đáy": tang_sday, "Giảm so với Đỉnh": giam_sdinh
        }
    except Exception as e:
        print(f"Lỗi tính toán dữ liệu cổ phiếu {symbol}: {e}")
        return {}

def get_price_historical_vnd(symbol, fromdate, todate):
    try:
        fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
        fdate, tdate = fromdate.strftime('%Y-%m-%d'), todate.strftime('%Y-%m-%d')
        url = f'https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{fdate}~date:lte:{tdate}&size=100000&page=1'
        
        r = requests.get(url, headers=head, timeout=15)
        df = pd.DataFrame(r.json()['data'])
        data = df[['code', 'date', 'open', 'high', 'low', 'close', 'nmVolume', 'nmValue', 'ptVolume', 'ptValue', 'change', 'pctChange']].copy()
        data.rename(columns={'nmVolume': 'KLGD Khớp lệnh', 'nmValue': 'GTGD Khớp lệnh', 'ptVolume': 'KLGD Thỏa thuận', 'ptValue': 'GTGD Thỏa thuận', 'change': 'tăng/giảm', 'pctChange': '% tăng/giảm'}, inplace=True)
        data['% tăng/giảm'] = data['% tăng/giảm'].astype(str) + '%'
        return data
    except Exception as e:
        print(f"Lỗi lịch sử giá VNDirect: {e}")
        return pd.DataFrame()

def list_company():
    return rpv.list_company()

def giao_dich_tu_doanh(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.giao_dich_tu_doanh(fromdate, todate)

def report_finance_vnd(symbol, type, year):
    return rpv.report_finance_vnd(symbol, type, year)

def nuoc_ngoai_mua_ban(tradecenter, fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.nuoc_ngoai_mua_ban(tradecenter, fromdate, todate)

def rsi_vietstock(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.rsi_vietstock(fromdate, todate)

def macd_vietstock(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.macd_vietstock(fromdate, todate)

def solieu_XNK_vietstock(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.solieu_XNK_vietstock(fromdate, todate)

def solieu_FDI_vietstock(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.solieu_FDI_vietstock(fromdate, todate)

def tygia_vietstock(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.tygia_vietstock(fromdate, todate)

def solieu_tindung_vietstock(fromdate, todate):
    fromdate, todate = pd.to_datetime(fromdate, dayfirst=True), pd.to_datetime(todate, dayfirst=True)
    return rpv.solieu_tindung_vietstock(fromdate, todate)

def solieu_GDP_vietstock(fromyear, fromQ, toyear, toQ):
    return rpv.solieu_GDP_vietstock(int(fromyear), int(fromQ), int(toyear), int(toQ))

# =====================================================================
# HÀM ĐIỀU KHIỂN CHÍNH: TỰ ĐỘNG CHẠY VÀ SINH GIAO DIỆN WEB HTML
# =====================================================================
def main():
    print("=== BẮT ĐẦU QUY TRÌNH THỐNG KÊ DỮ LIỆU TỰ ĐỘNG ===")
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Gọi các hàm lấy dữ liệu chỉ số chính
    df_index = get_data_index()
    df_pe = get_PE_PB_vnindex()
    df_sbv = dau_thau_thi_truong_mo()
    df_vang = gia_vang_24money()
    df_world = get_index_stock_world()

    # Phân tích thử nghiệm 3 mã cổ phiếu điểm nhấn làm mẫu hiển thị
    list_ma = ["HPG", "SSI", "VNM"]
    data_points = []
    for ma in list_ma:
        res = tinh_du_lieu_cp(ma)
        if res:
            data_points.append(res)
    df_cp_analysis = pd.DataFrame(data_points) if data_points else pd.DataFrame()

    # Chuyển đổi dữ liệu sang bảng dạng HTML đẹp mắt (Dùng Bootstrap class)
    html_index = df_index.to_html(classes='table table-bordered table-striped text-center table-info') if not df_index.empty else "<p>Không có dữ liệu</p>"
    html_pe = df_pe.to_html(classes='table table-bordered table-dark') if not df_pe.empty else "<p>Không có dữ liệu</p>"
    html_sbv = df_sbv.to_html(classes='table table-bordered text-center table-success') if not df_sbv.empty else "<p>Không có dữ liệu</p>"
    html_vang = df_vang.to_html(classes='table table-striped table-hover table-warning') if not df_vang.empty else "<p>Không có dữ liệu</p>"
    html_world = df_world.to_html(classes='table table-striped table-secondary') if not df_world.empty else "<p>Không có dữ liệu</p>"
    html_cp_analysis = df_cp_analysis.to_html(classes='table table-striped text-center table-light', index=False) if not df_cp_analysis.empty else "<p>Không có dữ liệu</p>"

    # Xây dựng bộ khung giao diện trang web HTML
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hệ thống Thống kê Dữ liệu Chứng khoán</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #f8f9fa; font-family: 'Segoe UI', Arial, sans-serif; }}
            .card {{ border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 25px; }}
            .card-header {{ font-weight: bold; font-size: 1.1rem; }}
        </style>
    </head>
    <body>
        <div class="container my-5">
            <div class="text-center mb-5">
                <h1 class="text-primary fw-bold">BÁO CÁO THỊ TRƯỜNG CHỨNG KHOÁN TỰ ĐỘNG</h1>
                <p class="text-muted">Hệ thống vận hành ngầm bằng GitHub Actions | Cập nhật lúc: <span class="badge bg-dark">{now_str}</span></p>
            </div>

            <div class="card">
                <div class="card-header bg-primary text-white">1. Chỉ số tổng quan các Sàn Giao Dịch Việt Nam</div>
                <div class="card-body table-responsive">{html_index}</div>
            </div>

            <div class="card">
                <div class="card-header bg-dark text-white">2. Định giá P/E, P/B toàn bộ thị trường VNINDEX</div>
                <div class="card-body table-responsive">{html_pe}</div>
            </div>

            <div class="row">
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header bg-success text-white">3. Đấu thầu thị trường mở (Ngân hàng Nhà nước SBV)</div>
                        <div class="card-body table-responsive">{html_sbv}</div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header bg-warning text-dark">4. Biến động giá vàng thế giới & trong nước (24hmoney)</div>
                        <div class="card-body table-responsive">{html_vang}</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header bg-secondary text-white">5. Chỉ số thị trường chứng khoán thế giới lớn</div>
                <div class="card-body table-responsive">{html_world}</div>
            </div>

            <div class="card">
                <div class="card-header bg-info text-dark">6. Bảng dữ liệu định lượng, Đỉnh/Đáy các cổ phiếu điểm nhấn (Mẫu: HPG, SSI, VNM)</div>
                <div class="card-body table-responsive">{html_cp_analysis}</div>
            </div>

            <footer class="text-center my-4 text-muted small">
                Báo cáo tự động được lưu trữ hoàn toàn miễn phí trên nền tảng GitHub Pages.
            </footer>
        </div>
    </body>
    </html>
    """

    # Ghi nội dung thành file trang web tĩnh index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("=== HOÀN THÀNH BÁO CÁO! ĐÃ XUẤT FILE INDEX.HTML ===")

if __name__ == "__main__":
    main()
