from langchain_core.prompts import ChatPromptTemplate

router_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an intent classification router for an AI research assistant.\n"
        "Classify the user input into exactly one category:\n"
        "- 'retrieve': Looking up research papers, documents, or academic concepts.\n"
        "- 'verify_claim': Verifying, fact-checking, or assessing a claim or hypothesis.\n"
        "- 'direct_answer': Chit-chat, conversational greetings, or direct logic questions.\n"
        "Respond with your decision and reasoning."
    )),
    ("human", "{question}")
])
