import datetime as dt
import pandas as pd
from datetime import date, datetime, timedelta
import requests
import time
from user_agent import random_user
import RStockvn as rpv
import json
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import plotly.express as px
import plotly.io as pio

# Khởi tạo User-Agent toàn cục tránh bị block
global head
head = {"User-Agent": random_user()}

# =====================================================================
# CÁC HÀM CÀO DỮ LIỆU PHỤ TRỢ (VĨ MÔ, CHỈ SỐ)
# =====================================================================
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
    except:
        return pd.DataFrame()

# =====================================================================
# HÀM LOGIC TÍNH TOÁN CỔ PHIẾU (Thay thế hàm xlwings cũ)
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
        KL1000 = pd.to_numeric(first_row['volumn'], errors='coerce') / 1000
        BD_gia = pd.to_numeric(first_row['pctChange'], errors='coerce') / 100

        KLGD_KLTB21_mean = pd.to_numeric(data['volumn'].iloc[:22].mean(), errors='coerce')
        KLTB_KLTB21 = pd.to_numeric(first_row['volumn'], errors='coerce') / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0

        close_mean_5 = pd.to_numeric(data['close'].iloc[:6].mean(), errors='coerce')
        close_mean_21 = pd.to_numeric(data['close'].iloc[:22].mean(), errors='coerce')
        gia_tbgia5 = close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0

        KL_KLTB5_mean = pd.to_numeric(data['volumn'].iloc[:6].mean(), errors='coerce')
        KL_KLTB5 = pd.to_numeric(first_row['volumn'], errors='coerce') / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0

        close_60 = pd.to_numeric(data['close'].iloc[:60], errors='coerce')
        day2t = close_60.min()
        dinh2t = close_60.max()
        dinh_day = (dinh2t - day2t) / day2t if day2t > 0 else 0
        giam_sdinh = (gia_close - dinh2t) / dinh2t if dinh2t > 0 else 0
        tang_sday = (gia_close - day2t) / day2t if day2t > 0 else 0

        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, day2t, dinh2t, tang_sday, giam_sdinh]
    except:
        return None

