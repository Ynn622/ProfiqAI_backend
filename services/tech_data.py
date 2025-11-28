import numpy as np
import pandas as pd
import datetime
from stockstats import StockDataFrame as Sdf

from util.logger import Log, Color
from util.nowtime import TaiwanTime
from util.stock_list import StockList

def get_technical_indicators(data, sdf_indicator_list):
    """
    計算技術指標
    Args:
        data(DataFrame): 股價歷史資料
        sdf_indicator_list (list): 欲計算的技術指標清單
    """
    indicator_dict = {
        'close':'Close',
        'open':'Open',
        'high':'High',
        'low':'Low',
        'volume':'Volume',
        'close_5_sma':'SMA_5',
        'close_10_sma':'SMA_10',
        'close_20_sma':'SMA_20',
        'close_60_sma':'SMA_60',
        'close_5_ema':'EMA_5',
        'close_10_ema':'EMA_10',
        'close_20_ema':'EMA_20',
        'macd': 'MACD',
        'macds': 'Signal Line',
        'macdh': 'Histogram',
        'kdjk': '%K',
        'kdjd': '%D',
        'rsi_5': 'RSI_5',
        'rsi_10': 'RSI_10',
        'close_5_roc': 'ROC',
        'boll_ub': 'BOLL_UPPER',
        'boll': 'BOLL_MIDDLE',
        'boll_lb': 'BOLL_LOWER',
        'change': 'PCT'
    }

    # 計算技術指標
    stock_df = Sdf.retype(data)
    
    # 嘗試計算指標,忽略不支援的指標
    valid_indicators = []
    for indicator in sdf_indicator_list:
        try:
            # 訪問指標欄位會觸發 stockstats 自動計算
            _ = stock_df[indicator]
            valid_indicators.append(indicator)
        except (KeyError, Exception) as e:
            Log(f"⚠️  [Warning] 無法計算指標 '{indicator}': {str(e)}", color=Color.YELLOW)
            continue

    # 取出需要的指標資料
    indicator_data = stock_df[valid_indicators].copy()
    
    indicator_data.rename(columns=indicator_dict, inplace=True)  # 將指標名稱轉換
    indicator_data = indicator_data.round(2)
    
    # 避免重複：只保留 data 裡沒有的欄位
    new_cols = [col for col in indicator_data.columns if col not in data.columns]
    indicator_data = indicator_data[new_cols]
    
    return indicator_data


