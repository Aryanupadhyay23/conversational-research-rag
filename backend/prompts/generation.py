from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

answer_generation_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an AI research assistant. Provide an accurate, comprehensive, and scholarly answer.\n"
        "- If context documents are present, ground your answer in them and cite sources.\n"
        "- If claim verification was performed, clearly state the verdict, evidence, and any superseding papers.\n"
        "- If conversational, respond warmly."
    )),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", (
        "Category: {route}\n"
        "Evidence Context:\n{context}\n\n"
        "Question: {question}"
    ))
])
