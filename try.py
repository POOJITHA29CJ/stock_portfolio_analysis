import yfinance as yf

def get_fundamentals(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info

    return {
        "current_price": info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "book_value": info.get("bookValue"),
        "dividend_yield": info.get("dividendYield"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "profit_margins": info.get("profitMargins"),
        "operating_margins": info.get("operatingMargins"),
        "gross_margins": info.get("grossMargins"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "beta": info.get("beta"),
        "debt_to_equity": info.get("debtToEquity"),
    }

print(get_fundamentals("AAPL"))
