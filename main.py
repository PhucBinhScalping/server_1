import datetime as dt
import pandas as pd
from datetime import date, datetime, timedelta
import requests
import time
from user_agent import random_user
import RStockvn as rpv
import json
import openpyxl
import plotly.express as px
import plotly.io as pio

# Khởi tạo User-Agent toàn cục tránh bị block
global head
head = {"User-Agent": random_user()}

# =====================================================================
# CÁC HÀM CÀO DỮ LIỆU PHỤ TRỢ (VĨ MÔ, CHỈ SỐ CHUNG)
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
    except Exception as e:
        print(f"[Cảnh báo] Không lấy được index chung: {e}")
        return pd.DataFrame()

# =====================================================================
# HÀM TÍNH TOÁN DỮ LIỆU CỔ PHIẾU (AN TOÀN TUYỆT ĐỐI)
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
        
        # Ép toàn bộ kiểu dữ liệu về float tiêu chuẩn của Python (Sửa lỗi openpyxl không nhận định dạng)
        gia_close = float(pd.to_numeric(first_row['close'], errors='coerce'))
        KL1000 = float(pd.to_numeric(first_row['volumn'], errors='coerce') / 1000)
        BD_gia = float(pd.to_numeric(first_row['pctChange'], errors='coerce') / 100)

        KLGD_KLTB21_mean = pd.to_numeric(data['volumn'].iloc[:22].mean(), errors='coerce')
        KLTB_KLTB21 = float(pd.to_numeric(first_row['volumn'], errors='coerce') / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0)

        close_mean_5 = pd.to_numeric(data['close'].iloc[:6].mean(), errors='coerce')
        close_mean_21 = pd.to_numeric(data['close'].iloc[:22].mean(), errors='coerce')
        gia_tbgia5 = float(close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0)

        KL_KLTB5_mean = pd.to_numeric(data['volumn'].iloc[:6].mean(), errors='coerce')
        KL_KLTB5 = float(pd.to_numeric(first_row['volumn'], errors='coerce') / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0)

        close_60 = pd.to_numeric(data['close'].iloc[:60], errors='coerce')
        day2t = float(close_60.min())
        dinh2t = float(close_60.max())
        dinh_day = float((dinh2t - day2t) / day2t if day2t > 0 else 0)
        giam_sdinh = float((gia_close - dinh2t) / dinh2t if dinh2t > 0 else 0)
        tang_sday = float((gia_close - day2t) / day2t if day2t > 0 else 0)

        return [gia_close, KL1000, BD_gia, KLTB_KLTB21, gia_tbgia5, KL_KLTB5, dinh_day, day2t, dinh2t, tang_sday, giam_sdinh]
    except Exception as e:
        # Nếu lỗi (ví dụ mã ngừng giao dịch), trả về None để bỏ qua an toàn
        return None

