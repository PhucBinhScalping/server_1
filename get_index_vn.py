import requests
import pandas as pd
from datetime import datetime
import pytz

def get_data_index():
    try:
        # 1. Lấy dữ liệu bảng giá chính
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', timeout=10)
        results_vni = re_vni_url.json()
        
        # 2. Tạo DataFrame và xử lý cột chỉ số
        df = pd.DataFrame(results_vni)
        
        # Ưu tiên lấy cột 'mc' (thường chứa điểm số) nếu tồn tại
        if 'mc' in df.columns:
            df['index_val'] = df['mc']
        else:
            df['index_val'] = df['index']
            
        name_map = {
            'VN-Index': 'VNINDEX', 
            'VN30-Index': 'VN30', 
            'HNXINDEX': 'HNX', 
            'HNX30-Index': 'HNX30', 
            'HNXUPCOMINDEX': 'UPCOM'
        }
        df['name'] = df['name'].replace(name_map)
        df = df[df['name'].isin(name_map.values())].copy()
        
        # Chuyển đổi dữ liệu - Loại bỏ dấu phẩy trước khi ép kiểu
        df['Chỉ số'] = pd.to_numeric(df['index_val'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['Thay đổi'] = pd.to_numeric(df['change'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['%'] = pd.to_numeric(df['percent'], errors='coerce').fillna(0) / 100
        df['KL Khớp'] = pd.to_numeric(df['volume'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['GT Khớp'] = pd.to_numeric(df['value'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 3. Lấy dữ liệu lịch sử để tính thanh khoản (Cả Volume và Value hôm trước)
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
            except Exception as e:
                data_list.append({'name': name, 'volume_2': 1.0, 'value_2': 1.0})

        # 4. Merge và Tính toán
        result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
        result_df['Thanh khoản %'] = (((result_df['KL Khớp'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1)
        result_df['Thay đổi GT %'] = (((result_df['GT Khớp'] - result_df['value_2']) / result_df['value_2']) * 100).round(1)
        
        # 5. Định dạng lại bảng
        custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
        result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
        final_df = result_df.sort_values('name').set_index('name')
        
        # 6. Lấy thời gian cập nhật hiện tại theo múi giờ VN
        vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
        time_str = vn_now.strftime('%d-%m-%Y %H:%M:%S')

        # 7. Tạo bảng HTML (Ép kiểu inline style để đè đứt CSS cũ của file template)
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
        
        for name, row in final_df.iterrows():
            def get_color(v): return '#dc3545' if v < 0 else '#198754' if v > 0 else 'black'
            
            html += f"<tr style='border-bottom: 1px solid #eee;'>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap; font-weight:bold;'>{name}</td>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap; font-weight:bold;'>{row['Chỉ số']:,.2f}</td>" 
            html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['Thay đổi'])}; font-weight:bold;'>{row['Thay đổi']:,.2f}</td>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['%'])}; font-weight:bold;'>{row['%']:.2%}</td>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap;'>{row['KL Khớp']:,.0f}</td>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap;'>{row['GT Khớp']:,.0f}</td>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['Thanh khoản %'])}; font-weight:bold;'>{row['Thanh khoản %']:.1f}%</td>"
            html += f"<td style='padding: 12px 6px; white-space: nowrap; color:{get_color(row['Thay đổi GT %'])}; font-weight:bold;'>{row['Thay đổi GT %']:.1f}%</td>"
            html += "</tr>"
            
        html += '</tbody></table></div>'
        return html

    except Exception as e:
        return f"<p style='color:red;'>Lỗi tải dữ liệu bảng giá: {e}</p>"
