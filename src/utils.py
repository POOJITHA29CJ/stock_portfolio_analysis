# noinspection PyTypedDict
from tavily import TavilyClient
def compute_portfolio_values(state):
    quantities=state["quantities"]
    current_price=state["current_price"]
    holdings={}
    total_holdings=0.0
    for ticker,qty in quantities.items():
        price=current_price[ticker]
        if price is None:
            continue
        value=price*qty
        holdings[ticker]=value
        total_holdings+=value
    state["portfolio_analysis"]={
        "holdings": holdings,
        "total_value": total_holdings
    }
    state["available_capital"]=total_holdings
    state["action_decision"]="direct_question"
    return state


def compute_profit_loss(state):
    quantities=state["quantities"]
    current_price=state["current_price"]
    purchased_price=state["purchased_price"]
    state["stock_analysis"] = {}
    holdings = {}
    state["reinvestment_capital"]={}
    value=0.0
    total_holdings = 0.0
    for ticker,qty in quantities.items():
        cost_price=current_price[ticker]
        purchase_price=purchased_price[ticker]
        if cost_price is None or purchase_price is None:
            continue
        profit_loss=(cost_price-purchase_price)*qty
        value = cost_price * qty
        holdings[ticker] = value
        total_holdings += value
        if profit_loss>0:
            decision="hold"
        else:
            decision="sell"
        if decision=="sell":
            state["reinvestment_capital"][ticker]=value
        state["stock_analysis"][ticker]={
            "profit_loss": profit_loss,
            "decision": decision
        }
    state["portfolio_analysis"] = {
        "holdings": holdings,
        "total_value": total_holdings
    }
    state["available_capital"] = total_holdings
    return state

def tool_web_search_top_stocks():
    """
        Uses Tavily Search API to identify top 3 performing stocks today.
    """
    tavily_client=TavilyClient("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")
    query="""
    List the top performing / top gaining 3 stocks yesterday.
    Include their tickers clearly in the text.
    """
    result = tavily_client.search(query, max_results=1,domains=["finance.yahoo.com"])
    content = result["results"][0]["content"]
    return content



