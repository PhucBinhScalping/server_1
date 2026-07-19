import requests
import pandas as pd
from datetime import datetime
import pytz

def get_data_index():
    # 1. Lấy dữ liệu CafeF hiện tại
    try:
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', timeout=10)
        results_vni = re_vni_url.json()
        name_map = {'VN-Index': 'VNINDEX', 'VN30-Index': 'VN30', 'HNXINDEX': 'HNX', 'HNX30-Index': 'HNX30', 'HNXUPCOMINDEX': 'UPCOM'}
        df = pd.DataFrame(results_vni)
        
        # Đồng bộ hóa tên các chỉ số
        df['name'] = df['name'].replace(name_map)
        df = df[df['name'].isin(name_map.values())].copy()
        
        # Ưu tiên lấy cột điểm số thực tế 'mc' (nếu có) hoặc dùng cột 'index'
        if 'mc' in df.columns:
            df['diem_so'] = pd.to_numeric(df['mc'].astype(str).str.replace(',', ''), errors='coerce')
        else:
            df['diem_so'] = pd.to_numeric(df['index'].astype(str).str.replace(',', ''), errors='coerce')
            
        df['change'] = pd.to_numeric(df['change'], errors='coerce').fillna(0)
        df['percent'] = pd.to_numeric(df['percent'], errors='coerce').fillna(0) / 100
        
        # SỬA LỖI TÊN CỘT: Sử dụng đúng cột gốc 'volume' và 'value' từ dữ liệu API
        df['volume'] = df['volume'].astype(str).str.replace(',', '', regex=False).astype(float).fillna(0)
        df['value'] = df['value'].astype(str).str.replace(',', '', regex=False).astype(float).fillna(0)
    except Exception as e:
        return f"<p style='color:red;'>Lỗi lấy dữ liệu bảng giá: {e}</p>"

    # 2. Định nghĩa URLs lấy lịch sử phiên trước để so sánh thanh khoản
    urls = {
        'VNINDEX': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=VNINDEX&PageIndex=1&PageSize=20',
        'VN30': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=VN30INDEX&PageIndex=1&PageSize=20',
        'HNX': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HNX&Symbol=HNX-INDEX&PageIndex=1&PageSize=20',
        'UPCOM': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=UPCOM&Symbol=UPCOM-INDEX&PageIndex=1&PageSize=20',
        'HNX30': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HNX&Symbol=HNX30-INDEX&PageIndex=1&PageSize=20'
    }

    data_list = []
    for name, url in urls.items():
        try:
            r = requests.get(url, timeout=5).json()
            history_list = r.get('Data', {}).get('Data', [])
            
            if len(history_list) > 1:
                prev_day = history_list[1]  # Lấy phiên liền trước phiên hiện tại
                vol_raw = str(prev_day.get('KhoiLuongKhopLenh', '1')).replace(',', '')
                val_raw = str(prev_day.get('GiaTriKhopLenh', '1')).replace(',', '')
                
                data_list.append({
                    'name': name, 
                    'volume_2': float(vol_raw) if vol_raw else 1.0, 
                    'value_2': float(val_raw) if val_raw else 1.0
                })
            else:
                data_list.append({'name': name, 'volume_2': 1.0, 'value_2': 1.0})
        except Exception:
            data_list.append({'name': name, 'volume_2': 1.0, 'value_2': 1.0})

    # 4. Merge và Tính toán phần trăm chênh lệch (Đã sửa đổi gọi tên cột chính xác)
    result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
    result_df['Thanh khoản %'] = (((result_df['volume'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1)
    result_df['Thay đổi GT %'] = (((result_df['value'] - result_df['value_2']) / result_df['value_2']) * 100).round(1)
    
    # 5. Định dạng lại bảng theo thứ tự ưu tiên hiển thị
    custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
    result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
    final_df = result_df.sort_values('name')
        
    # 6. Lấy thời gian cập nhật thực tế (Múi giờ Việt Nam)
    vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    time_str = vn_now.strftime('%d-%m-%Y %H:%M:%S')

    # 7. Khởi tạo cấu trúc HTML có nhúng CSS Inline chống tràn tuyệt đối
    html = f"""
    <div style="text-align: right; font-size: 13px; color: #666; margin-bottom: 15px; font-style: italic;">
        Cập nhật: {time_str}
    </div>
    <div style="width:100%; overflow-x:auto !important; -webkit-overflow-scrolling:touch;">
        <table class="world-index-table" border="0" style="width:100% !important; min-width:780px !important; border-collapse:collapse; text-align:center; table-layout:auto !important;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 12px 6px; white-space: nowrap;">Chỉ số</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">Điểm số</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">Thay đổi</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">%</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">KL Khớp</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">GT Khớp</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">Thanh khoản %</th>
                    <th style="padding: 12px 6px; white-space: nowrap;">Thay đổi GT %</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Duyệt qua từng dòng dữ liệu để kết xuất bảng HTML màu sắc động
    for _, row in final_df.iterrows():
        def get_color(v): return '#dc3545' if v < 0 else '#198754' if v > 0 else 'black'
        
        html += f"<tr style='border-bottom: 1px solid #eee;'>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap; font-weight:bold;'>{row['name']}</td>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap; font-weight:bold;'>{row['diem_so']:,.2f}</td>" 
        html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['change'])}; font-weight:bold;'>{row['change']:,.2f}</td>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['percent'])}; font-weight:bold;'>{row['percent']:.2%}</td>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap;'>{row['volume']:,.0f}</td>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap;'>{row['value']:,.0f}</td>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['Thanh khoản %'])}; font-weight:bold;'>{row['Thanh khoản %']:.1f}%</td>"
        html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['Thay đổi GT %'])}; font-weight:bold;'>{row['Thay đổi GT %']:.1f}%</td>"
        html += "</tr>"
        
    html += '</tbody></table></div>'
    
    return html
