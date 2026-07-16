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



def gia_vang_24money():
    url = 'https://api-finance-t19.24hmoney.vn/v1/ios/world-stock/all?device_id=web1723350utptenhuf4a5wu7r8rvgjjohs1qjvbq8468116'
    r = requests.get(url, head)
    data = r.json()['data']['gold_price']
    
    df = pd.DataFrame(data)[['Last', 'footer', 'text', 'Percent', 'change', 'symbol', 'extra_name']].assign(
        change=lambda x: pd.to_numeric(x['change'], errors='coerce'),
        Percent=lambda x: pd.to_numeric(x['Percent'].str.replace('%', '').str.strip(), errors='coerce') / 100,
        Last=lambda x: x['Last'].str.replace('N', '').str.strip()
    )
    df=df[['footer','Last','Percent','change']]
    
    return df
