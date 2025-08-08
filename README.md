RAG-based PDF Summarizer

This Streamlit application summarizes the contents of PDF documents using a Retrieval-Augmented Generation (RAG) approach. It integrates LangChain, FAISS for semantic retrieval, and OpenAI's GPT models to provide accurate and context-aware summaries.

Features
Retrieval-Augmented Generation using LangChain and FAISS

Semantic chunking and vector-based search

Real-time interaction and summarization via Streamlit UI

Supports multi-page PDFs and dynamic user queries

Get your OpenAI API Key
Sign up for an OpenAI account.

Navigate to the API section to create and copy your key.

Set your OpenAI API key:
export OPENAI_API_KEY=your_api_key_here

Run the app
streamlit run app.py
