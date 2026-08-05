import pandas as pd
import requests
import plotly.graph_objects as io_go
from datetime import datetime, timedelta
import pytz
from user_agent import random_user

HEAD = {
    "User-Agent": random_user()
}

def tinh_du_lieu_cp(symbol):
    try:
        clean_symbol = str(symbol).strip().upper()
        
        todate = datetime.now()
        fromdate = todate - timedelta(days=156)

        from_timestamp = int(fromdate.timestamp())
        to_timestamp = int(todate.timestamp())

        symbols_to_try = [f"HOSE:{clean_symbol}", f"HNX:{clean_symbol}", f"UPCOM:{clean_symbol}", clean_symbol]
        res_json = None

        for sym in symbols_to_try:
            url = f"https://web7.vps.com.vn/trading-view/api/public/history?symbol={sym}&resolution=1D&from={from_timestamp}&to={to_timestamp}"
            try:
                r = requests.get(url, headers=HEAD, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    if data and data.get("s") == "ok":
                        res_json = data
                        break
            except Exception:
                continue

        if not res_json:
            return None

        df = pd.DataFrame({
            "timestamp": res_json["t"],
            "close": res_json["c"],
            "volume": res_json["v"],
        })

        if df.empty:
            return None

        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s") + timedelta(hours=7)
        df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")
        df = df.sort_values(by="date").reset_index(drop=True)

        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["pctChange"] = df["close"].pct_change() * 100

        # LƯU Ý: Hạ hoặc bỏ hẳn điều kiện lọc volume nếu muốn ĐẢM BẢO hiện đủ 30 mã VN30
        if len(df) < 100:  
            return None

        df_desc = df.sort_values(by="date", ascending=False).reset_index(drop=True)
        last = df_desc.iloc[0]

        bd_gia = (
            round(float(last["pctChange"]), 2)
            if pd.notnull(last["pctChange"])
            else 0.0
        )
        vol_mean_21 = df_desc["volume"].iloc[:21].mean()
        kl_tb21 = (
            round(float(last["volume"] / vol_mean_21), 2)
            if vol_mean_21 > 0
            else 0.0
        )

        return {"bd_gia": bd_gia, "kl_tb21": kl_tb21}
    except Exception as e:
        print(f"Lỗi mã {symbol}: {e}")
        return None


def main():
    list_vn30 = [
        'ACB', 'BID', 'BSR', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'LPB', 
        'MBB', 'MCH', 'MSN', 'MWG', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 
        'TCX', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VPL', 'VRE'
    ]
    kq_vn30 = []
    
    for i in list_vn30:
        data = tinh_du_lieu_cp(i)
        if data is not None:
            kq_vn30.append({
                'name': i, 
                'percent_change': data['bd_gia'], 
                'volume_ratio': data['kl_tb21']
            })
        else:
            # Nếu không lấy được dữ liệu, vẫn add giá trị 0 để không xót mã nào
            kq_vn30.append({
                'name': i,
                'percent_change': 0.0,
                'volume_ratio': 0.0
            })

    df_final = pd.DataFrame(kq_vn30).sort_values('percent_change', ascending=True)
    
    if df_final.empty:
        print("Không có dữ liệu thỏa mãn điều kiện.")
        return

    vn_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    time_str = vn_now.strftime('%d-%m-%Y %H:%M:%S')
    
    # Màu sắc: Xanh (>0), Đỏ (<0), Xám/Vàng (==0)
    colors = [
        '#198754' if x > 0 else ('#dc3545' if x < 0 else '#6c757d') 
        for x in df_final['percent_change']
    ]
    
    fig = io_go.Figure()
    
    # Thêm Bar Chart với viền marker để hiện rõ vạch 0.0%
    fig.add_trace(io_go.Bar(
        x=df_final['name'], 
        y=df_final['percent_change'], 
        marker_color=colors, 
        marker_line_color='white',  # Viền trắng giúp vạch 0.0% nổi bật
        marker_line_width=1.5,
        name='BĐ giá', 
        texttemplate='%{y:.1f}%', 
        textposition='outside',
        cliponaxis=False  # Giúp nhãn text không bị đè/mất khi sát mép
    ))
    
    # Line Chart cho Volume
    fig.add_trace(io_go.Scatter(
        x=df_final['name'], 
        y=df_final['volume_ratio'], 
        yaxis='y2', 
        line=dict(color='#FFD700', width=3), 
        name='KL/TB21'
    ))
    
    fig.update_layout(
        title=f"Biến động ngành {time_str}",
        paper_bgcolor='#333333', plot_bgcolor='#333333', font=dict(color='white'),
        height=500, margin=dict(l=20, r=20, t=50, b=120),
        yaxis=dict(title='BĐ giá (%)', zeroline=True, zerolinecolor='white', zerolinewidth=1),
        yaxis2=dict(title='KL/TB21', overlaying='y', side='right'),
        xaxis=dict(tickangle=-45, type='category'), # 'category' giữ đúng thứ tự 30 mã
        autosize=True              
    )
    
    fig.show()


if __name__ == "__main__":
    main()
