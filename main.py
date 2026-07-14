import datetime as dt
import pandas as pd
from datetime import date, datetime, timedelta, timezone
import requests
import json
import openpyxl
import plotly.express as px
import plotly.io as pio
from user_agent import random_user
from concurrent.futures import ThreadPoolExecutor

# Khởi tạo User-Agent toàn cục để tránh bị chặn
global head
head = {"User-Agent": random_user()}

# =====================================================================
# HÀM TÍNH TOÁN DỮ LIỆU CỔ PHIẾU GỐC CỦA BẠN (ĐÃ THÊM BẢO VỆ LỖI)
# =====================================================================
def tinh_du_lieu_cp(symbol):
    try:
        # Thiết lập thời gian
        tz_vn = timezone(timedelta(hours=7))
        todate = datetime.now(tz_vn)
        fromdate = todate - timedelta(days=200)
        fdate = fromdate.strftime('%Y-%m-%d')
        tdate = todate.strftime('%Y-%m-%d')

        # API URL và header
        url = f'https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol.upper()}~date:gte:{fdate}~date:lte:{tdate}&size=100000&page=1' 
        payload = {}

        # Gọi API và chuyển đổi dữ liệu
        r = requests.get(url, headers=head, data=payload, timeout=10)
        if r.status_code != 200 or 'data' not in r.json() or len(r.json()['data']) == 0:
            return None
            
        data = pd.DataFrame(r.json()['data'])

        # Đổi tên cột cho dễ hiểu và thêm cột 'volumn'
        data.rename(columns={
            'nmVolume': 'KLGD Khớp lệnh',
            'nmValue': 'GTGD Khớp lệnh',
            'ptVolume': 'KLGD Thỏa thuận',
            'ptValue': 'GTGD Thỏa thuận',
            'change': 'tăng/giảm',
            'pctChange': '% tăng/giảm'
        }, inplace=True)

        data['volumn'] = pd.to_numeric(data['KLGD Khớp lệnh'], errors='coerce').fillna(0) + pd.to_numeric(data['KLGD Thỏa thuận'], errors='coerce').fillna(0)

        # Lấy các giá trị cần thiết từ DataFrame
        first_row = data.iloc[0]
        gia_close = pd.to_numeric(first_row['close'], errors='coerce')
        KL1000 = pd.to_numeric(first_row['volumn'], errors='coerce') / 1000
        BD_gia = pd.to_numeric(first_row['% tăng/giảm'], errors='coerce') / 100

        # Tính toán các giá trị cần thiết
        KLGD_KLTB21_mean = pd.to_numeric(data['volumn'].iloc[:22].mean(), errors='coerce')
        KLTB_KLTB21 = pd.to_numeric(first_row['volumn'], errors='coerce') / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0

        close_mean_5 = pd.to_numeric(data['close'].iloc[:6].mean(), errors='coerce')
        close_mean_21 = pd.to_numeric(data['close'].iloc[:22].mean(), errors='coerce')
        gia_tbgia5 = close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0

        KL_KLTB5_mean = pd.to_numeric(data['volumn'].iloc[:6].mean(), errors='coerce')
        KL_KLTB5 = pd.to_numeric(first_row['volumn'], errors='coerce') / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0

        # Tính đỉnh và đáy của 60 ngày đầu
        close_60 = pd.to_numeric(data['close'].iloc[:60], errors='coerce')
        day2t = close_60.min()
        dinh2t = close_60.max()
        dinh_day = (dinh2t - day2t) / day2t if day2t > 0 else 0
        giam_sdinh = (gia_close - dinh2t) / dinh2t if dinh2t > 0 else 0
        tang_sday = (gia_close - day2t) / day2t if day2t > 0 else 0

        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, day2t, dinh2t, tang_sday, giam_sdinh]
    except Exception:
        return None

# Hàm bọc để chạy đa luồng
def worker(task):
    row, sym = task
    res = tinh_du_lieu_cp(sym)
    return row, sym, res

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
        return df[['name', 'change', 'index', 'percent', 'volume', 'value']]
    except Exception:
        return pd.DataFrame()

