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
        
        df['name'] = df['name'].replace(name_map)
        df = df[df['name'].isin(name_map.values())].copy()
        
        if 'mc' in df.columns:
            df['diem_so'] = pd.to_numeric(df['mc'].astype(str).str.replace(',', ''), errors='coerce')
        else:
            df['diem_so'] = pd.to_numeric(df['index'].astype(str).str.replace(',', ''), errors='coerce')
            
        df['change'] = pd.to_numeric(df['change'], errors='coerce').fillna(0)
        df['percent'] = pd.to_numeric(df['percent'], errors='coerce').fillna(0) / 100
        
        df['volume'] = df['volume'].astype(str).str.replace(',', '', regex=False).astype(float).fillna(0)
        df['value'] = df['value'].astype(str).str.replace(',', '', regex=False).astype(float).fillna(0)
    except Exception as e:
        return f"<p style='color:red;'>Lỗi lấy dữ liệu bảng giá: {e}</p>"

    # 2. Định nghĩa URLs lấy lịch sử
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
            # Lấy trực tiếp từ key 'Data' cấp 1 theo đúng cấu trúc thực tế
            history_list = r.get('Data', [])
            
            if len(history_list) > 1:
                prev_day = history_list[1]  
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

    # 3. Merge và Tính toán phần trăm (Dùng chính xác tên cột volume/value gốc)
    result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
    result_df['Thanh khoản %'] = (((result_df['volume'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1)
    result_df['Thay đổi GT %'] = (((result_df['value'] - result_df['value_2']) / result_df['value_2']) * 100).round(1)
    
    # 4. Định dạng thứ tự bảng
    custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
    result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
    final_df = result_df.sort_values('name')
        
    # 5. Sinh bảng HTML với CSS inline cưỡng ép kích thước
    html = """
    <table border="0">
        <thead>
            <tr>
                <th>Chỉ số</th>
                <th>Điểm số</th>
                <th>Thay đổi</th>
                <th>%</th>
                <th>KL Khớp</th>
                <th>GT Khớp</th>
                <th>Thanh khoản %</th>
                <th>Thay đổi GT %</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for _, row in final_df.iterrows():
        def get_color(v): return '#dc3545' if v < 0 else '#198754' if v > 0 else 'black'
        
        html += "<tr>"
        html += f"<td style='font-weight:bold;'>{row['name']}</td>"
        html += f"<td style='font-weight:bold;'>{row['diem_so']:,.2f}</td>" 
        html += f"<td style='color:{get_color(row['change'])}; font-weight:bold;'>{row['change']:,.2f}</td>"
        html += f"<td style='color:{get_color(row['percent'])}; font-weight:bold;'>{row['percent']:.2%}</td>"
        html += f"<td>{row['volume']:,.0f}</td>"
        html += f"<td>{row['value']:,.0f}</td>"
        html += f"<td style='color:{get_color(row['Thanh khoản %'])}; font-weight:bold;'>{row['Thanh khoản %']:.1f}%</td>"
        html += f"<td style='color:{get_color(row['Thay đổi GT %'])}; font-weight:bold;'>{row['Thay đổi GT %']:.1f}%</td>"
        html += "</tr>"
        
    html += '</tbody></table>'
    return html
