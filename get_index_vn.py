import requests
import pandas as pd

def get_data_index():
    try:
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', timeout=10)
        results_vni = re_vni_url.json()
        name_map = {'VN-Index': 'VNINDEX', 'VN30-Index': 'VN30', 'HNXINDEX': 'HNX', 'HNX30-Index': 'HNX30', 'HNXUPCOMINDEX': 'UPCOM'}
        df = pd.DataFrame(results_vni)
        df['name'] = df['name'].replace(name_map)
        df['change'] = pd.to_numeric(df['change'], errors='coerce')
        df['percent'] = pd.to_numeric(df['percent'], errors='coerce') / 100
        df['volume'] = df['volume'].astype(str).str.replace(',', '').astype(float)
        df['value'] = df['value'].astype(str).str.replace(',', '').astype(float)
    except Exception as e:
        return f"Lỗi lấy dữ liệu bảng giá: {e}"

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
            vol = float(str(r['Data']['Data'][1]['KhoiLuongKhopLenh']).replace(',', ''))
            data_list.append({'name': name, 'volume_2': vol})
        except:
            data_list.append({'name': name, 'volume_2': None})

    result_df = pd.merge(df, pd.DataFrame(data_list), on='name', how='left')
    result_df['thanh khoản'] = (((result_df['volume'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1)
    
    # Sắp xếp
    custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
    result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
    result_df = result_df.sort_values('name').set_index('name')
    
    # Đổi tên cột
    result_df.columns = ['Chỉ số', 'Thay đổi', '%', 'KL Khớp', 'GT Khớp', 'Thanh khoản %']
    
    # Định dạng màu sắc
    def style_cells(val):
        try:
            v = float(val)
            color = '#dc3545' if v < 0 else '#198754' if v > 0 else 'black'
            return f'color: {color}; font-weight: bold;'
        except: return ''

    # Áp dụng Style
    styled = result_df.style.applymap(style_cells, subset=['Thay đổi', '%', 'Thanh khoản %']) \
        .format({'Thay đổi': '{:,.2f}', '%': '{:.2%}', 'Thanh khoản %': '{:.1f}%', 'KL Khớp': '{:,.0f}', 'GT Khớp': '{:,.0f}'})
        
    return styled.to_html(classes='world-index-table', border=0, justify='center')