def calculate_technical_indicators(stock_id: str):
    from services.stock_data import getStockPrice
    
    stock_id, _ = StockList.query_from_yahoo(stock_id)
    df = getStockPrice(symbol=stock_id, 
                        start='2024-06-10', 
                        chip_enable=False,
                        sdf_indicator_list=['close_5_ema', 'close_10_ema','macd', 'macds', 'macdh','kdjk', 'kdjd', 'rsi_5','close_5_roc','close_6_sma'])
    # 收盤前 → 排除今天資料
    if TaiwanTime.now().time() < datetime.time(14, 00):  df = df[df.index < TaiwanTime.string(time=False)]
    df.rename(columns={'close_6_sma': 'SMA_6', 'RSI_5': 'RSI'}, inplace=True, errors='ignore')
    
    ma6 = df['SMA_6'] if 'SMA_6' in df.columns else df['Close'].rolling(6).mean()
    df['BIAS'] = ((df['Close'] - ma6) / ma6 * 100).round(2)    
    df = df.round(2)

    # 初始化各指標評分欄位
    df[['EMA_Score', 'MACD_Score', 'KD_Score', 'RSI_Score', 'ROC_Score', 'BIAS_Score']] = 0.0

    #EMA條件
    df['EMA_Score'] += np.where(df['EMA_5'] >= df['EMA_10'], 0.7, -0.7)
    df['EMA_Score'] += np.where(df['EMA_5'] >= df['EMA_5'].shift(1), 0.7, -0.7)
    df['EMA_Score'] += np.where((df['EMA_5'].shift(1) < df['EMA_10'].shift(1))&(df['EMA_5'] >= df['EMA_10']), 1, 0)
    df['EMA_Score'] += np.where((df['EMA_5'].shift(1) > df['EMA_10'].shift(1))&(df['EMA_5'] <= df['EMA_10']), -1, 0)

    #MACD條件
    df['MACD_Score'] += np.where(df['MACD'] >= df['Signal Line'], 0.7, -0.7)
    df['MACD_Score'] += np.where(df['MACD'] >= df['MACD'].shift(1), 0.5, -0.5)
    df['MACD_Score'] += np.where(df['Signal Line'] >= df['Signal Line'].shift(1), 0.5, -0.5)
    df['MACD_Score'] += np.where((df['MACD'].shift(1) < df['Signal Line'].shift(1))&(df['MACD'] >= df['Signal Line']), 1, 0)
    df['MACD_Score'] += np.where((df['MACD'].shift(1) > df['Signal Line'].shift(1))&(df['MACD'] <= df['Signal Line']), -1, 0)
    df['MACD_Score'] += np.where(df['Histogram'] >= df['Histogram'].shift(1), 0.3, -0.3)

    #KD條件
    df['KD_Score'] += np.where(df['%K'] >= df['%D'], 0.7, -0.7)
    df['KD_Score'] += np.where(df['%K'] >= df['%K'].shift(1), 0.5, -0.5)
    df['KD_Score'] += np.where(df['%D'] >= df['%D'].shift(1), 0.5, -0.5)
    df['KD_Score'] += np.where((df['%K'] > 80) & (df['%D'] > 80), -0.5, 0)
    df['KD_Score'] += np.where((df['%K'] < 20) & (df['%D'] < 20), 0.5, 0)
    df['KD_Score'] += np.where((df['%K'].shift(1) < df['%D'].shift(1)) & (df['%K'] >= df['%D']), 1, 0)
    df['KD_Score'] += np.where((df['%K'].shift(1) > df['%D'].shift(1)) & (df['%K'] <= df['%D']), -1, 0)

    #RSI條件
    df['RSI_Score'] += np.where(df['RSI'] > 70, -0.5, 0)
    df['RSI_Score'] += np.where(df['RSI'] < 30, 0.5, 0)
    df['RSI_Score'] += np.where(df['RSI'] > df['RSI'].shift(1), 0.5, -0.5)

    #ROC條件
    df['ROC_Score'] += np.where(df['ROC'] > df['ROC'].shift(1), 0.5, -0.5)
    df['ROC_Score'] += np.where((df['ROC'] > 0) & (df['ROC'].shift(1) < 0), 0.7, 0)
    df['ROC_Score'] += np.where((df['ROC'] < 0) & (df['ROC'].shift(1) > 0), -0.7, 0)

    #BIAS條件
    df['BIAS_Score'] += np.where(df['BIAS'] > df['BIAS'].shift(1), 0.5, -0.5)
    df['BIAS_Score'] += np.where((df['BIAS'] > 0) & (df['BIAS'].shift(1) < 0), 0.7, 0)
    df['BIAS_Score'] += np.where((df['BIAS'] < 0) & (df['BIAS'].shift(1) > 0), -0.7, 0)

    # 總分
    df['TotalScore'] = df[['EMA_Score','MACD_Score','KD_Score','RSI_Score','ROC_Score','BIAS_Score']].sum(axis=1)
    
    # 各指標評級標籤
    df['EMA_label'] = pd.cut(df['EMA_Score'],  bins=[-np.inf, -1.01, 0, 1, np.inf], labels=['極空', '偏空', '偏多', '極多'])
    df['MACD_label'] = pd.cut(df['MACD_Score'], bins=[-np.inf, -1.21, 0, 1.2, np.inf], labels=['極空', '偏空', '偏多', '極多'])
    df['KD_label'] = pd.cut(df['KD_Score'], bins=[-np.inf, -1.21, 0, 1.2, np.inf], labels=['極空', '偏空', '偏多', '極多'])
    df['RSI_label'] = pd.cut(df['RSI_Score'], bins=[-np.inf, -0.51, 0, 0.5, np.inf], labels=['極空', '偏空', '偏多', '極多'])
    df['ROC_label'] = pd.cut(df['ROC_Score'], bins=[-np.inf, -0.51, 0, 0.5, np.inf], labels=['極空', '偏空', '偏多', '極多'])
    df['BIAS_label'] = pd.cut(df['BIAS_Score'], bins=[-np.inf, -0.51, 0, 0.5, np.inf], labels=['極空', '偏空', '偏多', '極多'])
    
    # EMA 狀態描述
    ema_rules = {
        "黃金交叉": ( (df["EMA_5"].shift(1) < df["EMA_10"].shift(1)) & (df["EMA_5"] >= df["EMA_10"]) ),
        "死亡交叉": ( (df["EMA_5"].shift(1) > df["EMA_10"].shift(1)) & (df["EMA_5"] <= df["EMA_10"]) ),
        "多頭排列 & 快線向上": ( (df["EMA_5"] >= df["EMA_10"]) & (df["EMA_5"] >= df["EMA_5"].shift(1)) ),
        "空頭排列 & 快線向下": ( (df["EMA_5"] <= df["EMA_10"]) & (df["EMA_5"] <= df["EMA_5"].shift(1)) ),
        "多頭排列 & 快線向下": ( (df["EMA_5"] >= df["EMA_10"]) & (df["EMA_5"] < df["EMA_5"].shift(1)) ),
        "空頭排列 & 快線向上": ( (df["EMA_5"] <= df["EMA_10"]) & (df["EMA_5"] > df["EMA_5"].shift(1)) ),
    }
    # 套用 EMA 狀態欄位
    df["EMA_Status"] = np.select( list(ema_rules.values()), list(ema_rules.keys()), default="整理中" )


    # MACD 狀態描述字典
    macd_rules = {
        "黃金交叉": ( (df["MACD"].shift(1) < df["Signal Line"].shift(1)) & (df["MACD"] >= df["Signal Line"]) ),
        "死亡交叉": ( (df["MACD"].shift(1) > df["Signal Line"].shift(1)) & (df["MACD"] <= df["Signal Line"]) ),
        "快線>慢線 & 柱狀圖增強": ( (df["MACD"] >= df["Signal Line"]) & (df["Histogram"] >= df["Histogram"].shift(1)) ),
        "快線<慢線 & 柱狀圖增強": ( (df["MACD"] <= df["Signal Line"]) & (df["Histogram"] <= df["Histogram"].shift(1)) ),
        "快線>慢線 & 柱狀圖減弱": ( (df["MACD"] >= df["Signal Line"]) & (df["Histogram"] < df["Histogram"].shift(1)) ),
        "快線<慢線 & 柱狀圖減弱": ( (df["MACD"] <= df["Signal Line"]) & (df["Histogram"] > df["Histogram"].shift(1)) ),
    }
    # 套用 MACD 狀態欄位
    df["MACD_Status"] = np.select( list(macd_rules.values()), list(macd_rules.keys()), default="整理中" )


    # KD 狀態描述
    kd_rules = {
        "超買區死亡交叉": ( (df["%K"].shift(1) > df["%D"].shift(1)) & (df["%K"] <= df["%D"]) & (df["%K"] > 80) & (df["%D"] > 80) ),
        "超賣區黃金交叉": ( (df["%K"].shift(1) < df["%D"].shift(1)) & (df["%K"] >= df["%D"]) & (df["%K"] < 20) & (df["%D"] < 20) ),
        "黃金交叉": ( (df["%K"].shift(1) < df["%D"].shift(1)) & (df["%K"] >= df["%D"]) ),
        "死亡交叉": ( (df["%K"].shift(1) > df["%D"].shift(1)) & (df["%K"] <= df["%D"]) ),
        "超買區鈍化/盤整": ( (df["%K"] > 80) & (df["%D"] > 80) ),
        "超賣區鈍化/盤整": ( (df["%K"] < 20) & (df["%D"] < 20) ),
        "K>D & K向上": ( (df["%K"] >= df["%D"]) & (df["%K"] >= df["%K"].shift(1)) ),
        "K<D & K向下": ( (df["%K"] <= df["%D"]) & (df["%K"] <= df["%K"].shift(1)) ),
    }
    # 新增 KD 狀態欄位
    df["KD_Status"] = np.select( list(kd_rules.values()), list(kd_rules.keys()), default="整理中" )


    # RSI 狀態描述
    rsi_rules = {
        "超買區高點回落": ( (df["RSI"] > 70) & (df["RSI"] <= df["RSI"].shift(1)) ),
        "超買區持續走高": ( (df["RSI"] > 70) & (df["RSI"] > df["RSI"].shift(1)) ),
        "超賣區低點回升": ( (df["RSI"] < 30) & (df["RSI"] >= df["RSI"].shift(1)) ),
        "超賣區持續走低": ( (df["RSI"] < 30) & (df["RSI"] < df["RSI"].shift(1)) ),
        "中性區間走高":  ( df["RSI"] > df["RSI"].shift(1) ),
        "中性區間走低":  ( df["RSI"] < df["RSI"].shift(1) ),
    }
    # 套用 RSI 狀態欄位
    df["RSI_Status"] = np.select( list(rsi_rules.values()), list(rsi_rules.keys()), default="整理中" )


    # ROC 狀態描述
    roc_rules = {
        "由負轉正":        (df["ROC"] > 0) & (df["ROC"].shift(1) <= 0),
        "由正轉負":        (df["ROC"] < 0) & (df["ROC"].shift(1) >= 0),
        "正值區持續增強":   (df["ROC"] > 0) & (df["ROC"] > df["ROC"].shift(1)),
        "負值區持續減弱":   (df["ROC"] < 0) & (df["ROC"] < df["ROC"].shift(1)),
        "正值區減弱/修正":  (df["ROC"] > 0) & (df["ROC"] <= df["ROC"].shift(1)),
        "負值區增強/修正":  (df["ROC"] < 0) & (df["ROC"] >= df["ROC"].shift(1)),
    }
    # 套用 ROC 狀態欄位
    df["ROC_Status"] = np.select( list(roc_rules.values()), list(roc_rules.keys()), default="零軸附近整理" )


    # BIAS 狀態描述
    bias_rules = {
        "由負轉正":    (df["BIAS"] > 0) & (df["BIAS"].shift(1) <= 0),
        "由正轉負":    (df["BIAS"] < 0) & (df["BIAS"].shift(1) >= 0),
        "正乖離擴大":  (df["BIAS"] > 0) & (df["BIAS"] > df["BIAS"].shift(1)),
        "負乖離擴大":  (df["BIAS"] < 0) & (df["BIAS"] < df["BIAS"].shift(1)),
        "正乖離縮小":  (df["BIAS"] > 0) & (df["BIAS"] <= df["BIAS"].shift(1)),
        "負乖離縮小":  (df["BIAS"] < 0) & (df["BIAS"] >= df["BIAS"].shift(1)),
    }
    # 套用 BIAS 狀態欄位
    df["BIAS_Status"] = np.select( list(bias_rules.values()), list(bias_rules.keys()), default="零軸附近整理" )

    # 評級
    df['result'] = (df['Close']>df['Close'].shift(1)).astype(int)
    df['accurate'] = ( (df['TotalScore'] > 0).astype(int) == df['result'].shift(-1) ).astype(int)
    df['direction'] = pd.cut(df['TotalScore'], bins=[-np.inf, -3, 0, 3, np.inf], labels=[-2, -1, 1, 2], right=False).astype(int)
    df['direction_label'] = pd.cut(df['TotalScore'], bins=[-np.inf, -3, 0, 3, np.inf], labels=['極空', '偏空', '偏多', '極多'], right=False)

    df = df.iloc[::-1]

    latestdata = df.iloc[0]
    latestdata_dict = latestdata.to_dict()
    latestdata_dict['date'] = str(df.index[0])  # 加入日期
    tech_df = df[['Open', 'High', 'Low', 'Close', 'Volume', 'EMA_5', 'EMA_10', 'MACD', 'Signal Line', 'Histogram', '%K', '%D', 'RSI', 'ROC', 'SMA_6']]
    return latestdata_dict, tech_df