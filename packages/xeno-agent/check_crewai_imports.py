try:
    from crewai import LLM

    print("crewai.LLM found")
except ImportError:
    print("crewai.LLM NOT found")

try:
    from langchain_openai import ChatOpenAI

    print("langchain_openai.ChatOpenAI found")
except ImportError:
    print("langchain_openai.ChatOpenAI NOT found")
