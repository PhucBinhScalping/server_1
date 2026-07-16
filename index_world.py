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
        
        # Lọc
        df = df[~df['name'].str.contains('Futures', case=False, na=False)]
        df = df[~df['name'].isin(['Space Exploration Technologies Corp', 'VinFast Auto Ltd. Ordinary Shares (VFS)'])]
        
        # Chuyển thành HTML với định dạng màu
        html = '<table class="world-index-table"><tr><th>Chỉ số</th><th>Giá</th><th>Thay đổi</th></tr>'
        for _, row in df.iterrows():
            color = 'green' if float(row['change_percent']) >= 0 else 'red'
            html += f"<tr><td>{row['name']}</td><td>{row['last_price']}</td><td style='color:{color}'>{row['change_percent']}%</td></tr>"
        html += '</table>'
        return html
    except:
        return "Không thể tải dữ liệu."
