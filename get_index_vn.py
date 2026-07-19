import requests
import pandas as pd
from datetime import datetime

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

    # 2. Lấy dữ liệu lịch sử phiên trước để so sánh thanh khoản
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
            history_list = r.get('Data', [])
            prev_day = history_list[1] if len(history_list) > 1 else (history_list[0] if history_list else {})
            
            vol_raw = str(prev_day.get('KhoiLuongKhopLenh', '0')).replace(',', '')
            val_raw = str(prev_day.get('GiaTriKhopLenh', '0')).replace(',', '')
            
            v_2 = float(vol_raw) if vol_raw and float(vol_raw) > 0 else 1.0
            val_2 = float(val_raw) if val_raw and float(val_raw) > 0 else 1.0
            data_list.append({'name': name, 'volume_2': v_2, 'value_2': val_2})
        except:
            data_list.append({'name': name, 'volume_2': 1.0, 'value_2': 1.0})

    # 3. Tính toán 8 cột dữ liệu đầy đủ
    result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
    result_df['Thanh khoản %'] = (((result_df['volume'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1).fillna(0)
    result_df['Thay đổi GT %'] = (((result_df['value'] - result_df['value_2']) / result_df['value_2']) * 100).round(1).fillna(0)
    
    # Định dạng hiển thị số liệu đẹp mắt trước khi render
    result_df['Chỉ số'] = result_df['name']
    result_df['Điểm số'] = result_df['diem_so'].apply(lambda x: f"{x:,.2f}")
    result_df['Thay đổi'] = result_df['change'].apply(lambda x: f"{x:,.2f}")
    result_df['%'] = result_df['percent'].apply(lambda x: f"{x:.2%}")
    result_df['KL Khớp'] = result_df['volume'].apply(lambda x: f"{x:,.0f}")
    result_df['GT Khớp'] = result_df['value'].apply(lambda x: f"{x:,.0f}")
    result_df['Thanh khoản %'] = result_df['Thanh khoản %'].apply(lambda x: f"{x}%")
    result_df['Thay đổi GT %'] = result_df['Thay đổi GT %'].apply(lambda x: f"{x}%")
    
    # Sắp xếp thứ tự các sàn đúng chuẩn
    custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
    result_df['Chỉ số'] = pd.Categorical(result_df['Chỉ số'], categories=custom_order, ordered=True)
    result_df = result_df.sort_values('Chỉ số')

    # Trích xuất đúng 8 cột cần hiển thị
    cols_to_show = ['Chỉ số', 'Điểm số', 'Thay đổi', '%', 'KL Khớp', 'GT Khớp', 'Thanh khoản %', 'Thay đổi GT %']
    final_df = result_df[cols_to_show]
    
    # 4. Tự động sinh mã HTML từ DataFrame (Tuyệt đối không lệch cột)
    html_output = final_df.to_html(index=False, border=0, classes='table_vn')
    return html_output
