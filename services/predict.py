import torch
import torch.nn as nn
import numpy as np
import pandas as pd
import yfinance as yf
import datetime
from huggingface_hub import hf_hub_download

from util.nowtime import TaiwanTime
from util.logger import Log, Color
from util.stock_list import StockList

# ===== 模型與設定 =====
SEQ_LEN = 25
HIDDEN_SIZE = 96
DROPOUT = 0.3
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ===== 模型架構 =====
class Attention(nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.attn = nn.Linear(hidden_dim * 2, 1)
    def forward(self, lstm_output):
        attn_weights = torch.softmax(self.attn(lstm_output), dim=1)
        context = torch.sum(attn_weights * lstm_output, dim=1)
        return context

class LSTMClassifier(nn.Module):
    def __init__(self, input_dim, hidden_dim=HIDDEN_SIZE, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, num_layers=num_layers,
            batch_first=True, dropout=DROPOUT, bidirectional=True
        )
        self.attention = Attention(hidden_dim)
        self.fc = nn.Linear(hidden_dim * 2, 1)
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        context = self.attention(lstm_out)
        logit = self.fc(context).squeeze(1)
        return logit


def predict_future(symbol: str):
    """
    預測指定股票未來1天上漲機率。
    Args:
        symbol (str): 股票代號
    Returns:
        float: 未來1天上漲機率（0~1）
    """
    df = get_predict_stock_data_talib(symbol)
    # 從你的 model repo 下載模型
    model_path = hf_hub_download(
        repo_id="Ynn22/ProfiqAI_Model",
        filename="lstm_stock_model.pth"
    )

    # 檢查資料夠不夠長
    if len(df) < SEQ_LEN:
        raise ValueError(f"資料太短，至少需要 {SEQ_LEN} 筆，目前只有 {len(df)} 筆。")

    # 取最近25天資料
    recent_df = df.tail(SEQ_LEN)
    features = recent_df.drop(columns=["Close"]).values  # shape: (25, feature_dim)
    X_input = np.expand_dims(features, axis=0)           # shape: (1, 25, feature_dim)
    X_tensor = torch.tensor(X_input, dtype=torch.float32).to(DEVICE)

    # 載入模型
    model = LSTMClassifier(input_dim=features.shape[1]).to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.eval()

    # 推論
    with torch.no_grad():
        logit = model(X_tensor)
        prob_up = torch.sigmoid(logit).item()

    Log(f"[Predict] {symbol} 未來1天上漲機率：{prob_up:.2%}  下跌機率：{1 - prob_up:.2%}", color=Color.ORANGE, reload_only=True)
    return round(prob_up, 2)

def get_predict_stock_data(symbol: str) -> pd.DataFrame:
    """
    使用 stockstats 取得預測用的股票資料。（60分k、近5日）
    Args:
        symbol (str): 股票代號
    """
    from stockstats import StockDataFrame as Sdf
    
    stockID, _ = StockList.query_from_yahoo(symbol)
    data = yf.Ticker(stockID).history(period="100d", interval="60m")
    data = data.round(2)
    data.index = pd.to_datetime(data.index).map(lambda x: x.date()).astype(str)
    data = data[data.index != TaiwanTime.string(time=False)]   # 移除今天未收盤資料
    data = data.drop(['Dividends', 'Stock Splits'], axis=1)

    sdf = Sdf.retype(data)
    data['MACD'] = sdf['macd']
    data['MACDsignal'] = sdf['macds']
    data['MACDhist'] = sdf['macdh']
    data['slowk'] = sdf['kdjk']
    data['slowd'] = sdf['kdjd']
    data['RSI5'] = sdf['rsi_5']
    data['RSI10'] = sdf['rsi_10']
    data.drop(['Open', 'High', 'Low', 'Volume'], axis=1, inplace=True)
    data.dropna(inplace=True)

    return data[-25:]

def get_predict_stock_data_talib(symbol: str) -> pd.DataFrame:
    """
    使用 TA-Lib 取得預測用的股票資料。（60分k、近5日）
    Args:
        symbol (str): 股票代號
    """
    import talib
    
    stockID, _ = StockList.query_from_yahoo(symbol)
    data = yf.Ticker(stockID).history(period="100d", interval="60m")
    data = data.round(2)
    data.index = pd.to_datetime(data.index).map(lambda x: x.date()).astype(str)
    data = data.drop(['Dividends', 'Stock Splits'], axis=1)
    # 收盤前 → 排除今天所有小時K
    if TaiwanTime.now().time() < datetime.time(14, 00):  data = data[data.index < TaiwanTime.string(time=False)]

    macd, macdsignal, macdhist = talib.MACD(data['Close'], fastperiod=12, slowperiod=26, signalperiod=9)
    data['MACD'] = macd
    data['MACDsignal'] = macdsignal
    data['MACDhist'] = macdhist

    slowk, slowd = talib.STOCH(data['High'], data['Low'], data['Close'], fastk_period=9, slowk_period=3, slowk_matype=5, slowd_period=3, slowd_matype=5)
    data['slowk'] = slowk
    data['slowd'] = slowd

    data['RSI5'] = talib.RSI(data['Close'], timeperiod=5)
    data['RSI10'] = talib.RSI(data['Close'], timeperiod=10)

    data = data.drop(['Open', 'High', 'Low', 'Volume'], axis=1).dropna()
    return data[-25:]