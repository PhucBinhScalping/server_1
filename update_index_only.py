# update_index_only.py
import requests
import pandas as pd
from bs4 import BeautifulSoup

OUTPUT_FILE = "index.html"

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
        
        # Tạo HTML bảng
        html = '<table class="world-index-table"><tr><th>Chỉ số</th><th>Giá</th><th>Thay đổi</th></tr>'
        for _, row in df.iterrows():
            # Chuyển đổi an toàn sang float để so sánh màu
            try:
                change = float(row['change_percent'])
                color = 'green' if change >= 0 else 'red'
            except:
                color = 'black'
            
            html += f"<tr><td>{row['name']}</td><td>{row['last_price']}</td><td style='color:{color}'>{row['change_percent']}%</td></tr>"
        html += '</table>'
        return html
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu: {e}")
        return "<p>Không thể tải dữ liệu thị trường thế giới.</p>"

def update_world_table():
    # 1. Lấy dữ liệu bảng mới nhất
    new_table_html = get_world_index_html()
    
    # 2. Đọc file index.html hiện tại
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        # 3. Tìm vị trí đặt bảng có id="world-table-container"
        target_div = soup.find(id="world-table-container")
        
        if target_div:
            target_div.clear()
            target_div.append(BeautifulSoup(new_table_html, 'html.parser'))
            
            # 4. Ghi đè lại file
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            print("Cập nhật chỉ số thế giới vào index.html thành công!")
        else:
            print("Không tìm thấy <div id='world-table-container'> trong file index.html.")
    except FileNotFoundError:
        print(f"Không tìm thấy file {OUTPUT_FILE}")

if __name__ == "__main__":
    update_world_table()
