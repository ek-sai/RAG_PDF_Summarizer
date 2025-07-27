import streamlit as st
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import io

load_dotenv()
os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY", "")


def get_pdf_text(pdf_docs):
    text = ''
    for uploaded_file in pdf_docs:
        file_bytes = uploaded_file.read()
        pdf_stream = io.BytesIO(file_bytes)
        pdf_reader = PdfReader(pdf_stream)
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    return text


def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(text)
    return chunks


def get_vector_store(text_chunks):
    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")
    return vector_store


def summarize_with_rag(text_chunks, summary_type="comprehensive"):
    # Create vector store from chunks
    st.info("🔍 Creating vector embeddings...")
    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    
    # Define different summary prompts with RAG context
    prompt_templates = {
        "comprehensive": """
            Based on the following relevant context from the document, provide a comprehensive summary. 
            Include all main points, key findings, important details, and conclusions found in the context.
            Make it detailed but well-organized:
            
            Context: {context}
            
            Comprehensive Summary:
        """,
        
        "brief": """
            Based on the following relevant context from the document, provide a brief summary. 
            Focus only on the most important points and key takeaways in 2-3 paragraphs:
            
            Context: {context}
            
            Brief Summary:
        """,
        
        "bullet_points": """
            Based on the following relevant context from the document, create a bullet point summary. 
            Extract the main ideas and present them as clear, concise bullet points:
            
            Context: {context}
            
            Key Points:
        """,
        
        "executive": """
            Based on the following relevant context from the document, provide an executive summary. 
            Focus on key insights, main conclusions, and actionable information relevant for decision-making:
            
            Context: {context}
            
            Executive Summary:
        """
    }
    
    model = ChatOpenAI(model="gpt-4o", temperature=0.3)
    prompt = PromptTemplate(template=prompt_templates[summary_type], input_variables=["context"])
    
    # Generate summary queries to retrieve relevant chunks
    summary_queries = [
        "main topics and key points",
        "important findings and conclusions", 
        "significant details and insights",
        "recommendations and actionable items"
    ]
    
    # Retrieve relevant chunks using similarity search
    st.info("🔍 Retrieving relevant content...")
    all_relevant_docs = []
    for query in summary_queries:
        docs = vector_store.similarity_search(query, k=3)  # Get top 3 most relevant chunks per query
        all_relevant_docs.extend(docs)
    
    # Remove duplicates while preserving order
    seen_content = set()
    unique_docs = []
    for doc in all_relevant_docs:
        if doc.page_content not in seen_content:
            seen_content.add(doc.page_content)
            unique_docs.append(doc)
    
    # Combine relevant context
    context = "\n\n".join([doc.page_content for doc in unique_docs[:10]])  # Limit to top 10 unique chunks
    
    # Generate summary using RAG
    st.info(f"🤖 Generating {summary_type} summary with RAG...")
    formatted_prompt = prompt.format(context=context)
    response = model.invoke(formatted_prompt)
    
    return response.content, len(unique_docs)


def main():
    st.set_page_config(page_title="PDF RAG Summarizer", page_icon="📄")
    st.header("PDF RAG Summarizer using GPT 📄")
    st.subheader("Upload PDFs and get intelligent summaries using Retrieval-Augmented Generation")

    with st.sidebar:
        st.title("📋 RAG Options")
        
        # File uploader
        pdf_docs = st.file_uploader(
            "Upload your PDF files", 
            type=["pdf"], 
            accept_multiple_files=True,
            help="You can upload multiple PDF files at once"
        )
        
        # Summary mode options
        summary_type = st.selectbox(
            "Choose summary type:",
            ["comprehensive", "brief", "bullet_points", "executive"],
            help="Select the type of summary you want"
        )
        
        # Summary button
        summarize_button = st.button(" Generate RAG Summary", type="primary")
            

    # Main content area for summary mode
    if pdf_docs and summarize_button:
        with st.spinner(" Processing PDFs with RAG pipeline..."):
            try:
                # Extract text from PDFs
                st.info(" Extracting text from PDFs...")
                raw_text = get_pdf_text(pdf_docs)
                
                if not raw_text.strip():
                    st.error(" No text could be extracted from the PDFs. Please check if the PDFs contain readable text.")
                    return
                
                # Show text statistics
                word_count = len(raw_text.split())
                st.info(f" Extracted {word_count:,} words from {len(pdf_docs)} PDF(s)")
                
                # Split text into chunks with custom parameters
                st.info(" Creating text chunks for RAG...")
                # Update chunk size based on sidebar settings
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size= 1000, 
                    chunk_overlap=200
                )
                text_chunks = text_splitter.split_text(raw_text)
                st.info(f" Created {len(text_chunks)} text chunks for RAG processing")
                
                # Generate RAG-based summary
                summary, relevant_chunks_count = summarize_with_rag(text_chunks, summary_type)
                
                # Display results
                st.success(" RAG Summary completed!")
                
                # Summary results with RAG info
                st.markdown(" RAG Summary Results")
                
                # RAG Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(" Total Chunks", len(text_chunks))
                with col2:
                    st.metric(" Relevant Chunks Used", relevant_chunks_count)
                with col3:
                    st.metric(" Retrieval Efficiency", f"{(relevant_chunks_count/len(text_chunks)*100):.1f}%")
                
                # Create expandable sections for better organization
                with st.expander(" Generated RAG Summary", expanded=True):
                    st.markdown(summary)
                
                # Download option
                summary_with_metadata = f"""RAG SUMMARY REPORT
Generated using Retrieval-Augmented Generation

Document(s): {len(pdf_docs)} PDF file(s)
Total Words: {word_count:,}
Total Chunks: {len(text_chunks)}
Relevant Chunks Used: {relevant_chunks_count}
Summary Type: {summary_type.title()}

=== SUMMARY ===
{summary}
"""
                
                st.download_button(
                    label=" Download RAG Summary Report",
                    data=summary_with_metadata,
                    file_name=f"rag_summary_{summary_type}.txt",
                    mime="text/plain"
                )
                
                # Optional: Show chunk analysis
                with st.expander(" RAG Chunk Analysis"):
                    st.write(f"**RAG Processing Details:**")
                    st.write(f"- Original document split into {len(text_chunks)} chunks of 1000 characters each")
                    st.write(f"- System intelligently retrieved {relevant_chunks_count} most relevant chunks")
                    st.write(f"- Summary generated using only the most pertinent content ({(relevant_chunks_count/len(text_chunks)*100):.1f}% of total)")
                    st.write("- This ensures focused, accurate summaries without information overload")
                
                # Optional: Show original text preview
                with st.expander(" Preview Original Text (First 1000 characters)"):
                    st.text(raw_text[:1000] + "..." if len(raw_text) > 1000 else raw_text)
                    
            except Exception as e:
                st.error(f" An error occurred: {str(e)}")
                st.error("Please check your OpenAI API key and try again.")
    
    elif not pdf_docs:
        st.info(" Please upload PDF files using the sidebar to get started")
    
    # Footer
    st.markdown("---")
    st.markdown("*Built with Streamlit, OpenAI GPT-4, FAISS Vector Store & RAG Pipeline*")


if __name__ == "__main__":
    main()