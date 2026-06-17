"""
AI Chat Page — free-form Q&A about your portfolio using RAG + Claude.
"""

import streamlit as st
import json
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PORTFOLIO_PATH
from src.rag.router import route_and_retrieve
from src.analysis.llm_analyst import answer_chat_question


def load_portfolio():
    with open(PORTFOLIO_PATH) as f:
        return json.load(f)


def build_portfolio_summary(holdings) -> str:
    lines = ["Current Portfolio Holdings:"]
    for h in holdings:
        lines.append(f"- {h['name']} ({h['ticker']}): {h['qty']} shares @ ₹{h['avg_price']:.0f} avg")
    return "\n".join(lines)


EXAMPLE_QUESTIONS = [
    "Should I sell Infosys now or wait?",
    "Which of my IT stocks has the best outlook?",
    "How will a RBI rate cut affect my banking stocks?",
    "Which stock in my portfolio has the most upside?",
    "Is it a good time to buy more Reliance?",
    "What are the biggest risks in my portfolio right now?",
    "Should I diversify into any new sectors?",
    "Compare HDFC Bank and SBI — which is better to hold?",
]


def render():
    st.title("💬 AI Portfolio Chat")
    st.caption("Ask anything about your portfolio, Indian markets, or specific stocks.")

    portfolio = load_portfolio()
    holdings = portfolio["holdings"]
    portfolio_tickers = [h["ticker"] for h in holdings]
    portfolio_summary = build_portfolio_summary(holdings)

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Example questions
    st.subheader("💡 Example Questions")
    cols = st.columns(4)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i % 4].button(q, use_container_width=True, key=f"ex_{i}"):
            st.session_state.pending_question = q

    st.divider()

    # Chat history display
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("actionable"):
                st.info(f"💡 **Action:** {msg['actionable']}")
            if msg.get("confidence"):
                st.caption(f"Confidence: {msg['confidence']}")

    # Input
    question = st.chat_input("Ask about your portfolio...")

    # Handle example question clicks
    if "pending_question" in st.session_state:
        question = st.session_state.pending_question
        del st.session_state.pending_question

    if question:
        # Show user message
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.chat_history.append({"role": "user", "content": question})

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Searching news, fundamentals, and macro data..."):
                # Route and retrieve context
                rag_result = route_and_retrieve(question, portfolio_tickers)
                routing = rag_result["routing"]

                # Show routing info in expander
                with st.expander("🔍 Data sources used", expanded=False):
                    st.write(f"**Query type:** {routing['query_type']}")
                    st.write(f"**Intent:** {routing['intent']}")
                    if routing["tickers_mentioned"]:
                        st.write(f"**Stocks detected:** {', '.join(routing['tickers_mentioned'])}")
                    st.write(f"**Context chunks retrieved:** {len(rag_result['context'])}")

                # Get LLM answer
                response = answer_chat_question(
                    question,
                    rag_result["context_text"],
                    portfolio_summary,
                    routing,
                )

            st.markdown(response.answer)
            if response.actionable_advice:
                st.info(f"💡 **Actionable:** {response.actionable_advice}")
            st.caption(f"Confidence: {response.confidence} | Relevant stocks: {', '.join(response.relevant_tickers) if response.relevant_tickers else 'general market'}")

        # Save to history
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response.answer,
            "actionable": response.actionable_advice,
            "confidence": response.confidence,
        })

    # Clear chat button
    if st.session_state.chat_history:
        st.divider()
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()
