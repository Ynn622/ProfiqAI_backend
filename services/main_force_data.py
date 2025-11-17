from bs4 import BeautifulSoup as bs
import pandas as pd
import cloudscraper
import numpy as np
from util.config import Env  # 確保環境變數被載入
from util.supabase_client import supabase

scraper = cloudscraper.create_scraper()   # 防檔爬蟲用

def main_force_all_days(stock_id, date_list):
    """
    爬取主力所有資料
    Args:
        stock_id(str): 股票代號
        date_list(list): 日期列表 ex. ['2024-05-10', '2024-05-11']
    """
    stock_id = stock_id.split('.')[0]  # 去除可能的後綴
    main_force_list = []
    # 從 Supabase 獲取已存在的主力資料
    sql_response = (
        supabase.table("stockMainForceData")
        .select("date, mainForce")
        .eq("stock_id", stock_id)
        .gte("date", date_list[0])   # 日期 >= 起始日
        .order("date")
        .execute()
    )
    sql_df = None
    sql_preupload = []

    if len(sql_response.data):
        if Env.RELOAD: print(f" Find: {stock_id} supabase 已存在！")
        sql_df = pd.DataFrame(sql_response.data).set_index("date")
        sql_df.index = pd.to_datetime(sql_df.index)

    for date in date_list:
        if Env.RELOAD: print(f"\r主力資料截取中：{date}", end="")
        # 檢查 Supabase 是否已有資料
        if (sql_df is not None) and (date in sql_df.index):
            main_force_list.append(sql_df.loc[date, "mainForce"])
            continue
        
        result = None
        while result is None:
          result = main_force_one_day(stock_id, date)
        main_force_list.append(result[0]-result[1])
        if result == (np.nan, np.nan):
            print(f"\r  Alert: {date} 無主力資料，跳過！")
            continue  # 如果沒有資料，不存入資料庫
        sql_preupload.append({
            "stock_id": stock_id,
            "date": str(date),
            "mainForce": result[0] - result[1]
        })

    # 儲存到 Supabase
    if len(sql_preupload):
        print(f"\r儲存主力資料中...{' '*15}", end="")
        response = (
            supabase.table("stockMainForceData")
            .insert(sql_preupload)
            .execute()
        )

    main_force_df = pd.DataFrame(main_force_list, columns=["主力買賣超"], index=date_list)
    
    if Env.RELOAD: print(f"\r Done: 主力資料-載入完畢！")
    return main_force_df

def main_force_one_day(stock_id, date):
    """
    main_force_all_days() 調用的輔助函數：爬取單日主力買賣超資料
    """
    try:
        url = f'https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco.djhtm?a={stock_id}&e={date}&f={date}'
        web = scraper.get(url).text
        web_bs = bs(web, 'html.parser')
        web_find = web_bs.find("tr", id="oScrollFoot")
        if web_find is None: return np.nan, np.nan  # 如果沒有資料，返回 NaN
        buysell = web_find.find_all("td", class_="t3n1")    # 買賣超 欄位
        buy_value = int(buysell[0].text.replace(",", ""))   # 買超
        sell_value = int(buysell[1].text.replace(",", ""))  # 賣超
        return buy_value, sell_value
    except Exception as e:
        print(f" \n{date} 發生錯誤：{e}")
        return None