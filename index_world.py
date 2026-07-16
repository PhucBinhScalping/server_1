import xlwings as xw
import datetime as dt
import pandas as pd
from datetime import date
import requests
import time
from user_agent import random_user
import RStockvn as rpv
from selenium.webdriver.common.by import By
from selenium import webdriver
import gdown
from datetime import datetime
from datetime import timedelta
from bs4 import BeautifulSoup
import json
import html5lib
head={"User-Agent":random_user()}
def get_index_stock_world():
    url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
    r = requests.get(url, headers=head)
    
    df = pd.DataFrame(r.json()['data']['world_stock'])[['name', 'last_price', 'change_price', 'change_percent']]
    df['change_percent'] = pd.to_numeric(df['change_percent'])
    # --- ĐOẠN MÃ LỌC DỮ LIỆU BẠN CẦN THÊM ---
    # Loại bỏ các dòng có chữ "Futures"
    condition_not_futures = ~df['name'].str.contains('Futures', case=False, na=False)
    
    # Loại bỏ các mã cụ thể
    remove_list = ['Space Exploration Technologies Corp', 'VinFast Auto Ltd. Ordinary Shares (VFS)']
    condition_not_specific_items = ~df['name'].isin(remove_list)
    
    # Cập nhật lại df đã lọc
    df = df[condition_not_futures & condition_not_specific_items]
    # ----------------------------------------
    
    return df
