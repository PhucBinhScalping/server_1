import datetime as dt
import pandas as pd
from datetime import datetime, timedelta, timezone
import requests
import json
import os
import plotly.express as px
import plotly.io as pio
from user_agent import random_user

# Khởi tạo User-Agent toàn cục để tránh bị chặn
global head
head = {"User-Agent": random_user()}

url_danh_sach_cty = "danh_sach_cong_ty.xlsx"

# =====================================================================
# 1. TẢI TOÀN BỘ DỮ LIỆU LỊCH SỬ 60 PHIÊN CỦA TOÀN THỊ TRƯỜNG (SIÊU TỐC)
# =====================================================================
def download_all_market_history():
    """Tải dữ liệu của tất cả các mã trong khoảng 90 ngày (đảm bảo đủ 60 phiên giao dịch thực tế)"""
    try:
        tz_vn = timezone(timedelta(hours=7))
        todate = datetime.now(tz_vn)
        # Lấy lùi lại 90 ngày để trừ đi thứ 7, Chủ Nhật và ngày lễ, chắc chắn đủ 60 phiên giao dịch
        fromdate = todate - timedelta(days=90)
        fdate = fromdate.strftime('%Y-%m-%d')

        print(f"-> Đang tải dữ liệu lịch sử thị trường hàng loạt từ ngày: {fdate}...")
        # Sử dụng size=50000 để quét toàn bộ lịch sử các mã trong 1 lần gọi duy nhất
        url = f"https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&q=date:gte:{fdate}&size=50000&page=1"
        r = requests.get(url, headers=head, timeout=20)
        
        if r.status_code == 200 and 'data' in r.json():
            df = pd.DataFrame(r.json()['data'])
            if df.empty:
                return pd.DataFrame()
                
            # Chuẩn hóa tên cột đồng bộ với hàm tính toán gốc của bạn
            df.rename(columns={
                'code': 'symbol',
                'nmVolume': 'klgd_khop_lenh',
                'nmValue': 'gtgd_khop_lenh',
                'ptVolume': 'klgd_thoa_thuan',
                'ptValue': 'gtgd_thoa_thuan',
                'change': '+/-',
                'pctChange': '+/-%'
            }, inplace=True)

            # Tính tổng khối lượng (volume)
            df['volume'] = pd.to_numeric(df['klgd_khop_lenh'], errors='coerce').fillna(0) + \
                            pd.to_numeric(df['klgd_thoa_thuan'], errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True)
            
            # Ép kiểu số cho giá và khối lượng
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
                
            # Sắp xếp theo ngày tăng dần để phục vụ tính hàm tail() hoặc mean() lũy tiến
            df = df.sort_values(by=['symbol', 'date'], ascending=[True, True])
            return df
    except Exception as e:
        print(f"[Lỗi] Không thể tải dữ liệu thị trường hàng loạt: {e}")
    return pd.DataFrame()

