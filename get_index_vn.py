import requests
import pandas as pd
import json
from datetime import datetime
from user_agent import random_user

def get_data_index():
    try:
        # 1. Lấy dữ liệu CafeF hiện tại từ bảng giá trực tuyến
        headers = {"User-Agent": random_user()}
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', headers=headers, timeout=10)
        results_vni = re_vni_url.json()
        name_map = {'VN-Index': 'VNINDEX', 'VN30-Index': 'VN30', 'HNXINDEX': 'HNX', 'HNX30-Index': 'HNX30', 'HNXUPCOMINDEX': 'UPCOM'}
        
        df = pd.DataFrame(results_vni)
        df['name'] = df['name'].replace(name_map)
        df = df[df['name'].isin(name_map.values())].copy()
        
        # Chuyển đổi dữ liệu số từ bảng giá trực tuyến
        if 'mc' in df.columns:
            df['diem_so'] = pd.to_numeric(df['mc'].astype(str).str.replace(',', ''), errors='coerce')
        else:
            df['diem_so'] = pd.to_numeric(df['index'].astype(str).str.replace(',', ''), errors='coerce')
            
        df['change'] = pd.to_numeric(df['change'], errors='coerce').fillna(0)
        df['percent'] = pd.to_numeric(df['percent'], errors='coerce').fillna(0) / 100
        df['volume'] = df['volume'].astype(str).str.replace(',', '', regex=False).astype(float).fillna(0)
        df['value'] = df['value'].astype(str).str.replace(',', '', regex=False).astype(float).fillna(0)

        # 2. Cấu hình Parameter Symbol chuẩn hóa theo API Lịch sử CafeF
        urls = {
            'VNINDEX': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=VNINDEX&PageIndex=1&PageSize=20',
            'VN30': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=VN30INDEX&PageIndex=1&PageSize=20',
            'HNX': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HNX&Symbol=HNX-INDEX&PageIndex=1&PageSize=20',
            'HNX30': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HNX&Symbol=HNX30-INDEX&PageIndex=1&PageSize=20',
            'UPCOM': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=UPCOM&Symbol=UPCOM-INDEX&PageIndex=1&PageSize=20'
        }

        today_str = datetime.now().strftime('%d/%m/%Y')
        data_list = []
        
        for name, url in urls.items():
            try:
                res = requests.get(url, headers=headers, timeout=5)
                try:
                    r = res.json()
                except:
                    r = json.loads(res.text)
                
                # Bóc tách lớp Dictionary 'Data' lồng nhau của CafeF Index
                history_list = r.get('Data', [])
                if isinstance(history_list, str):
                    history_list = json.loads(history_list)
                
                if isinstance(history_list, dict):
                    for k, v in history_list.items():
                        if isinstance(v, list) and len(v) > 0:
                            history_list = v
                            break
                
                prev_day = {}
                if isinstance(history_list, list) and len(history_list) > 0:
                    first_item = history_list[0]
                    first_item_date = first_item.get('Ngay', first_item.get('ngay', ''))
                    
                    # Nếu trùng ngày hôm nay, lấy dòng index 1 (phiên trước đó)
                    if first_item_date == today_str:
                        prev_day = history_list[1] if len(history_list) > 1 else history_list[0]
                    else:
                        prev_day = history_list[0]

                vol_raw = str(prev_day.get('KhoiLuongKhopLenh', prev_day.get('khoiLuongKhopLenh', '0'))).replace(',', '')
                val_raw = str(prev_day.get('GiaTriKhopLenh', prev_day.get('giaTriKhopLenh', '0'))).replace(',', '')
                
                v_2 = float(vol_raw) if vol_raw and float(vol_raw) > 0 else 1.0
                val_2 = float(val_raw) if val_raw and float(val_raw) > 0 else 1.0
                
                if val_2 < 100000:  
                    val_2 = val_2 * 1000000000
                
                data_list.append({'name': name, 'volume_2': v_2, 'value_2': val_2})
                
            except Exception:
                data_list.append({'name': name, 'volume_2': 1.0, 'value_2': 1.0})

        # 3. Tiến hành gộp dữ liệu và tính toán tỷ lệ % thay đổi
        result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
        
        # Chuẩn hoá cột dữ liệu value hiện tại từ bảng giá về cùng đơn vị gốc
        for idx, row in result_df.iterrows():
            if row['value'] < 100000:
                result_df.at[idx, 'value'] = row['value'] * 1000000000


        def get_color(v):
            return '#198754' if v > 0 else '#dc3545' if v < 0 else '#000000'
        # Hàm tính phần trăm thay đổi thanh khoản
        def calc_pct(row, col_now, col_prev):
            now = row[col_now]
            prev = row[col_prev]
            if prev == 1.0 or now == 0: return 0.0
            return ((now - prev) / prev) * 100

        result_df['Thanh khoản %'] = result_df.apply(lambda r: calc_pct(r, 'volume', 'volume_2'), axis=1).round(1)
        result_df['Thay đổi GT %'] = result_df.apply(lambda r: calc_pct(r, 'value', 'value_2'), axis=1).round(1)
        
        # Sắp xếp hiển thị theo thứ tự mong muốn
        custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
        result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
        result_df = result_df.sort_values('name').reset_index(drop=True)
        
        # Lọc giữ lại các cột cần thiết để bảng nhìn gọn gàng
        output_cols = ['name', 'diem_so', 'change', 'percent', 'volume', 'value', 'Thanh khoản %', 'Thay đổi GT %']
        result_df=result_df[output_cols]
        html = '<table border="0"><thead><tr>'
        html += '<th>Chỉ số</th><th>Điểm số</th><th>Thay đổi</th><th>%</th><th>KL Khớp</th><th>GT Khớp</th><th>Thanh khoản %</th><th>Thay đổi GT %</th>'
        html += '</tr></thead><tbody>'
        
        for _, row in result_df.iterrows():
            color_chg = get_color(row['change'])
            color_per = get_color(row['percent'])
            color_tk = get_color(row['Thanh khoản %'])
            color_gt = get_color(row['Thay đổi GT %'])
            
            # Hiển thị Giá trị Khớp lệnh thân thiện (Chia lại cho 1 tỷ để gọn bảng nếu số quá lớn)
            display_value = row["value"]
            if display_value > 1000000:
                display_value = display_value / 1000000000
            
            html += '<tr>'
            html += f'<td style="font-weight:bold;">{row["name"]}</td>'
            html += f'<td style="font-weight:bold;">{row["diem_so"]:,.2f}</td>'
            html += f'<td style="color:{color_chg}; font-weight:bold;">{row["change"]:,.2f}</td>'
            html += f'<td style="color:{color_per}; font-weight:bold;">{row["percent"]:.2%}</td>'
            html += f'<td>{row["volume"]:,.0f}</td>'
            html += f'<td>{display_value:,.0f}</td>'
            html += f'<td style="color:{color_tk}; font-weight:bold;">{row["Thanh khoản %"]}%</td>'
            html += f'<td style="color:{color_gt}; font-weight:bold;">{row["Thay đổi GT %"]}%</td>'
            html += '</tr>'
            
        html += '</tbody></table>'
        
        return html
        
    except Exception as e:
        print(f"Lỗi tổng thể hệ thống: {e}")
        return pd.DataFrame()