# =====================================================================
# HÀM TIẾN TRÌNH CHÍNH
# =====================================================================
def main():
    print("=== KHỞI CHẠY HỆ THỐNG PHÂN TÍCH 1000 MÃ AN TOÀN ===")
    file_path = "THONG_KE_VNINDEX_VN30.xlsm"
    
    try:
        wb = openpyxl.load_workbook(file_path, keep_vba=True)
    except Exception as e:
        print(f"Không thể mở file Excel {file_path}: {e}")
        return

    summary_data = []
    
    # 1. Vòng lặp quét an toàn qua từng Sheet ngành
    for sheet_name in wb.sheetnames:
        # Loại trừ các sheet hệ thống giao diện
        if sheet_name.lower() in ["dashboard", "index", "summary", "sheet1", "sheet2"]:
            continue
            
        sheet = wb[sheet_name]
        print(f"-> Đang tổng hợp số liệu ngành: {sheet_name}")
        
        row_idx = 2
        symbols = []
        
        # Đọc danh sách mã ở cột A
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
        
        for row, sym in symbols:
            if len(sym) != 3: 
                continue
                
            res = tinh_du_lieu_cp(sym)
            
            # KIỂM TRA CHẶT CHẼ: Chỉ xử lý nếu kết quả trả về là một list hợp lệ
            if isinstance(res, list) and len(res) == 11:
                try:
                    # Ghi dữ liệu vào các cột tương ứng trên Excel (Cột B -> L)
                    for col_idx, val in enumerate(res, start=2):
                        sheet.cell(row=row, column=col_idx, value=val)
                    
                    total_bd_gia += res[2]  # Biến động giá
                    total_kltb += res[3]    # KLTB/KLTB21
                    count_valid += 1
                except Exception as write_err:
                    print(f"Lỗi ghi mã {sym} vào sheet {sheet_name}: {write_err}")
            
            # Thời gian nghỉ 0.15 giây tránh spam nghẽn mạng API VNDirect
            time.sleep(0.15)
            
        # Tính toán giá trị trung bình nếu ngành có mã hợp lệ
        if count_valid > 0:
            avg_bd = (total_bd_gia / count_valid) * 100
            avg_kl = total_kltb / count_valid
            summary_data.append({
                "Nhóm Ngành": sheet_name,
                "Biến động TB (%)": round(avg_bd, 2),
                "Thanh khoản TB (Lần)": round(avg_kl, 2)
            })
            print(f"   => Hoàn thành {sheet_name}: {count_valid} mã. Biến động TB: {round(avg_bd, 2)}%")

    # 2. Cập nhật số liệu an toàn vào sheet Dashboard
    if "Dashboard" in wb.sheetnames and summary_data:
        dash_sheet = wb["Dashboard"]
        
        # Tìm vị trí ghi dữ liệu thích hợp hoặc ghi đè từ hàng 3 một cách an toàn
        for r in range(3, 40):
            dash_sheet.cell(row=r, column=1, value=None)
            dash_sheet.cell(row=r, column=2, value=None)
            dash_sheet.cell(row=r, column=3, value=None)
            
        for idx, data in enumerate(summary_data, start=3):
            dash_sheet.cell(row=idx, column=1, value=data["Nhóm Ngành"])
            dash_sheet.cell(row=idx, column=2, value=data["Biến động TB (%)"] / 100)
            dash_sheet.cell(row=idx, column=3, value=data["Thanh khoản TB (Lần)"])
            
    try:
        wb.save(file_path)
        print("=== ĐÃ CẬP NHẬT FILE EXCEL THÀNH CÔNG ===")
    except Exception as save_err:
        print(f"Không thể lưu file Excel (Có thể file đang mở): {save_err}")

    # =====================================================================
    # 3. SINH ĐỒ THỊ TRỰC QUAN DIỄN BIẾN CÁC NGÀNH RA FILE HTML
    # =====================================================================
    df_dash = pd.DataFrame(summary_data)
    html_charts = ""
    html_table = "<p>Không có số liệu</p>"
    
    if not df_dash.empty:
        # Sắp xếp ngành theo thứ tự biến động giảm dần để biểu đồ đẹp mắt hơn
        df_dash = df_dash.sort_values(by="Biến động TB (%)", ascending=False)
        
        fig_p = px.bar(df_dash, x='Nhóm Ngành', y='Biến động TB (%)', 
                       title="Biến Động Giá Trung Bình Theo Từng Nhóm Ngành (%)", text_auto='.2f',
                       color='Biến động TB (%)', color_continuous_scale='RdYlGn',
                       labels={'Biến động TB (%)': 'Biến động (%)'})
        
        fig_p.update_layout(xaxis_title="Nhóm Ngành", yaxis_title="Biến động (%)", title_x=0.5)
                       
        html_charts = pio.to_html(fig_p, full_html=False, include_plotlyjs='cdn')
        html_table = df_dash.to_html(classes='table table-hover table-striped table-bordered text-center', index=False)

    df_idx = get_data_index()
    html_idx = df_idx.to_html(classes='table table-bordered text-center table-info', index=False) if not df_idx.empty else ""

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Diễn Biến Nhóm Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #f4f6f9; font-family: 'Segoe UI', Arial, sans-serif; }}
            .card {{ border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 30px; }}
            .card-header {{ font-weight: bold; font-size: 1.2rem; }}
        </style>
    </head>
    <body>
        <div class="container my-5">
            <div class="text-center mb-5">
                <h2 class="fw-bold text-dark">HỆ THỐNG PHÂN TÍCH BIẾN ĐỘNG NGÀNH TỰ ĐỘNG</h2>
                <p class="text-muted">Đồng bộ dữ liệu thời gian thực | Cập nhật lúc: <span class="badge bg-danger">{now_str}</span></p>
            </div>
            
            <div class="card border-primary">
                <div class="card-header bg-primary text-white">📊 BIỂU ĐỒ DIỄN BIẾN CÁC NHÓM NGÀNH</div>
                <div class="card-body">
                    {html_charts}
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-5">
                    <div class="card">
                        <div class="card-header bg-dark text-white">📋 CHI TIẾT SỐ LIỆU TRUNG BÌNH</div>
                        <div class="card-body table-responsive">{html_table}</div>
                    </div>
                </div>
                <div class="col-md-7">
                    <div class="card">
                        <div class="card-header bg-info text-dark">🌐 CHỈ SỐ THỊ TRƯỜNG TỔNG QUAN</div>
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
    print("=== ĐÃ TẠO THÀNH CÔNG GIAO DIỆN INDEX.HTML BIỂU ĐỒ NGÀNH ===")

if __name__ == "__main__":
    main()