# =====================================================================
# 2. HÀM TÍNH TOÁN DỮ LIỆU CỦA 1 CỔ PHIẾU TỪ DỮ LIỆU ĐÃ CÓ TRÊN RAM
# =====================================================================
def tinh_du_lieu_cp_from_ram(symbol, market_df):
    try:
        # Lọc ra lịch sử của duy nhất mã này
        data = market_df[market_df['symbol'] == symbol.upper()].copy()
        if data.empty or len(data) < 21: # Đảm bảo đủ phiên để tính toán chỉ số
            return None
            
        # Lấy dòng cuối cùng (phiên mới nhất)
        last_row = data.iloc[-1]
        
        # Kiểm tra thanh khoản trung bình 60 phiên (hoặc tối đa số phiên đang có)
        volume_trung_binh = data['volume'].tail(60).mean()
        if pd.isna(volume_trung_binh) or volume_trung_binh <= 10000:
            return None # Lọc sớm cổ phiếu thanh khoản thấp

        # Lấy các giá trị tại phiên mới nhất
        gia_close = float(last_row['close'])
        KL1000 = float(last_row['volume']) / 1000
        BD_gia = float(last_row['+/-%']) / 100

        # 2. Tính toán các giá trị trung bình dựa trên các phiên GẦN NHẤT (dưới lên)
        KLGD_KLTB21_mean = data['volume'].tail(21).mean()
        KLTB_KLTB21 = float(last_row['volume']) / KLGD_KLTB21_mean if KLGD_KLTB21_mean > 0 else 0

        close_mean_5 = data['close'].tail(5).mean()
        close_mean_21 = data['close'].tail(21).mean()
        gia_tbgia5 = close_mean_5 / close_mean_21 if close_mean_21 > 0 else 0

        KL_KLTB5_mean = data['volume'].tail(5).mean()
        KL_KLTB5 = float(last_row['volume']) / KL_KLTB5_mean if KL_KLTB5_mean > 0 else 0

        # 3. Tính đỉnh và đáy của tối đa 60 ngày gần nhất
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
# 3. HÀM ĐIỀU PHỐI CHÍNH
# =====================================================================
def main():
    print("=== HỆ THỐNG QUÉT LỊCH SỬ KHÔNG Ổ ĐĨA SIÊU TỐC ===")
    
    if not os.path.exists(url_danh_sach_cty):
        print(f"Lỗi: Không tìm thấy file danh sách công ty: {url_danh_sach_cty}")
        return

    # Tải toàn bộ bảng giá lịch sử vào bộ nhớ RAM trước
    market_df = download_all_market_history()
    if market_df.empty:
        print("[Lỗi] Không lấy được dữ liệu lịch sử từ API. Tiến trình dừng lại.")
        return

    # Đọc cấu trúc danh mục ngành
    df_company = pd.read_excel(url_danh_sach_cty)
    list_name_nganh = df_company['Ngành Cấp 2'].unique().tolist()
    nganh_hop_le = [n for n in list_name_nganh if isinstance(n, str)]

    danh_sach_kq_nganh = []

    for nganh in nganh_hop_le:
        df_nganh_raw = df_company[df_company['Ngành Cấp 2'] == nganh]
        list_ticker = df_nganh_raw['Ticker'].unique().tolist()
        
        list_ds_tb = {}
        for ma in list_ticker:
            # Tra cứu và tính toán siêu tốc trực tiếp trên RAM, không gọi API lặp
            res = tinh_du_lieu_cp_from_ram(ma, market_df)
            if res is not None:
                list_ds_tb[ma] = res
                
        if not list_ds_tb:
            continue

        # Chuyển đổi sang DataFrame tổng hợp ngành
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
        print(f" -> Hoàn thành phân tích ngành: {nganh}")

    if not danh_sach_kq_nganh:
        print("Không có dữ liệu ngành hợp lệ nào được trích xuất.")
        return

    # Tổng hợp dữ liệu
    df_tong_hop_nganh = pd.concat(danh_sach_kq_nganh, ignore_index=True)
    df_tong_hop_nganh.rename(columns={'Ngành': 'name', 'BD_gia': 'percent_change', 'KLTB_KLTB21': 'volume_ratio'}, inplace=True)
    
    tz_vn = timezone(timedelta(hours=7))
    now_dt = datetime.now(tz_vn)
    df_tong_hop_nganh['updated_at'] = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    # =====================================================================
    # 4. XUẤT WEBSITE HTML VÀ BIỂU ĐỒ DIỄN BIẾN NGÀNH
    # =====================================================================
    df_dash = df_tong_hop_nganh.copy()
    df_dash['percent_change'] = df_dash['percent_change'] * 100  # Chuyển sang số %
    df_dash = df_dash.sort_values(by="percent_change", ascending=False)

    fig_p = px.bar(df_dash, x='name', y='percent_change', 
                   title="Biến Động Giá Trung Bình Theo Từng Nhóm Ngành (%)", text_auto='.2f',
                   color='percent_change', color_continuous_scale='RdYlGn',
                   labels={'percent_change': 'Biến động (%)', 'name': 'Nhóm Ngành'})
    fig_p.update_layout(xaxis_title="Nhóm Ngành", yaxis_title="Biến động (%)", title_x=0.5)
    html_charts = pio.to_html(fig_p, full_html=False, include_plotlyjs='cdn')
    
    df_table_show = df_dash[['name', 'percent_change', 'volume_ratio']].copy()
    df_table_show.columns = ['Nhóm Ngành', 'Biến Động Giá (%)', 'Tỷ Lệ Thanh Khoản (Lần)']
    html_table = df_table_show.to_html(classes='table table-hover table-striped table-bordered text-center', index=False, float_format=lambda x: f"{x:.2f}")

    df_idx = get_data_index()
    html_idx = df_idx.to_html(classes='table table-bordered text-center table-info', index=False) if not df_idx.empty else "<p>Không có dữ liệu chỉ số</p>"

    full_html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Phân Tích Nhóm Ngành</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head>
    <body style="background-color: #f4f6f9;">
        <div class="container my-5">
            <div class="text-center mb-5">
                <h2 class="fw-bold">HỆ THỐNG PHÂN TÍCH BIẾN ĐỘNG NGÀNH TỰ ĐỘNG</h2>
                <p>Cập nhật phiên mới nhất: <span class="badge bg-danger">{now_dt.strftime('%d/%m/%Y %H:%M:%S')}</span></p>
            </div>
            <div class="card mb-4">
                <div class="card-header bg-primary text-white fw-bold">📊 BIỂU ĐỒ DIỄN BIẾN CÁC NHÓM NGÀNH</div>
                <div class="card-body">{html_charts}</div>
            </div>
            <div class="row">
                <div class="col-md-5">
                    <div class="card">
                        <div class="card-header bg-dark text-white fw-bold">📋 CHI TIẾT SỐ LIỆU</div>
                        <div class="card-body table-responsive">{html_table}</div>
                    </div>
                </div>
                <div class="col-md-7">
                    <div class="card">
                        <div class="card-header bg-info fw-bold">🌐 CHỈ SỐ THỊ TRƯỜNG CHUNG</div>
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
    print("=== HOÀN THÀNH: BIỂU ĐỒ VÀ TRANG HTML ĐÃ ĐƯỢC DỰNG THÀNH CÔNG ===")

if __name__ == "__main__":
    main()
