
import os
from langchain_ollama.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_openai import AzureChatOpenAI
from langchain.chat_models import init_chat_model

llm = ChatOllama(model="llama3.1:8b", temperature=0.1, max_tokens=2048)