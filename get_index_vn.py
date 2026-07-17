import requests
import pandas as pd

def get_data_index():
    try:
        # 1. Lấy dữ liệu bảng giá chính
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', timeout=10)
        results_vni = re_vni_url.json()
        
        # 2. Tạo DataFrame
        df = pd.DataFrame(results_vni)
        name_map = {'VN-Index': 'VNINDEX', 'VN30-Index': 'VN30', 'HNXINDEX': 'HNX', 'HNX30-Index': 'HNX30', 'HNXUPCOMINDEX': 'UPCOM'}
        df['name'] = df['name'].replace(name_map)
        
        # Lọc danh sách an toàn
        df = df[df['name'].isin(name_map.values())].copy()
        
        # Chuyển đổi dữ liệu
        df['change'] = pd.to_numeric(df['change'], errors='coerce').fillna(0)
        df['percent'] = pd.to_numeric(df['percent'], errors='coerce').fillna(0) / 100
        df['volume'] = pd.to_numeric(df['volume'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['value'] = pd.to_numeric(df['value'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['index'] = pd.to_numeric(df['index'], errors='coerce').fillna(0)

        # 3. Lấy dữ liệu lịch sử
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
                vol_raw = str(r['Data']['Data'][1]['KhoiLuongKhopLenh']).replace(',', '')
                data_list.append({'name': name, 'volume_2': float(vol_raw)})
            except:
                data_list.append({'name': name, 'volume_2': 1.0})

        # 4. Merge và Tính toán
        result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
        result_df['thanh khoản'] = (((result_df['volume'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1)
        
        # 5. Định dạng
        custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
        result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
        result_df = result_df.sort_values('name').set_index('name')
        
        cols_to_use = ['index', 'change', 'percent', 'volume', 'value', 'thanh khoản']
        final_df = result_df.reindex(columns=cols_to_use).fillna(0)
        final_df.columns = ['Chỉ số', 'Thay đổi', '%', 'KL Khớp', 'GT Khớp', 'Thanh khoản %']
        
        # 6. Tạo bảng HTML thủ công (Thay thế cho .style để không cần jinja2)
        html = '<table class="world-index-table" border="0" style="width:100%; border-collapse:collapse; text-align:center;">'
        html += '<thead><tr><th>Chỉ số</th><th>Thay đổi</th><th>%</th><th>KL Khớp</th><th>GT Khớp</th><th>Thanh khoản %</th></tr></thead><tbody>'
        
        for name, row in final_df.iterrows():
            def get_color(v): return '#dc3545' if v < 0 else '#198754' if v > 0 else 'black'
            
            html += f"<tr><td>{name}</td>"
            html += f"<td style='color:{get_color(row['Thay đổi'])}; font-weight:bold;'>{row['Thay đổi']:,.2f}</td>"
            html += f"<td style='color:{get_color(row['%'])}; font-weight:bold;'>{row['%']:.2%}</td>"
            html += f"<td>{row['KL Khớp']:,.0f}</td>"
            html += f"<td>{row['GT Khớp']:,.0f}</td>"
            html += f"<td style='color:{get_color(row['Thanh khoản %'])}; font-weight:bold;'>{row['Thanh khoản %']:.1f}%</td></tr>"
            
        html += '</tbody></table>'
        return html

    except Exception as e:
        return f"<p style='color:red;'>Lỗi tải dữ liệu bảng giá: {e}</p>"
