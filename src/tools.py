import yfinance as yf
from langchain_core.tools import tool
from typing import List,Dict,Optional
from datetime import datetime,timedelta
import math

@tool
def get_current_stock_prices(tickers:List[str])->Dict[str,Optional[float]]:
    """
        Fetches the current market price for a given stock ticker.
        Input should be a List of stock ticker (e.g., ['AAPL','MSFT']).
    """
    current_price={}
    for ticker in tickers:
        data=yf.Ticker(ticker).history(period="1d")
        price=float(data["Close"].iloc[0])
        if not data.empty:
            current_price[ticker]=price
        else:
            current_price[ticker]=None
    return current_price

@tool
def get_purchased_price(purchases:List[Dict[str,str]])->Dict[str,float]:
    """"
    Fetches the purchased price for a given stock ticker.
    Input example:
    [
        {"ticker": "AAPL", "purchase_date": "2001-08-20"},
        {"ticker": "MSFT", "purchase_date": "2010-05-10"}
    ]
    """
    purchased_price= {}
    for item in purchases:
        ticker = item["ticker"]
        purchased_date=item["purchase_date"]
        if not purchased_date:
            purchased_price[ticker] = None
            continue
        try:
            purchased_date=datetime.strptime(purchased_date, "%Y-%m-%d")
            end_date = purchased_date + timedelta(days=1)
            end_date_str = end_date.strftime("%Y-%m-%d")
            data=yf.Ticker(ticker).history(start=purchased_date, end=end_date_str,interval="1d")
            if not data.empty:
                purchased_price[ticker]=float(data["Close"].iloc[0])
            else:
                purchased_price[ticker]=None
        except Exception as e:
            print(f"Error fetching purchase price for {ticker}: {e}")
            purchased_price[ticker] = None
    return purchased_price

@tool
def calculate_quantities(prices:dict,capital:float):
    """
       prices: { "AAPL": 246.0, "MSFT": 345.0, ... }
       capital: total investment amount

       Returns:
          {
             "AAPL": {"quantity": X},
             "MSFT": {"quantity": Y}
          }
       """
    result={}
    for ticker,price in prices.items():
        if price<=0:
            qty=0
        else:
            qty=math.floor(capital/price)
        result[ticker]={"quantity":qty}
    return result



