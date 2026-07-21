import requests
import pandas as pd
import json
from datetime import datetime
from user_agent import random_user

def get_data_index():
    try:
        headers = {"User-Agent": random_user()}
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', headers=headers, timeout=10)
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
                    first_item_date = str(first_item.get('Ngay', first_item.get('ngay', '')))
                    
                    if first_item_date == today_str:
                        prev_day = history_list[1] if len(history_list) > 1 else history_list[0]
                    else:
                        prev_day = history_list[0]

                vol_kl = float(str(prev_day.get('KhoiLuongKhopLenh', prev_day.get('khoiLuongKhopLenh', '0')) or 0).replace(',', ''))
                vol_tt = float(str(prev_day.get('KLThoaThuan', prev_day.get('khoiLuongThoaThuan', '0')) or 0).replace(',', ''))
                val_kl = float(str(prev_day.get('GiaTriKhopLenh', prev_day.get('giaTriKhopLenh', '0')) or 0).replace(',', ''))
                val_tt = float(str(prev_day.get('GtThoaThuan', prev_day.get('giaTriThoaThuan', '0')) or 0).replace(',', ''))

                vol_raw = vol_kl + vol_tt
                val_raw = val_kl + val_tt  # Lấy giá trị thô không nhân/chia

                data_list.append({
                    'name': name, 
                    'volume_2': vol_raw if vol_raw > 0 else 0.0, 
                    'value_2': val_raw if val_raw > 0 else 0.0
                })
                
            except Exception:
                data_list.append({'name': name, 'volume_2': 0.0, 'value_2': 0.0})

        result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')

        # CHUẨN HÓA ĐỘNG (Dynamic Normalization) ĐƯA CẢ 2 VỀ CÙNG ĐƠN VỊ ĐỒNG
        def normalize_to_dong(val):
            if val <= 0: return 0.0
            if val < 100000:          # Nếu là Tỷ đồng (VD: 23092.4)
                return val * 1_000_000_000
            elif val < 100000000:     # Nếu là Triệu đồng
                return val * 1_000_000
            return val                # Nếu đã là Đồng

        # Áp dụng chuẩn hóa cho cả hiện tại và lịch sử
        result_df['value_dong'] = result_df['value'].apply(normalize_to_dong)
        result_df['value_2_dong'] = result_df['value_2'].apply(normalize_to_dong)

        def get_color(v):
            return '#198754' if v > 0 else '#dc3545' if v < 0 else '#000000'

        # Tính % Thanh khoản
        result_df['Thanh khoản %'] = result_df.apply(
            lambda r: round(((r['volume'] - r['volume_2']) / r['volume_2']) * 100, 2) if r['volume_2'] > 0 else 0.0, 
            axis=1
        )
        
        # Tính % Thay đổi Giá trị chính xác tuyệt đối (trên cùng đơn vị Đồng)
        result_df['Thay đổi GT %'] = result_df.apply(
            lambda r: round(((r['value_dong'] - r['value_2_dong']) / r['value_2_dong']) * 100, 2) if r['value_2_dong'] > 0 else 0.0, 
            axis=1
        )

        custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
        result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
        result_df = result_df.sort_values('name')

        html = '<table border="0"><thead><tr>'
        html += '<th>Chỉ số</th><th>Điểm số</th><th>Thay đổi</th><th>%</th><th>KL Khớp</th><th>GT Khớp (Tỷ)</th><th>Thanh khoản %</th>'
        html += '</tr></thead><tbody>'
        
        for _, row in result_df.iterrows():
            color_chg = get_color(row['change'])
            color_per = get_color(row['percent'])
            color_tk = get_color(row['Thanh khoản %'])
            color_gt = get_color(row['Thay đổi GT %'])
            
            # Hiển thị GT Khớp theo Tỷ đồng chuẩn
            display_value = row["value_dong"] / 1_000_000_000
            
            html += '<tr>'
            html += f'<td style="font-weight:bold;">{row["name"]}</td>'
            html += f'<td style="font-weight:bold;">{row["diem_so"]:,.2f}</td>'
            html += f'<td style="color:{color_chg}; font-weight:bold;">{row["change"]:,.2f}</td>'
            html += f'<td style="color:{color_per}; font-weight:bold;">{row["percent"]:.2%}</td>'
            html += f'<td>{row["volume"]:,.0f}</td>'
            html += f'<td>{display_value:,.1f}</td>'
            html += f'<td style="color:{color_tk}; font-weight:bold;">{row["Thanh khoản %"]}%</td>'
            #html += f'<td style="color:{color_gt}; font-weight:bold;">{row["Thay đổi GT %"]}%</td>'
            html += '</tr>'
            
        html += '</tbody></table>'
        return html

    except Exception as e:
        return f"<p style='color:red;'>Lỗi tổng thể hệ thống: {e}</p>"
