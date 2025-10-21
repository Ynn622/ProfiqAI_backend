from bs4 import BeautifulSoup as bs
import requests
import pandas as pd
from util.logger import Log, Color

def get_PE_Ratio(stockID):
    '''
    獲取 PE Ratio / PE Ratio產業平均。
    '''
    try:
        quoteWeb = requests.get(f'https://tw.stock.yahoo.com/quote/{stockID}')
        quoteSoup = bs(quoteWeb.text, 'html.parser')
        PE_ratio_table = quoteSoup.find_all('span',class_='Fz(16px) C($c-link-text) Mb(4px)')[1].text
        PE_ratio_table = PE_ratio_table.strip(")").split(" (")
        if len(PE_ratio_table) == 1:
            PE_ratio = None
            PE_ratio_compare = None
        else:
            PE_ratio = float(PE_ratio_table[0])
            PE_ratio_compare = float(PE_ratio_table[1])
    except Exception as e:
        Log(f"🔴 [Error] 獲取 PE Ratio 資訊發生錯誤: {str(e)}", color=Color.RED)
        PE_ratio = None
        PE_ratio_compare = None
    
    return {'PE_ratio': PE_ratio, 'PE_ratio_compare': PE_ratio_compare}

def get_revenue(stockID):
    '''
    獲取 MoM / YoY。   
    '''
    try:
        revenueWeb = requests.get(f'https://tw.stock.yahoo.com/quote/{stockID}/revenue')
        revenueSoup = bs(revenueWeb.text, 'html.parser')
        table = revenueSoup.find('div', class_='table-body-wrapper').find_all('li', class_="List(n)")

        rows = []
        for item in table[:12]:    # 這裡控制筆數
            month = item.find('div',class_='W(65px) Ta(start)').text
            detail = list(item.find("ul").stripped_strings)
            rows.append({"Month": month,
                        "MoM": float(detail[1].replace('%','').replace(',','')),
                        "YoY": float(detail[3].replace('%','').replace(',',''))})

        df_momyoy = pd.DataFrame(rows)
        json_momyoy = {
            "month": df_momyoy["Month"].tolist(),
            "mom": df_momyoy["MoM"].tolist(),
            "yoy": df_momyoy["YoY"].tolist()
        }
    except Exception as e:
        Log(f"🔴 [Error] 獲取 MoM/YoY 資訊發生錯誤: {str(e)}", color=Color.RED)
        json_momyoy = {
            "month": [],
            "mom": [],
            "yoy": []
        }
    
    return json_momyoy

def get_EPS(stockID):
    '''
    獲取 EPS。
    '''
    try:
        epsWeb = requests.get(f'https://tw.stock.yahoo.com/quote/{stockID}/eps')
        epsSoup = bs(epsWeb.text, 'html.parser')
        table = epsSoup.find('div', class_='table-body-wrapper').find_all('li', class_="List(n)")

        rows_eps = []
        for item in table[:8]:    # 這邊控制筆數
            row_data = list(item.stripped_strings)
            rows_eps.append({"quarter": row_data[0],"eps": float(row_data[1])})

        df_eps = pd.DataFrame(rows_eps) #.set_index("quarter")
        json_eps = {
            "quarter": df_eps["quarter"].tolist(),
            "eps": df_eps["eps"].tolist()
        }
    except Exception as e:
        Log(f"🔴 [Error] 獲取 EPS 資訊發生錯誤: {str(e)}", color=Color.RED)
        json_eps = {
            "quarter": [],
            "eps": []
        }
    
    return json_eps

def get_profile(stockID):
    '''
    獲取 營業毛利率、資產報酬率、營業利益率、股東權益報酬率、稅前淨利率。
    '''
    try:
        profileWeb = requests.get(f'https://tw.stock.yahoo.com/quote/{stockID}/profile')
        profileSoup = bs(profileWeb.text, 'html.parser')

        financeInfo = profileSoup.find_all('section', class_='Mb($m-module)')[2].find_all('div', recursive=False)
        profitabilityTable = financeInfo[2].find_all('div', recursive=False)

        data_profile = {}

        financial_metrics = {
            "營業毛利率": "GPM",   # Gross Profit Margin
            "資產報酬率": "ROA",   # Return on Assets
            "營業利益率": "OPM",   # Operating Profit Margin
            "股東權益報酬率": "ROE",   # Return on Equity
            "稅前淨利率": "PTPM"   # Pre-tax Profit Margin
        }

        for block in profitabilityTable[:-1]:   # 每股淨值 不要
            items = list(block.stripped_strings)
            key_zh = items[0]  # 中文名稱
            value = float(items[1].replace('%',''))

            if key_zh in financial_metrics:  # 確保有對應縮寫
                key_en = financial_metrics[key_zh]
                data_profile[key_en] = value
    except Exception as e:
        Log(f"🔴 [Error] 獲取 Profile 資訊發生錯誤: {str(e)}", color=Color.RED)
        data_profile = {
            "GPM": None,
            "ROA": None,
            "OPM": None,
            "ROE": None,
            "PTPM": None
        }

    return data_profile

def get_dividend(stockID):
    '''
    獲取 股票股利、現金股利。
    '''
    try:
        dividendWeb = requests.get(f'https://histock.tw/stock/{stockID}/%E9%99%A4%E6%AC%8A%E9%99%A4%E6%81%AF')
        dividendSoup = bs(dividendWeb.text, 'html.parser')
        divTable = dividendSoup.find('table')
        trs = divTable.find_all('tr')
        col = [th.get_text(strip=True) for th in trs[0].find_all('th')]

        table = []
        for tr in trs[2:]:
            table.append([td.get_text(strip=True) for td in tr.find_all('td')])
        
        df = pd.DataFrame(table, columns=col)[['發放年度','除息日','股票股利','現金股利']]
        df["發放日"] = df["發放年度"].astype(str) + "/" + df["除息日"]
        json_dividend = {
        "date": df["發放日"].tolist(),
        "stockSplits": df["股票股利"].tolist(),
        "capitalGains": df["現金股利"].tolist()
        }
    except Exception as e:
        Log(f"🔴 [Error] 獲取 Dividend 資訊發生錯誤: {str(e)}", color=Color.RED)
        json_dividend = {
            "date": [],
            "stockSplits": [],
            "capitalGains": []
        }
    
    return json_dividend