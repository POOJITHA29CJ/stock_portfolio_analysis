from typing import Optional, List, Dict, Any, TypedDict, Literal
from langchain_core.messages import HumanMessage
from src.prompts import INPUT_AGENT_PROMPT,DATA_FETCHING_AGENT_PROMPT,PORTFOLIO_ANALYSIS_AGENT_PROMPT,OUTPUT_FORMATTING_AGENT_PROMPT,RECOMMENDATION_AGENT_PROMPT1,RECOMMENDATION_AGENT_PROMPT2
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.store.memory import InMemoryStore
from langmem import create_manage_memory_tool, create_search_memory_tool
import json
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph,END,START
from langgraph.types import Interrupt,Command
from src.tools import get_purchased_price,get_current_stock_prices,calculate_quantities,get_stock_fundamentals
from src.utils import compute_portfolio_values,compute_profit_loss,tool_web_search_top_stocks
import uuid

load_dotenv()

llm = ChatGoogleGenerativeAI(
    temperature=0,
    model="gemini-2.0-flash"
)

store = InMemoryStore(
    index={
        "dims": 384,
        "embed": "huggingface:sentence-transformers/all-MiniLM-L6-v2"
    }
)


manage_memory = create_manage_memory_tool(namespace=("memories",), store=store)
search_memory = create_search_memory_tool(namespace=("memories",), store=store)

class AgentState(TypedDict,total=False):
    question: str
    quantities:Optional[Dict[str, float]]
    category: Optional[str]
    recommendation:Optional[str]
    reinvestment_capital:Optional[Dict[str,float]]
    current_price: Optional[Dict[str, float]]
    purchased_price: Optional[Dict[str, float]]
    available_capital: Optional[float]
    action_decision: Optional[str]
    stock_analysis: Optional[Dict[str, Dict[str, Any]]]
    portfolio_analysis: Optional[Dict[str, Dict[str, Any]]]
    top_stocks_price: Optional[Dict[str, float]]
    need_recommendation_confirmation: Optional[str]
    quantities_can_be_bought: Optional[Dict[str, float]]
    final_report: Optional[str]
    fundamentals: Optional[Dict[str, dict]]


def input_agent(state: AgentState):
    question = state["question"]
    mem_response = search_memory.invoke({
        "query": "portfolio",
        "limit": 1
    })
    parsed = json.loads(mem_response)
    contents = [item["value"]["content"] for item in parsed]
    #print("contents : ",contents)
    memory_text = contents
    classification_prompt = f"""
        {INPUT_AGENT_PROMPT}
        ## MEMORY CONTEXT
        {memory_text}
        ## USER QUERY
        {question}
    """
    response = llm.invoke([HumanMessage(content=classification_prompt)])
    state["category"] = response.content.strip()
    print("category:", state["category"])
    return state

def data_fetching_agent(state:AgentState):
    question=state["question"]
    prompt=f"""
    {DATA_FETCHING_AGENT_PROMPT}
    ## USER QUESTION : {question}
     """
    tools=[
        get_current_stock_prices,
        get_purchased_price
    ]
    llm_with_tools=llm.bind_tools(tools)
    response=llm_with_tools.invoke([HumanMessage(content=prompt)])
    print("llm tool calls:",response.tool_calls)
    if response.tool_calls:
        print(f"[DATA_FETCHING_AGENT] --> Agent decided to excecute {len(response.tool_calls)} tools")
        for tool_call in response.tool_calls:
            tool_name=tool_call["name"]
            tool_args=tool_call["args"]
            print(f"\n [DATA_FETCHING_AGENT] --> Executing Tool -{tool_name} with args: {tool_args}")
            if tool_name=="get_current_stock_prices":
                tickers_list = tool_args.get("tickers", [])
                if tickers_list:
                    current_prices_result = get_current_stock_prices.func(tickers_list)
                    state["current_price"] = current_prices_result
            elif tool_name=="get_purchased_price":
                purchases_list = tool_args.get("purchases", [])
                if purchases_list:
                    purchased_prices_result = get_purchased_price.func(purchases_list)
                    state["purchased_price"] = purchased_prices_result
    #print("current_price",state["current_price"])
    #print("purchased_price",state["purchased_price"])
    return state

