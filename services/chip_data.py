import pandas as pd
import cloudscraper
import numpy as np
from datetime import date, timedelta

from util.config import Env  # 確保環境變數被載入
from services.function_tools import fetchStockInfo, getStockPrice, get_margin_data
from services.main_force_data import main_force_all_days

scraper = cloudscraper.create_scraper()   # 防檔爬蟲用

#定義計算連續買賣超狀態
def calculate_consecutive_status(column):
    result = []
    last_status = None
    count = 0
    for num in column:
        status = 1 if num >= 0 else -1
        count = count + 1 if status == last_status else 1
        last_status = status
        result.append(status*count)
    return result

def calculate_chip_indicators(stock_id: str):
    start_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")  # 最近30天資料
    stock_id, stock_name = fetchStockInfo(stock_id)
    stock_data = getStockPrice(stock_id, start_date)
    main_force_data = main_force_all_days(stock_id, stock_data.index)
    margin_data = get_margin_data(stock_id, start_date, select_columns=['融資增減', '融資餘額', '融券增減', '融券餘額', '融券券資比%'])
    df = pd.concat([stock_data, main_force_data, margin_data], axis=1, join='inner')

    df['外資連續買賣'] = calculate_consecutive_status(df['外資'])
    df['投信連續買賣'] = calculate_consecutive_status(df['投信'])
    df['自營連續買賣'] = calculate_consecutive_status(df['自營商'])
    df['主力連續買賣'] = calculate_consecutive_status(df['主力買賣超'])

    # 求出佔比
    df['外資佔比'] = (df['外資'].abs() / df['Volume']).round(4)
    df['投信佔比'] = (df['投信'].abs() / df['Volume']).round(4)
    df['自營商佔比'] = (df['自營商'].abs() / df['Volume']).round(4)
    df['主力買賣超佔比'] = (df['主力買賣超'].abs() / df['Volume']).round(4)

    df['Score'] = 0

    # 1. 單日買賣超
    df['Score'] += np.where(df['外資'] > 0, 1, -1)
    df['Score'] += np.where(df['投信'] > 0, 1, -1)
    df['Score'] += np.where(df['自營商'] > 0, 1, -1)
    df['Score'] += np.where(df['主力買賣超'] > 0, 1, -1)

    # 2. 連續買賣天數
    def score_streak(x):
        if x >= 3: return 2
        elif x <= -3: return -2
        else: return 0

    for c in ['外資連續買賣','投信連續買賣','自營連續買賣','主力連續買賣']:
        df['Score'] += df[c].apply(score_streak)

    # 3. 持股佔比
    # 外資佔比
    df['Score'] += np.where(df['外資佔比'] > 0.15, 2,
                    np.where(df['外資佔比'] >= 0.05, 1, 0))

    # 投信佔比
    df['Score'] += np.where(df['投信佔比'] > 0.1, 2,
                    np.where(df['投信佔比'] >= 0.05, 1, 0))

    # 自營商佔比
    df['Score'] += np.where(df['自營商佔比'] > 0.04, 1, 0)

    # 主力買賣超佔比
    df['Score'] += np.where(df['主力買賣超佔比'] > 0.12, 2,
                    np.where(df['主力買賣超佔比'] >= 0.07, 1, 0))

    # 4. 融資券
    # 融資變動比
    df['融資變動比'] = df['融資增減'] / df['融資餘額']
    df['融券變動比'] = df['融券增減'] / df['融券餘額']
    df['Score'] += np.where(df['融資變動比'] > 0.05, -1,
                    np.where(df['融資變動比'] > 0.02, 2,
                    np.where(df['融資變動比'] < -0.05,  -2,
                    np.where(df['融資變動比'] < -0.02,  1, 0))))
    df['Score'] += np.where(df['融券變動比'] > 0.05,  -2,
                    np.where(df['融券變動比'] > 0.02,  1,
                    np.where(df['融券變動比'] < -0.05, -1,
                    np.where(df['融券變動比'] < -0.02, 2, 0))))

    # 融資增減
    df['Score'] += np.where(df['融資增減'] > 0, 1, 0)
    df['Score'] += np.where(df['融資增減'] < 0, -1, 0)

    # 融券增減
    df['Score'] += np.where(df['融券增減'] > 0, -1, 0)
    df['Score'] += np.where(df['融券增減'] < 0, 1, 0)

    # 券資比
    df['Score'] += np.where(df['融券券資比%'] > 0.2, 2,
                    np.where(df['融券券資比%'] >= 0.1, 1, 0))

    df['Score'] += np.where((df['融資增減'] > 0) & (df['融券增減'] < 0), 3, 0)
    df['Score'] += np.where((df['融券增減'] > 0) & (df['融資增減'] < 0), -3, 0)

    df['close_result'] = (df['Close']>df['Close'].shift(1)).astype(int)
    df['accurate'] = (((df['Score'] > 0) & (df['close_result'].shift(-1) == 1)) |((df['Score'] <= 0) & (df['close_result'].shift(-1) == 0))).astype(int)
    df = df.drop(columns=['Volume'])
    df = df.iloc[::-1]
    df['direction'] = np.where(df['Score'] <= 0, -1, 1)
    latestdata = df.iloc[0]
    latestdata_dict = latestdata.to_dict()
    latestdata_dict['date'] = str(df.index[0])  # 加入日期
    return latestdata_dict