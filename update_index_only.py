import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

OUTPUT_FILE = "index.html"

def get_world_index_html():
    url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
    head = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=head, timeout=10)
        data = r.json()['data']['world_stock']
        df = pd.DataFrame(data)[['name', 'last_price', 'change_price', 'change_percent']]
        df = df[~df['name'].str.contains('Futures', case=False, na=False)]
        remove_list = ['Space Exploration Technologies Corp', 'VinFast Auto Ltd. Ordinary Shares (VFS)']
        df = df[~df['name'].isin(remove_list)]
        
        # Thêm div bọc ngoài để hỗ trợ cuộn trên điện thoại
        html = '<div class="table-wrapper"><table class="world-index-table"><tr><th>Chỉ số</th><th>Giá</th><th>+/-</th><th>%</th></tr>'
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
        html += '</table></div>'
        return html
    except:
        return "Lỗi tải dữ liệu"

def get_gold_index_html():
    url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
    head = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get(url, headers=head, timeout=10)
        data = r.json()['data']['gold_price']
        
        df = pd.DataFrame(data)
        df['Percent_val'] = pd.to_numeric(df['Percent'].str.replace('%', '').str.replace(',', ''), errors='coerce')
        df['Last_clean'] = df['Last'].str.replace('N', '').str.strip()
        
        # Thêm div bọc ngoài tương tự để hỗ trợ responsive
        html = '<div class="table-wrapper"><table class="gold-table"><tr><th>Loại</th><th>Giá</th><th>+/-</th><th>%</th></tr>'
        
        for _, row in df.iterrows():
            try:
                pct = float(row['Percent_val'])
                color = 'green' if pct >= 0 else 'red'
            except:
                color = 'black'
            
            html += f"""<tr>
                <td>{row['footer']}</td>
                <td style='color:{color}'>{row['Last_clean']}</td>
                <td style='color:{color}'>{row['change']}</td>
                <td style='color:{color}'>{row['Percent']}</td>
            </tr>"""
        
        html += '</table></div>'
        return html
    except Exception as e:
        return f"<p>Lỗi tải vàng: {e}</p>"

def update_world_table():
    world_html = get_world_index_html()
    gold_html = get_gold_index_html()
    vn_time = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%d-%m-%Y %H:%M:%S')
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    target_div = soup.find(id="world-table-container")
    
    if target_div:
        target_div.clear()
        market_tables_content = f"""
        <div style="text-align: right; font-size: 13px; color: #666; margin-bottom: 15px; font-style: italic;">
            Cập nhật: {vn_time}
        </div>
        
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 280px; padding-bottom: 20px;">
                <h3 style="text-align:center; margin-bottom: 10px;">Thị trường Thế giới</h3>
                {world_html}
            </div>
            <div style="flex: 1; min-width: 280px;">
                <h3 style="text-align:center; margin-bottom: 10px;">Giá Vàng</h3>
                {gold_html}
            </div>
        </div>
        """
        flex_div = BeautifulSoup(market_tables_content, 'html.parser')
        target_div.append(flex_div)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(str(soup))

if __name__ == "__main__":
    update_world_table()