# =====================================================================
# HÀM XỬ LÝ CHÍNH: ĐỌC, GHI FILE EXCEL & ĐỒNG BỘ DASHBOARD
# =====================================================================
def main():
    print("=== BẮT ĐẦU ĐỌC VÀ CẬP NHẬT FILE EXCEL THONG_KE_VNINDEX_VN30.xlsm ===")
    file_path = "THONG_KE_VNINDEX_VN30.xlsm"
    
    # Mở file Excel bằng openpyxl (đọc cả macro ngầm)
    wb = openpyxl.load_workbook(file_path, keep_vba=True)
    
    summary_data = []
    
    # 1. Quét qua tất cả các Sheet ngành để tính toán từng cổ phiếu
    for sheet_name in wb.sheetnames:
        if sheet_name.lower() in ["dashboard", "index", "summary", "sheet1"]:
            continue
            
        sheet = wb[sheet_name]
        print(f"-> Đang xử lý ngành: {sheet_name}")
        
        # Tìm danh sách mã ở Cột A (bắt đầu từ hàng 2 để bỏ qua tiêu đề)
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
            
        total_bd_gia = 0
        total_kltb = 0
        count_valid = 0
        
        # Chạy hàm tính toán cho từng mã
        for row, sym in symbols:
            if len(sym) != 3: # Chỉ xử lý mã cổ phiếu 3 ký tự hợp lệ
                continue
                
            res = tinh_du_lieu_cp(sym)
            if res:
                # Ghi kết quả vào các cột tiếp theo (Cột B đến L tương ứng từ Giá close đến Giảm so với đỉnh)
                for col_idx, val in enumerate(res, start=2):
                    sheet.cell(row=row, column=col_idx, value=val)
                
                total_bd_gia += res[2]  # Biến động giá
                total_kltb += res[3]    # KLTB/KLTB21
                count_valid += 1
            
            # Nghỉ ngắn 0.15s tránh bị block IP khi quét nhiều mã
            time.sleep(0.15)
            
        # Tính toán giá trị trung bình ngành
        if count_valid > 0:
            avg_bd = (total_bd_gia / count_valid) * 100
            avg_kl = total_kltb / count_valid
            summary_data.append({
                "Nhóm Ngành": sheet_name,
                "Biến động TB (%)": round(avg_bd, 2),
                "Thanh khoản TB (Lần)": round(avg_kl, 2)
            })

    # 2. Ghi ngược dữ liệu trung bình ngành vào sheet Dashboard
    if "Dashboard" in wb.sheetnames and summary_data:
        dash_sheet = wb["Dashboard"]
        # Giả định bảng tổng hợp ngành của bạn bắt đầu từ hàng số 3
        # Xóa dữ liệu cũ ở cột ngành (Cột A, B, C) trước khi điền mới
        for r in range(3, 30):
            dash_sheet.cell(row=r, column=1, value=None)
            dash_sheet.cell(row=r, column=2, value=None)
            dash_sheet.cell(row=r, column=3, value=None)
            
        for idx, data in enumerate(summary_data, start=3):
            dash_sheet.cell(row=idx, column=1, value=data["Nhóm Ngành"])
            dash_sheet.cell(row=idx, column=2, value=data["Biến động TB (%)"] / 100) # Định dạng % trong Excel
            dash_sheet.cell(row=idx, column=3, value=data["Thanh khoản TB (Lần)"])
            
    # Lưu lại file Excel sau khi cập nhật toàn bộ số liệu mới
    wb.save(file_path)
    print("=== ĐÃ CẬP NHẬT VÀ LƯU FILE EXCEL THÀNH CÔNG ===")

    # =====================================================================
    # 3. ĐỒNG BỘ ĐỒ THỊ RA FILE WEB HTML (INDEX.HTML) ĐỂ XEM TRÊN GITHUB PAGES
    # =====================================================================
    df_dash = pd.DataFrame(summary_data)
    html_charts = ""
    html_table = "<p>Không có dữ liệu ngành</p>"
    
    if not df_dash.empty:
        fig_p = px.bar(df_dash, x='Nhóm Ngành', y='Biến động TB (%)', 
                       title="Biến Động Giá Trung Bình Theo Ngành (%)", text_auto='.2f',
                       color='Biến động TB (%)', color_continuous_scale='RdYlGn')
        
        fig_v = px.bar(df_dash, x='Nhóm Ngành', y='Thanh khoản TB (Lần)', 
                       title="Thanh Khoản Hiện Tại / TB 21 Phiên Theo Ngành", text_auto='.2f',
                       color='Thanh khoản TB (Lần)', color_continuous_scale='Blues')
                       
        html_charts = pio.to_html(fig_p, full_html=False, include_plotlyjs='cdn') + "<br>" + pio.to_html(fig_v, full_html=False, include_plotlyjs='cdn')
        html_table = df_dash.to_html(classes='table table-hover table-bordered text-center', index=False)

    df_idx = get_data_index()
    html_idx = df_idx.to_html(classes='table table-bordered text-center table-info', index=False) if not df_idx.empty else ""

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Thống Kê Ngành Tự Động</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #f8f9fa; font-family: sans-serif; }}
            .card {{ margin-bottom: 25px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        </style>
    </head>
    <body>
        <div class="container my-5">
            <div class="text-center mb-5">
                <h2 class="fw-bold text-primary">HỆ THỐNG ĐỒNG BỘ EXCEL & DASHBOARD</h2>
                <p class="text-muted">Cập nhật lúc: <span class="badge bg-dark">{now_str}</span></p>
            </div>
            <div class="card border-primary">
                <div class="card-header bg-primary text-white fw-bold">📊 BIỂU ĐỒ DASHBOARD CÁC NHÓM NGÀNH</div>
                <div class="card-body">{html_charts}</div>
            </div>
            <div class="card">
                <div class="card-header bg-dark text-white fw-bold">📋 BẢNG TỔNG HỢP SỐ LIỆU</div>
                <div class="card-body table-responsive">{html_table}</div>
            </div>
            <div class="card">
                <div class="card-header bg-info text-dark fw-bold">🌐 CHỈ SỐ THỊ TRƯỜNG CHUNG</div>
                <div class="card-body table-responsive">{html_idx}</div>
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("=== ĐÃ TẠO XONG FILE INDEX.HTML ===")

if __name__ == "__main__":
    main()
