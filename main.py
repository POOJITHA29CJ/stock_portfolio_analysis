import uuid
from src.agent import AgentState
from src.agent import app
def main():
    print("\n=== Stock portfolio and recommendation Analysis ===")
    print("Type 'exit' or 'quit' to stop.\n")
    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    while True:
        user_input = input("\nUser: ")
        if user_input.lower().strip() in ["exit", "quit", "bye"]:
            print("\nAssistant: Goodbye! ")
            break
        state: AgentState = {
            "question": user_input,
            "recommendation": "no"
        }
        print("\n--- Running Agent Graph ---\n")
        result = app.invoke(state, config=config)
        print("\nAssistant:", result.get("final_report", "No report generated."))

if __name__=="__main__":
    main()


# TESTCASE
# I own 3 AAPL stocks which is purchased in 29/08/2024 and 2 MSFT stock which is purchased in 28/10/2025 what is my current portfolio
# I have 1000 dollars and i want to invest in stocks
# What is the stock price of AAPL
#I own 3 AAPL shares purchased on 2023-07-20 and 2 MSFT shares purchased on 2024-03-15. What is my current portfolio?