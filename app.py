import streamlit as st
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.vectorstores import FAISS
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


def summarize_with_rag(text_chunks, summary_type="comprehensive", specific_topic=None):
    # Create vector store from chunks
    st.info(" Creating vector embeddings...")
    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    
    # Define different summary prompts with RAG context
    if specific_topic:
        # Topic-specific prompts
        prompt_templates = {
            "comprehensive": f"""
                Based on the following relevant context from the document, provide a comprehensive summary specifically about: "{specific_topic}".
                Focus on all information related to this topic, including main points, key findings, important details, and conclusions.
                If the topic is not covered in the context, clearly state that the topic was not found in the document.
                
                Context: {{context}}
                
                Comprehensive Summary about "{specific_topic}":
            """,
            
            "brief": f"""
                Based on the following relevant context from the document, provide a brief summary specifically about: "{specific_topic}".
                Focus only on the most important points related to this topic in 2-3 paragraphs.
                If the topic is not covered in the context, clearly state that the topic was not found.
                
                Context: {{context}}
                
                Brief Summary about "{specific_topic}":
            """,
            
            "bullet_points": f"""
                Based on the following relevant context from the document, create a bullet point summary specifically about: "{specific_topic}".
                Extract only the main ideas related to this topic and present them as clear, concise bullet points.
                If the topic is not covered in the context, clearly state that the topic was not found.
                
                Context: {{context}}
                
                Key Points about "{specific_topic}":
            """,
            
            "executive": f"""
                Based on the following relevant context from the document, provide an executive summary specifically about: "{specific_topic}".
                Focus on key insights, conclusions, and actionable information related to this topic that would be relevant for decision-making.
                If the topic is not covered in the context, clearly state that the topic was not found.
                
                Context: {{context}}
                
                Executive Summary about "{specific_topic}":
            """
        }
        
        # Use the specific topic as the main search query
        summary_queries = [
            specific_topic,
            f"{specific_topic} details",
            f"{specific_topic} findings",
            f"{specific_topic} information"
        ]
    else:
        # General summary prompts (original)
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
        
        # General summary queries
        summary_queries = [
            "main topics and key points",
            "important findings and conclusions", 
            "significant details and insights",
            "recommendations and actionable items"
        ]
    
    model = ChatOpenAI(model="gpt-4o", temperature=0.3)
    prompt = PromptTemplate(template=prompt_templates[summary_type], input_variables=["context"])
    
    # Retrieve relevant chunks using similarity search
    if specific_topic:
        st.info(f" Searching for content related to: '{specific_topic}'...")
    else:
        st.info("🔍 Retrieving relevant content...")
    
    all_relevant_docs = []
    for query in summary_queries:
        docs = vector_store.similarity_search(query, k=4)
        all_relevant_docs.extend(docs)
    
    # Remove duplicates while preserving order
    seen_content = set()
    unique_docs = []
    for doc in all_relevant_docs:
        if doc.page_content not in seen_content:
            seen_content.add(doc.page_content)
            unique_docs.append(doc)
    
    # Combine relevant context
    context = "\n\n".join([doc.page_content for doc in unique_docs[:12]])  # Limit to top 12 unique chunks
    
    # Generate summary using RAG
    if specific_topic:
        st.info(f" Generating {summary_type} summary about '{specific_topic}' with RAG...")
    else:
        st.info(f" Generating {summary_type} summary with RAG...")
    
    formatted_prompt = prompt.format(context=context)
    response = model.invoke(formatted_prompt)
    
    return response.content, len(unique_docs)