def portfolio_analysis_agent(state:AgentState):
    question=state["question"]
    prompt=f"""
    {PORTFOLIO_ANALYSIS_AGENT_PROMPT}
    ##Question:{question}
    """
    response=llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    content = content.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(content)
    #print("##Parsed",parsed)
    scenario=parsed.get("scenario")
    quantities=parsed.get("quantities",{})
    asks_recommendation=parsed.get("asks_recommendation",{})
    state["quantities"] = quantities
    if scenario=="direct_question":
        print(f"[PORTFOLIO_FETCHING_AGENT] --> direct_question")
        state["action_decision"]="direct_question"
        return state
    if scenario=="quantity_available":
        print(f"[PORTFOLIO_FETCHING_AGENT] --> quantity alone available")
        return compute_portfolio_values(state)
    if scenario=="both_available":
        print(f"[PORTFOLIO_FETCHING_AGENT] --> Both quantity and purchased date available")
        if not state["current_price"] or not state["purchased_price"]:
            print("Missing price data — skipping compute_profit_loss")
            return state
        else:
            updated_state=compute_profit_loss(state)
            state.update(updated_state)
            reinvestment_capital=state["reinvestment_capital"]
            #print("updated_state",state)
            input_to_memory = (
                f"reinvestment capital:{reinvestment_capital}"
            )
            manage_memory.invoke({
                "content": input_to_memory,
                "action": "create"
            })
            #print(store.search(("memories",)))
            if state.get("reinvestment_capital"):
                if asks_recommendation=="yes":
                    state["action_decision"]="recommendation"
                    return state
                else:
                    user_input=input("Do you need recommendation yes/no : ")
                    state["need_recommendation_confirmation"]=user_input
                    if state["need_recommendation_confirmation"]=="yes":
                        state["action_decision"]="recommendation"
                    else:
                        state["action_decision"] = "direct_question"
                    return state
            else:
                state["action_decision"] = "direct_question"
                state["reinvestment_capital"]=None
                return state


def recommendation_agent(state: AgentState):
    state["recommendation"]="yes"
    stock_state = state.get("stock_analysis", {})
    if stock_state:
        for ticker, analysis in stock_state.items():
            decision = analysis.get("decision")
            pl = analysis.get("profit_loss")
            if decision == "hold":
                print(f"{ticker}: Performing well (+${pl:.2f}). Recommendation: HOLD.")
            elif decision == "sell":
                print(f"{ticker}: Underperforming (-${pl:.2f}). Recommendation: SELL.")
            else:
                print(f"{ticker}: Decision = {decision}, Profit/Loss = {pl}")
    web_search_result = tool_web_search_top_stocks()
    mem_response = search_memory.invoke({
        "query": "reinvestment_capital",
        "limit": 1
    })
    #print("MEMORY SEARCH RESULT:", mem_response)
    parsed = json.loads(mem_response)
    contents = [item["value"]["content"] for item in parsed]
    #print("contents : ", contents)
    memory_text = contents
    prompt_step1 = f"""
    {RECOMMENDATION_AGENT_PROMPT1}
    ## Web search result:{web_search_result}
    ## memory : {memory_text}
    ## question ; {state["question"]}
    Note: You must generate the tool calls sequentially to complete the analysis. Start with get_current_stock_prices.
    """
    tools_step1 = [get_current_stock_prices]
    llm_with_tools_step1 = llm.bind_tools(tools_step1)
    response_step1 = llm_with_tools_step1.invoke([HumanMessage(content=prompt_step1)])
    #print("recommendation response (Step 1):", response_step1.content)

    if response_step1.tool_calls:
        print(f"[RECOMMENDATION AGENT]-->Agent decided to excecute {len(response_step1.tool_calls)} tools in Step 1")
        for tool in response_step1.tool_calls:
            tool_name = tool["name"]
            tool_args = tool["args"]
            print("[RECOMMENDATION AGENT]-->Agent decided to excecute tool", tool_name)
            if tool_name == "get_current_stock_prices":
                tickers_list = tool_args.get("tickers", [])
                prices = get_current_stock_prices.func(tickers_list)
                state["top_stocks_price"] = prices
                print("Fetched Prices:", prices)
    prompt_step2 = f"""
        {RECOMMENDATION_AGENT_PROMPT2}
        ## top_3_stock prices:{state.get("top_stocks_price")}
        ## memory : {memory_text}
        ## question ; {state["question"]}
        Note: You must generate the tool calls sequentially to complete the analysis.
        """
    tools_step2 = [calculate_quantities]
    llm_with_tools_step2 = llm.bind_tools(tools_step2)

    response_step2 = llm_with_tools_step2.invoke([HumanMessage(content=prompt_step2)])
    #print("recommendation response (Step 2):", response_step2.content)

    if response_step2.tool_calls:
        print(f"[RECOMMENDATION AGENT]-->Agent decided to excecute {len(response_step2.tool_calls)} tools in Step 2")
        for tool in response_step2.tool_calls:
            tool_name = tool["name"]
            tool_args = tool["args"]
            print("[RECOMMENDATION AGENT]-->Agent decided to excecute tool", tool_name)
            if tool_name == "calculate_quantities":
                quantities = calculate_quantities.func(
                    prices=tool_args.get("prices", {}),
                    capital=tool_args.get("capital", 0.0)
                )
                state["quantities_can_be_bought"] = quantities
                #print("Calculated Quantities:", quantities)
    #print(state)
    return state
