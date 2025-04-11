import os
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
# TEMP FIX for undefined BaseCache reference
class BaseCache:
    pass
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

def get_pdf_text(pdf_paths):
    text = ""
    for pdf_path in pdf_paths:
        try:
            pdf_reader = PdfReader(pdf_path)
            for page in pdf_reader.pages:
                text += page.extract_text()
        except Exception as e:
            raise Exception(f"Error reading PDF {pdf_path}: {str(e)}")
    return text

def get_text_chunks(text):
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        chunks = text_splitter.split_text(text)
        return chunks
    except Exception as e:
        raise Exception(f"Error splitting text: {str(e)}")

def get_vector_store(text_chunks):
    try:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vector_store = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
        
        # Save in the same directory as the script
        save_dir = os.path.dirname(os.path.abspath(__file__))
        vector_store.save_local(os.path.join(save_dir, "faiss_index"))
    except Exception as e:
        raise Exception(f"Error creating vector store: {str(e)}")

def process_question(user_question):
    try:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        vector_store = FAISS.load_local(
            os.path.join(current_dir, "faiss_index"),
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        docs = vector_store.similarity_search(user_question)
        
        prompt_template = """
        Answer the question as detailed as possible from the provided context. If the answer is not in
        the provided context, just say "Answer is not available in the context". Don't provide incorrect information.
        
        Context: {context}
        Question: {question}
        
        Answer:
        """
        
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise Exception("GROQ_API_KEY not found in environment variables")
        
        ChatGroq.model_rebuild()
        model = ChatGroq(
            api_key=groq_api_key,
            model_name="llama3-70b-8192",
            temperature=0.3
        )
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
        
        response = chain(
            {"input_documents": docs, "question": user_question},
            return_only_outputs=True
        )
        
        return response["output_text"]
    except Exception as e:
        raise Exception(f"Error processing question: {str(e)}")