def main():
    st.set_page_config(page_title="PDF RAG Summarizer", page_icon="")
    st.header("PDF RAG Summarizer using GPT")
    st.subheader("Upload PDFs and get intelligent summaries using Retrieval-Augmented Generation")

    with st.sidebar:
        st.title(" RAG Options")
        
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
        
        # RAG parameters
        st.markdown("nRAG Parameters")
        chunk_size = st.slider("Chunk Size", 500, 2000, 1000, 100, 
                              help="Size of text chunks for embedding")
        chunk_overlap = st.slider("Chunk Overlap", 50, 400, 200, 50,
                                 help="Overlap between chunks")
        
        # Summary button
        summarize_button = st.button(" Generate RAG Summary", type="primary")
            
        # Instructions
       

    # Topic-specific summary input in main area
    st.markdown(" Topic-Specific Summary (Optional)")
    specific_topic = st.text_area(
        "Enter a specific topic, question, or theme you'd like to focus on:",
        help="The RAG system will search for content specifically related to your topic and generate a focused summary",
        height=120,
        key="topic_input"
    )
    
    # Show topic indicator
    if specific_topic.strip():
        st.success(f" Focus Topic:** {specific_topic.strip()}")
        st.info(" The system will search for content specifically related to this topic")
    else:
        st.info(" General Summary Mode: Will summarize the entire document")
    

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
                    chunk_size=chunk_size, 
                    chunk_overlap=chunk_overlap
                )
                text_chunks = text_splitter.split_text(raw_text)
                st.info(f" Created {len(text_chunks)} text chunks for RAG processing")
                
                # Generate RAG-based summary
                topic_to_use = specific_topic.strip() if specific_topic.strip() else None
                summary, relevant_chunks_count = summarize_with_rag(text_chunks, summary_type, topic_to_use)
                
                # Display results
                st.success(" RAG Summary completed!")
                
                # Summary results with RAG info
                if topic_to_use:
                    st.markdown(f"RAG Topic Summary: '{topic_to_use}'")
                else:
                    st.markdown(" RAG General Summary Results")
                
                # RAG Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(" Total Chunks", len(text_chunks))
                with col2:
                    st.metric(" Relevant Chunks Used", relevant_chunks_count)
                with col3:
                    st.metric(" Retrieval Efficiency", f"{(relevant_chunks_count/len(text_chunks)*100):.1f}%")
                
                # Create expandable sections for better organization
                if topic_to_use:
                    with st.expander(f" Generated Topic Summary: '{topic_to_use}'", expanded=True):
                        st.markdown(summary)
                else:
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
Specific Topic: {topic_to_use if topic_to_use else 'General Summary'}
Chunk Size: {chunk_size}
Chunk Overlap: {chunk_overlap}

=== SUMMARY ===
{summary}
"""
                
                filename_suffix = f"_{topic_to_use.replace(' ', '_')}" if topic_to_use else ""
                st.download_button(
                    label=" Download RAG Summary Report",
                    data=summary_with_metadata,
                    file_name=f"rag_summary_{summary_type}{filename_suffix}.txt",
                    mime="text/plain"
                )
                
                # Optional: Show chunk analysis
                with st.expander(" RAG Chunk Analysis"):
                    st.write(f" RAG Processing Details:**")
                    if topic_to_use:
                        st.write(f" Topic Focus**: '{topic_to_use}'")
                        st.write(f" Searched specifically for content related to this topic")
                    st.write(f" Original document split into {len(text_chunks)} chunks of {chunk_size} characters each")
                    st.write(f" System intelligently retrieved {relevant_chunks_count} most relevant chunks")
                    st.write(f" Summary generated using only the most pertinent content ({(relevant_chunks_count/len(text_chunks)*100):.1f}% of total)")
                    if topic_to_use:
                        st.write(f" Focused retrieval** ensures summary is specifically about '{topic_to_use}'")
                    else:
                        st.write(" This ensures focused, accurate summaries without information overload")
                
                    
            except Exception as e:
                st.error(f" An error occurred: {str(e)}")
                st.error("Please check your OpenAI API key and try again.")
    
    elif not pdf_docs:
        st.info(" Please upload PDF files using the sidebar to get started")
    
    # Footer
    st.markdown("---")
    st.markdown(" Built with Streamlit, OpenAI GPT-4, FAISS Vector Store & RAG Pipeline*")


if __name__ == "__main__":
    main()
