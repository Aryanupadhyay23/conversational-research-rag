from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

query_rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an expert academic query reformulator for scientific document search (ChromaDB vector & BM25 lexical search).\n"
        "Your task is to rewrite the latest user query into a self-contained, highly specific search query:\n"
        "1. Contextual Disambiguation: If the user query contains pronouns or implicit references (e.g. 'it', 'they', 'the paper', 'this model', 'the second method', 'their findings'), "
        "resolve them using the provided conversation history into explicit names, paper titles, models, algorithms, or concepts.\n"
        "2. Domain Terminology: Expand acronyms and enrich with relevant scientific keywords and terminology to maximize retrieval recall.\n"
        "3. Standalone Independence: If the query is already specific and standalone, keep it intact or add relevant academic synonyms.\n"
        "4. DO NOT attempt to answer the question. Only output the reformulated search query."
    )),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "Latest User Query to Reformulate: {query}")
])
