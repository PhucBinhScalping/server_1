import requests
import pandas as pd

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
                # Truy cập chính xác vào mảng dữ liệu lịch sử 'Data' phía trong
                history_list = r.get('Data', {}).get('Data', [])
                
                if len(history_list) > 1:
                    # history_list[0] là hôm nay, history_list[1] là phiên trước đó
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
                # Nếu lỗi mạng hoặc lỗi parse thì gán giá trị tránh crash
                data_list.append({'name': name, 'volume_2': 1.0, 'value_2': 1.0})

        # 4. Merge và Tính toán
        result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
        result_df['Thanh khoản %'] = (((result_df['KL Khớp'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1)
        result_df['value/value %'] = (((result_df['GT Khớp'] - result_df['value_2']) / result_df['value_2']) * 100).round(1)
        
        # 5. Định dạng lại bảng
        custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
        result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
        final_df = result_df.sort_values('name').set_index('name')
        
        # 6. Tạo bảng HTML (Thêm tiêu đề cột mới)
        html = '<table class="world-index-table" border="0" style="width:100%; border-collapse:collapse; text-align:center;">'
        html += '<thead><tr><th>Chỉ số</th><th>Điểm số</th><th>Thay đổi</th><th>%</th><th>KL Khớp</th><th>GT Khớp</th><th>Thanh khoản %</th><th>Thay đổi GT %</th></tr></thead><tbody>'
        
        for name, row in final_df.iterrows():
            def get_color(v): return '#dc3545' if v < 0 else '#198754' if v > 0 else 'black'
            
            html += f"<tr><td>{name}</td>"
            html += f"<td style='font-weight:bold;'>{row['Chỉ số']:,.2f}</td>" 
            html += f"<td style='color:{get_color(row['Thay đổi'])}; font-weight:bold;'>{row['Thay đổi']:,.2f}</td>"
            html += f"<td style='color:{get_color(row['%'])}; font-weight:bold;'>{row['%']:.2%}</td>"
            html += f"<td>{row['KL Khớp']:,.0f}</td>"
            html += f"<td>{row['GT Khớp']:,.0f}</td>"
            html += f"<td style='color:{get_color(row['Thanh khoản %'])}; font-weight:bold;'>{row['Thanh khoản %']:.1f}%</td>"
            # Thêm dữ liệu cột Thay đổi Giá trị % vào bảng
            html += f"<td style='color:{get_color(row['Thay đổi GT %'])}; font-weight:bold;'>{row['Thay đổi GT %']:.1f}%</td></tr>"
            
        html += '</tbody></table>'
        return html

    except Exception as e:
        return f"<p style='color:red;'>Lỗi tải dữ liệu bảng giá: {e}</p>"
