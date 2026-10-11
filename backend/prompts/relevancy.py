from langchain_core.prompts import ChatPromptTemplate

relevancy_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "Grade whether this retrieved document passage contains relevant facts or concepts to answer the question.\n"
        "Return binary_score 'yes' or 'no' with a brief reasoning."
    )),
    ("human", "Question: {query}\n\nDocument:\n{document}")
])
