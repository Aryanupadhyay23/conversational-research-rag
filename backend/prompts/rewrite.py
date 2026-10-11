from langchain_core.prompts import ChatPromptTemplate

query_rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an academic query rewriter. The previous search failed to retrieve relevant documents.\n"
        "Rewrite the query by expanding technical keywords and scientific synonyms to improve retrieval recall."
    )),
    ("human", "Query to rewrite: {query}")
])
