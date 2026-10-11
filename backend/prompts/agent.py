from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

agent_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an academic research assistant with access to two tools:\n"
        "- 'retrieve_from_vectorstore(query)': Search uploaded papers in vector store.\n"
        "- 'web_search(query)': Search web and scientific repositories via Tavily/ArXiv.\n\n"
        "Call the appropriate tools if literature is needed. If context is sufficient, provide your answer."
    )),
    MessagesPlaceholder(variable_name="history", optional=True),
    ("human", "Research Query: {query}")
])
