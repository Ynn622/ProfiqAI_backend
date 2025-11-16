import numpy as np
import pandas as pd

from services.function_util import getStockPrice, fetchStockInfo

def calculate_technical_indicators(stock_id: str):
    stock_id = fetchStockInfo(stock_id)[0]
    df = getStockPrice(symbol=stock_id, 
                        start='2024-06-10', 
                        chip_enable=False,
                        sdf_indicator_list=['close_5_ema', 'close_10_ema','macd', 'macds', 'macdh','kdjk', 'kdjd', 'rsi_5','close_5_roc','close_6_sma'])
    
    # 確保有 close_6_sma 欄位
    if 'SMA_6' not in df.columns and 'close_6_sma' in df.columns:
        df.rename(columns={'close_6_sma': 'SMA_6'}, inplace=True)
    
    ma6 = df['SMA_6'] if 'SMA_6' in df.columns else df['Close'].rolling(6).mean()
    ma6 = df['SMA_6'] if 'SMA_6' in df.columns else df['Close'].rolling(6).mean()
    df['BIAS'] = ((df['Close'] - ma6) / ma6 * 100).round(2)
    df['Score'] = 0.0

    # 取得指標欄位(如果存在)
    ema_5 = df.get('EMA_5', df['Close'])
    ema_10 = df.get('EMA_10', df['Close'])
    macd = df.get('MACD', 0)
    signal_line = df.get('Signal Line', 0)
    histogram = df.get('Histogram', 0)
    k = df.get('%K', 50)
    d = df.get('%D', 50)
    rsi = df.get('RSI_5', 50)
    roc = df.get('ROC', 0)
    
    df = df.round(2)

    df['EMA_Score'] = 0.0
    df['MACD_Score'] = 0.0
    df['KD_Score'] = 0.0
    df['RSI_Score'] = 0.0
    df['ROC_Score'] = 0.0
    df['BIAS_Score'] = 0.0

    #EMA條件
    df['EMA_Score'] += np.where(ema_5 >= ema_10, 0.7, -0.7)
    df['EMA_Score'] += np.where(ema_5 >= ema_5.shift(1), 0.7, -0.7)
    df['EMA_Score'] += np.where((ema_5.shift(1) < ema_10.shift(1))&(ema_5 >= ema_10), 1, 0)
    df['EMA_Score'] += np.where((ema_5.shift(1) > ema_10.shift(1))&(ema_5 <= ema_10), -1, 0)

    #MACD條件
    df['MACD_Score'] += np.where(macd >= signal_line, 0.7, -0.7)
    df['MACD_Score'] += np.where(macd >= macd.shift(1), 0.5, -0.5)
    df['MACD_Score'] += np.where(signal_line >= signal_line.shift(1), 0.5, -0.5)
    df['MACD_Score'] += np.where((macd.shift(1) < signal_line.shift(1))&(macd >= signal_line), 1, 0)
    df['MACD_Score'] += np.where((macd.shift(1) > signal_line.shift(1))&(macd <= signal_line), -1, 0)
    df['MACD_Score'] += np.where(histogram >= histogram.shift(1), 0.3, -0.3)

    #KD條件
    df['KD_Score'] += np.where(k >= d, 0.7, -0.7)
    df['KD_Score'] += np.where(k >= k.shift(1), 0.5, -0.5)
    df['KD_Score'] += np.where(d >= d.shift(1), 0.5, -0.5)
    df['KD_Score'] += np.where((k > 80) & (d > 80), -0.5, 0)
    df['KD_Score'] += np.where((k < 20) & (d < 20), 0.5, 0)
    df['KD_Score'] += np.where((k.shift(1) < d.shift(1)) & (k >= d), 1, 0)
    df['KD_Score'] += np.where((k.shift(1) > d.shift(1)) & (k <= d), -1, 0)

    #RSI條件
    df['RSI_Score'] += np.where(rsi > 70, -0.5, 0)
    df['RSI_Score'] += np.where(rsi < 30, 0.5, 0)
    df['RSI_Score'] += np.where(rsi > rsi.shift(1), 0.5, -0.5)

    #ROC條件
    df['ROC_Score'] += np.where(roc > roc.shift(1), 0.5, -0.5)
    df['ROC_Score'] += np.where((roc > 0) & (roc.shift(1) < 0), 0.7, 0)
    df['ROC_Score'] += np.where((roc < 0) & (roc.shift(1) > 0), -0.7, 0)

    #BIAS條件
    df['BIAS_Score'] += np.where(df['BIAS'] > df['BIAS'].shift(1), 0.5, -0.5)
    df['BIAS_Score'] += np.where((df['BIAS'] > 0) & (df['BIAS'].shift(1) < 0), 0.7, 0)
    df['BIAS_Score'] += np.where((df['BIAS'] < 0) & (df['BIAS'].shift(1) > 0), -0.7, 0)

    df['EMA_rate'] = np.select([df['EMA_Score'] > 1,df['EMA_Score'] > 0,df['EMA_Score'] >= -1],['很偏多', '偏多', '偏空'],default='很偏空')
    df['MACD_rate'] = np.select([df['MACD_Score'] > 1.2, df['MACD_Score'] > 0, df['MACD_Score'] >= -1.2],['很偏多','偏多','偏空'], default='很偏空')
    df['KD_rate'] = np.select([df['KD_Score'] > 1.2, df['KD_Score'] > 0, df['KD_Score'] >= -1.2],['很偏多','偏多','偏空'], default='很偏空')
    df['RSI_rate']  = np.select([df['RSI_Score'] > 0.5, df['RSI_Score']  > 0, df['RSI_Score']  >= -0.5],['很偏多','偏多','偏空'], default='很偏空')
    df['ROC_rate']  = np.select([df['ROC_Score'] > 0.5, df['ROC_Score']  > 0, df['ROC_Score']  >= -0.5],['很偏多','偏多','偏空'], default='很偏空')
    df['BIAS_rate'] = np.select([df['BIAS_Score'] > 0.5, df['BIAS_Score'] > 0, df['BIAS_Score'] >= -0.5],['很偏多','偏多','偏空'], default='很偏空')

    df['result'] = (df['Close']>df['Close'].shift(1)).astype(int)
    df['TotalScore'] = df[['EMA_Score','MACD_Score','KD_Score','RSI_Score','ROC_Score','BIAS_Score']].sum(axis=1)

    #評級
    df['accurate'] = (((df['Score'] > 0) & (df['result'].shift(-1) == 1)) |((df['Score'] <= 0) & (df['result'].shift(-1) == 0))).astype(int)
    df['direction'] = np.select([df['TotalScore'] > 3,df['TotalScore'] > 0,df['TotalScore'] >= -3],[2, 1, -1],default=-2)
    df['評級'] = np.select([df['TotalScore'] > 3,df['TotalScore'] > 0,df['TotalScore'] >= -3],['很偏多', '偏多', '偏空'],default='很偏空')

    df = df.iloc[::-1]

    latestdata = df.iloc[0]
    latestdata_dict = latestdata.to_dict()
    return latestdata_dict