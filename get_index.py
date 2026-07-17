import requests
import pandas as pd

def get_data_index():
    # 1. Lấy dữ liệu CafeF hiện tại
    try:
        re_vni_url = requests.get('https://banggia.cafef.vn/stockhandler.ashx?index=true', timeout=10)
        results_vni = re_vni_url.json()
        name_map = {'VN-Index': 'VNINDEX', 'VN30-Index': 'VN30', 'HNXINDEX': 'HNX', 'HNX30-Index': 'HNX30', 'HNXUPCOMINDEX': 'UPCOM'}
        df = pd.DataFrame(results_vni)
        df['name'] = df['name'].replace(name_map)
        df['change'] = pd.to_numeric(df['change'], errors='coerce')
        df['percent'] = pd.to_numeric(df['percent'], errors='coerce') / 100
        # Xử lý volume: loại bỏ dấu phẩy và chuyển sang số nguyên
        df['volume'] = df['volume'].astype(str).str.replace(',', '').astype(float)
        df['value'] = df['value'].astype(str).str.replace(',', '').astype(float)
    except Exception as e:
        return f"Lỗi lấy dữ liệu bảng giá: {e}"

    # 2. Định nghĩa URLs
    urls = {
        'VNINDEX': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=VNINDEX&PageIndex=1&PageSize=20',
        'VN30': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HOSE&Symbol=VN30INDEX&PageIndex=1&PageSize=20',
        'HNX': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HNX&Symbol=HNX-INDEX&PageIndex=1&PageSize=20',
        'UPCOM': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=UPCOM&Symbol=UPCOM-INDEX&PageIndex=1&PageSize=20',
        'HNX30': 'https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?ExchangeType=HNX&Symbol=HNX30-INDEX&PageIndex=1&PageSize=20'
    }

    # 3. Hàm lấy khối lượng ngày hôm trước
    def get_prev_volume(data_json):
        try:
            # history_list[1] là ngày hôm trước
            history_list = data_json['Data']['Data']
            vol_raw = str(history_list[1]['KhoiLuongKhopLenh']).replace(',', '')
            return float(vol_raw)
        except:
            return None

    # 4. Fetch dữ liệu lịch sử
    data_list = []
    for name, url in urls.items():
        try:
            response = requests.get(url, timeout=5)
            val = get_prev_volume(response.json())
            data_list.append({'name': name, 'volume_2': val})
        except:
            data_list.append({'name': name, 'volume_2': None})

    df_t = pd.DataFrame(data_list)
    
    # 5. Merge và tính toán tỷ lệ thanh khoản (Volume/Volume)
    result_df = pd.merge(df, df_t, on='name', how='left')
    
    # Tính tỷ lệ thay đổi khối lượng: (Vol hôm nay - Vol hôm qua) / Vol hôm qua
    result_df['thanh khoản'] = (((result_df['volume'] - result_df['volume_2']) / result_df['volume_2']) * 100).round(1).astype(str) + '%'
    
    # Sắp xếp theo thứ tự
    custom_order = ['VNINDEX', 'VN30', 'HNX', 'HNX30', 'UPCOM']
    result_df['name'] = pd.Categorical(result_df['name'], categories=custom_order, ordered=True)
    result_df = result_df.sort_values('name')
    
    # Trả về bảng kết quả
    return result_df[['name', 'index', 'change', 'percent', 'volume', 'value', 'thanh khoản']].set_index('name')
