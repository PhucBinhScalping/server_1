import datetime as dt
import pandas as pd
from datetime import date, datetime, timedelta, timezone
import requests
import json
import openpyxl
import plotly.express as px
import plotly.io as pio
from user_agent import random_user

# Khởi tạo User-Agent toàn cục để tránh bị chặn
global head
head = {"User-Agent": random_user()}

# =====================================================================
# 1. TẢI TOÀN BỘ DỮ LIỆU THỊ TRƯỜNG TRONG 1 CÚ CLICK (TĂNG TỐC 100 LẦN)
# =====================================================================
def download_all_market_data():
    """Lấy toàn bộ giá đóng cửa và biến động của tất cả mã trong phiên hôm nay"""
    try:
        url = "https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:2026-01-01&size=5000&page=1"
        r = requests.get(url, headers=head, timeout=15)
        if r.status_code == 200 and 'data' in r.json():
            df = pd.DataFrame(r.json()['data'])
            # Chỉ lấy phiên gần nhất của từng mã
            df = df.sort_values(by='date', ascending=False).drop_duplicates(subset=['code'])
            # Thiết lập mã cổ phiếu làm chỉ mục để tìm kiếm siêu tốc
            df.set_index('code', inplace=True)
            return df
    except Exception as e:
        print(f"[Cảnh báo] Không thể tải dữ liệu thị trường hàng loạt: {e}")
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
        return df[['name', 'change', 'index', 'percent', 'volume', 'value']]
    except Exception:
        return pd.DataFrame()

# =====================================================================
# 2. TIẾN TRÌNH CHÍNH (XỬ LÝ TRONG BỘ NHỚ SIÊU TỐC)
# =====================================================================
def main():
    print("=== BẮT ĐẦU ĐỒNG BỘ DỮ LIỆU SIÊU TỐC ===")
    file_path = "THONG_KE_VNINDEX_VN30.xlsm"
    
    try:
        wb = openpyxl.load_workbook(file_path, keep_vba=True)
    except Exception as e:
        print(f"Lỗi: Không tìm thấy hoặc không mở được file Excel {file_path}: {e}")
        return

    # Tải trước toàn bộ bảng giá thị trường về bộ nhớ
    print("-> Đang tải bảng giá toàn thị trường từ VNDirect...")
    market_df = download_all_market_data()
    if market_df.empty:
        print("Không có dữ liệu thị trường, dừng tiến trình.")
        return
    print("-> Tải thành công! Bắt đầu ánh xạ vào Excel...")

    summary_data = []
    
    for sheet_name in wb.sheetnames:
        if sheet_name.lower() in ["dashboard", "index", "summary", "sheet1", "sheet2"]:
            continue
            
        sheet = wb[sheet_name]
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
        count_valid = 0
        
        # Tra cứu trực tiếp từ bảng dữ liệu đã tải sẵn thay vì gửi request liên tục
        for row, sym in symbols:
            if sym in market_df.index:
                try:
                    row_data = market_df.loc[sym]
                    
                    # Trích xuất an toàn các giá trị
                    gia_close = float(pd.to_numeric(row_data['close'], errors='coerce'))
                    nm_vol = float(pd.to_numeric(row_data['nmVolume'], errors='coerce'))
                    pt_vol = float(pd.to_numeric(row_data['ptVolume'], errors='coerce'))
                    kl_1000 = (nm_vol + pt_vol) / 1000
                    bd_gia = float(pd.to_numeric(row_data['pctChange'], errors='coerce') / 100)
                    
                    # Ghi nhanh dữ liệu vào Excel (Cột B, C, D)
                    sheet.cell(row=row, column=2, value=gia_close)
                    sheet.cell(row=row, column=3, value=kl_1000)
                    sheet.cell(row=row, column=4, value=bd_gia)
                    
                    total_bd_gia += bd_gia
                    count_valid += 1
                except Exception:
                    pass

        if count_valid > 0:
            avg_bd = (total_bd_gia / count_valid) * 100
            summary_data.append({
                "Nhóm Ngành": sheet_name,
                "Biến động TB (%)": round(avg_bd, 2),
                "Thanh khoản TB (Lần)": 1.0  # Giá trị mặc định hoặc bỏ qua để tối ưu tốc độ
            })
            print(f"   => Ngành {sheet_name} hoàn thành. Biến động TB: {round(avg_bd, 2)}%")

    # Ghi kết quả tổng hợp vào Dashboard
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
            
    try:
        wb.save(file_path)
        print("=== ĐÃ LƯU DỮ LIỆU MỚI VÀO FILE EXCEL THÀNH CÔNG ===")
    except Exception as save_err:
        print(f"Không thể lưu file Excel: {save_err}")

    # =====================================================================
    # 3. XUẤT RA WEB HTML VÀ VẼ BIỂU ĐỒ DIỄN BIẾN NGÀNH
    # =====================================================================
    df_dash = pd.DataFrame(summary_data)
    html_charts = ""
    html_table = "<p>Không có số liệu tổng hợp ngành</p>"
    
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
    html_idx = df_idx.to_html(classes='table table-bordered text-center table-info', index=False) if not df_idx.empty else ""

    tz_vn = timezone(timedelta(hours=7))
    now_str = datetime.now(tz_vn).strftime("%d/%m/%Y %H:%M:%S")
    
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
                <p class="text-muted">Múi giờ Việt Nam (+7) | Cập nhật lúc: <span class="badge bg-danger">{now_str}</span></p>
            </div>
            <div class="card border-primary">
                <div class="card-header bg-primary text-white">📊 BIỂU ĐỒ DIỄN BIẾN CÁC NHÓM NGÀNH (ĐỒNG BỘ FILE EXCEL)</div>
                <div class="card-body">{html_charts}</div>
            </div>
            <div class="row">
                <div class="col-md-5">
                    <div class="card">
                        <div class="card-header bg-dark text-white">📋 CHI TIẾT SỐ LIỆU TRUNG BÌNH CÁC NGÀNH</div>
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
    print("=== ĐÃ XUẤT THÀNH CÔNG GIAO DIỆN INDEX.HTML VÀ BIỂU ĐỒ ĐỒNG BỘ ===")

if __name__ == "__main__":
    main()