# =====================================================================
# TIẾN TRÌNH CHÍNH
# =====================================================================
def main():
    print("=== BẮT ĐẦU TÍNH TOÁN THEO HÀM GỐC (ĐA LUỒNG TỐC ĐỘ CAO) ===")
    file_path = "THONG_KE_VNINDEX_VN30.xlsm"
    summary_data = []
    
    try:
        wb = openpyxl.load_workbook(file_path, keep_vba=True)
        
        for sheet_name in wb.sheetnames:
            if sheet_name.lower() in ["dashboard", "index", "summary", "sheet1", "sheet2"]:
                continue
                
            sheet = wb[sheet_name]
            print(f"-> Đang tính toán nhóm ngành: {sheet_name}")
            row_idx = 2
            symbols = []
            
            while True:
                cell_val = sheet.cell(row=row_idx, column=1).value
                if cell_val is None:
                    break
                symbols.append((row_idx, str(cell_val).strip().upper()))
                row_idx += 1
                
            if not symbols:
                continue
                
            total_bd_gia = 0.0
            total_kltb = 0.0
            count_valid = 0
            
            # Sử dụng đa luồng (5 workers để vừa nhanh vừa không bị nghẽn IP)
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(worker, symbols)
                
            for row, sym, res in results:
                if res is not None:
                    try:
                        # Ghi toàn bộ 11 giá trị tính được vào các cột tương ứng (B đến L)
                        for col_idx, val in enumerate(res, start=2):
                            sheet.cell(row=row, column=col_idx, value=val)
                        
                        total_bd_gia += float(res[2])  # Cột % tăng/giảm
                        total_kltb += float(res[3])   # Cột KLTB_KLTB21
                        count_valid += 1
                    except Exception:
                        pass

            if count_valid > 0:
                avg_bd = (total_bd_gia / count_valid) * 100
                avg_kl = total_kltb / count_valid
                summary_data.append({
                    "Nhóm Ngành": sheet_name,
                    "Biến động TB (%)": round(avg_bd, 2),
                    "Thanh khoản TB (Lần)": round(avg_kl, 2)
                })
                print(f"   => Hoàn thành ngành {sheet_name}. Biến động TB: {round(avg_bd, 2)}%")

        # Ghi kết quả tổng hợp vào Dashboard Excel
        if "Dashboard" in wb.sheetnames and summary_data:
            dash_sheet = wb["Dashboard"]
            for r in range(3, 40):
                dash_sheet.cell(row=r, column=1, value=None)
                dash_sheet.cell(row=r, column=2, value=None)
                dash_sheet.cell(row=r, column=3, value=None)
                
            for idx, data in enumerate(summary_data, start=3):
                dash_sheet.cell(row=idx, column=1, value=data["Nhóm Ngành"])
                dash_sheet.cell(row=idx, column=2, value=data["Biến động TB (%)"] / 100) 
                dash_sheet.cell(row=idx, column=3, value=data["Thanh khoản TB (Lần)"])
                
        wb.save(file_path)
        print("=== ĐÃ LƯU EXCEL THÀNH CÔNG ===")
    except Exception as e:
        print(f"Lỗi xử lý file Excel: {e}")

    # =====================================================================
    # XUẤT HTML ĐỂ VẼ BIỂU ĐỒ DIỄN BIẾN NGÀNH
    # =====================================================================
    df_dash = pd.DataFrame(summary_data)
    html_charts = ""
    html_table = "<p class='text-muted p-3'>Không có dữ liệu tổng hợp ngành.</p>"
    
    if not df_dash.empty:
        df_dash = df_dash.sort_values(by="Biến động TB (%)", ascending=False)
        fig_p = px.bar(df_dash, x='Nhóm Ngành', y='Biến động TB (%)', 
                       title="Biến Động Giá Trung Bình Theo Từng Nhóm Ngành (%)", text_auto='.2f',
                       color='Biến động TB (%)', color_continuous_scale='RdYlGn',
                       labels={'Biến động TB (%)': 'Biến động (%)'})
        fig_p.update_layout(xaxis_title="Nhóm Ngành", yaxis_title="Biến động (%)", title_x=0.5)
        html_charts = pio.to_html(fig_p, full_html=False, include_plotlyjs='cdn')
        html_table = df_dash.to_html(classes='table table-hover table-striped table-bordered text-center', index=False)

    df_idx = get_data_index()
    html_idx = df_idx.to_html(classes='table table-bordered text-center table-info', index=False) if not df_idx.empty else "<p>Chưa có chỉ số thị trường</p>"

    tz_vn = timezone(timedelta(hours=7))
    now_str = datetime.now(tz_vn).strftime("%d/%m/%Y %H:%M:%S")
    
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Diễn Biến Nhóm Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head>
    <body style="background-color: #f4f6f9;">
        <div class="container my-5">
            <div class="text-center mb-5">
                <h2 class="fw-bold">HỆ THỐNG PHÂN TÍCH BIẾN ĐỘNG NGÀNH TỰ ĐỘNG</h2>
                <p>Cập nhật lần cuối: <span class="badge bg-danger">{now_str}</span></p>
            </div>
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">📊 BIỂU ĐỒ DIỄN BIẾN CÁC NHÓM NGÀNH</div>
                <div class="card-body">{html_charts if html_charts else "Chưa có biểu đồ."}</div>
            </div>
            <div class="row">
                <div class="col-md-5">
                    <div class="card"><div class="card-header bg-dark text-white">📋 CHI TIẾT NGÀNH</div><div class="card-body">{html_table}</div></div>
                </div>
                <div class="col-md-7">
                    <div class="card"><div class="card-header bg-info">🌐 CHỈ SỐ CHUNG</div><div class="card-body">{html_idx}</div></div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("=== ĐÃ TẠO FILE INDEX.HTML VỚI ĐẦY ĐỦ SỐ LIỆU BIỂU ĐỒ ===")

if __name__ == "__main__":
    main()
