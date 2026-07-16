# index_world.py
import requests
import pandas as pd

def get_world_index_html():
    url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
    head = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get(url, headers=head, timeout=10)
        data = r.json()['data']['world_stock']
        df = pd.DataFrame(data)[['name', 'last_price', 'change_price', 'change_percent']]
        
        # Lọc dữ liệu
        df = df[~df['name'].str.contains('Futures', case=False, na=False)]
        df = df[~df['name'].isin(['Space Exploration Technologies Corp', 'VinFast Auto Ltd. Ordinary Shares (VFS)'])]
        
        # Chuyển đổi sang định dạng HTML table đẹp mắt
        # Thêm class để CSS trong template xử lý
        html_table = df.to_html(classes='world-index-table', index=False, border=0)
        return html_table
    except Exception as e:
        return "<p>Không thể tải dữ liệu thị trường thế giới.</p>"