def output_formatting_agent(state:AgentState):
    fundamentals = {}
    if state.get("recommendation") == "no":
        tickers = list(state.get("quantities", {}).keys())
    else:
        tickers = list(state.get("quantities_can_be_bought", {}).keys())
    for ticker in tickers:
        try:
            fundamentals[ticker] = get_stock_fundamentals.func(ticker)
        except Exception as e:
            fundamentals[ticker] = {"error": str(e)}
    state["fundamentals"] = fundamentals
    recommendation_path=state["recommendation"]
    mem_response = search_memory.invoke({
        "query": "reinvestment_capital",
        "limit": 1
    })
    #print("MEMORY SEARCH RESULT:", mem_response)
    parsed = json.loads(mem_response)
    contents = [item["value"]["content"] for item in parsed]
    #print("contents : ", contents)
    memory_text = contents
    print("state",state)
    prompt = f"""
        {OUTPUT_FORMATTING_AGENT_PROMPT}
        ## Stock Analysis:
        {state.get("stock_analysis")}
        ## Fundamentals:
        {state.get("fundamentals")}
        ## Portfolio Analysis:
        {state.get("portfolio_analysis")}
        ## Quantities:
        {state.get("quantities")}
        ## Quantities Can Be Bought:
        {state.get("quantities_can_be_bought")}
        ## Recommendation state:
        {recommendation_path}
        ## Memory Context:
        {memory_text}
        ## Final state: {state}
        """
    #print("in output agent")
    response=llm.invoke([HumanMessage(content=prompt)])
    state["final_report"]=response.content
    if recommendation_path == "yes" and state.get("reinvestment_capital"):
        mem_response = search_memory.invoke({"query": "reinvestment_capital", "limit": 1})
        parsed = json.loads(mem_response)
        key_to_delete = None
        if parsed and isinstance(parsed, list) and len(parsed) > 0 and 'key' in parsed[0]:
            key_to_delete = parsed[0]['key']
        if key_to_delete:
            manage_memory.invoke({
                "id": key_to_delete,
                "action": "delete"
            })
            print(f"Memory Cleanup: Deleted old reinvestment capital entry with key {key_to_delete}")
            state["reinvestment_capital"] = None
        else:
            print("Memory Cleanup: Could not find a 'reinvestment_capital' entry to delete.")

    return state

def decision(state:AgentState):
    if state['action_decision']=="direct_question":
        return "output_formatting_agent"
    if state['action_decision']=="recommendation":
        return "recommendation_agent"
    return "output_formatting_agent"


def router(state:AgentState):
    if state["category"]=="portfolio":
        return "data_fetching_agent"
    else:
        return "recommendation_agent"

graph=StateGraph(AgentState)
graph.add_edge(START,"input_agent")
graph.add_node("input_agent",input_agent)
graph.add_node("data_fetching_agent",data_fetching_agent)
graph.add_node("portfolio_analysis_agent",portfolio_analysis_agent)
graph.add_node("output_formatting_agent",output_formatting_agent)
#graph.add_node("confirmation_handler", confirmation_handler)
graph.add_node("recommendation_agent",recommendation_agent)

graph.add_conditional_edges(
    "input_agent",
    router,
    {
        "data_fetching_agent":"data_fetching_agent",
         "recommendation_agent":"recommendation_agent"
    }
)
graph.add_conditional_edges(
    "portfolio_analysis_agent",
    decision,
    {
        "output_formatting_agent":"output_formatting_agent",
        "recommendation_agent":"recommendation_agent",
    }
)

graph.add_edge("data_fetching_agent","portfolio_analysis_agent")
graph.add_edge("recommendation_agent","output_formatting_agent")
graph.add_edge("output_formatting_agent",END)
checkpointer=MemorySaver()
app=graph.compile()


# png_bytes = app.get_graph().draw_mermaid_png()
#
# with open("graph.png", "wb") as f:
#     f.write(png_bytes)
#
# print("Graph saved as graph.png — open it in PyCharm to view.")

