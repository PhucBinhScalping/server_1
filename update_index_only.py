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
        df = df[~df['name'].str.contains('Futures', case=False, na=False)]    # Loại bỏ các dòng có chữ "Futures"
        # Loại bỏ các mã cụ thể
        remove_list = ['Space Exploration Technologies Corp', 'VinFast Auto Ltd. Ordinary Shares (VFS)']
        df = ~df['name'].isin(remove_list)
        
        html = '<table class="world-index-table"><tr><th>Chỉ số</th><th>Giá</th><th>+/-</th><th>%</th></tr>'
        for _, row in df.iterrows():
            try:
                change_pct = float(str(row['change_percent']).replace(',', ''))
                color = 'green' if change_pct >= 0 else 'red'
            except:
                color = 'black'
            html += f"""<tr>
                <td>{row['name']}</td>
                <td style='color:{color}'>{row['last_price']}</td>
                <td style='color:{color}'>{row['change_price']}</td>
                <td style='color:{color}'>{row['change_percent']}%</td>
            </tr>"""
        html += '</table>'
        return html
    except:
        return "Lỗi tải dữ liệu"


def get_gold_index_html():
    # BỎ TRY-EXCEPT để thấy lỗi thật
    df = gia_vang_24money()
    html = '<table class="gold-table"><tr><th>Loại</th><th>Giá</th><th>+/-</th><th>%</th></tr>'
    for _, row in df.iterrows():
        # Kiểm tra xem row['Percent'] có phải là số không
        color = 'green' if float(row['Percent']) >= 0 else 'red'
        html += f"""<tr>
            <td>{row['footer']}</td>
            <td style='color:{color}'>{row['Last']}</td>
            <td style='color:{color}'>{row['change']}</td>
            <td style='color:{color}'>{row['Percent']}%</td>
        </tr>"""
    html += '</table>'
    return html

def update_world_table():
    world_html = get_world_index_html()
    gold_html = get_gold_index_html()
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    target_div = soup.find(id="world-table-container")
    
    if target_div:
        target_div.clear()
        # Flexbox để chia 2 cột
        flex_div = BeautifulSoup(f"""
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 300px;">
                    <h3 style="text-align:center;">Thị trường Thế giới</h3>
                    {world_html}
                </div>
                <div style="flex: 1; min-width: 300px;">
                    <h3 style="text-align:center;">Giá Vàng</h3>
                    {gold_html}
                </div>
            </div>
        """, 'html.parser')
        target_div.append(flex_div)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print("Cập nhật thành công 2 bảng!")

if __name__ == "__main__":
    update_world_table()
