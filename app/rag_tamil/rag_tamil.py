import os
import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

class RagTamil:
    def __init__(self):
        # Create base directory for storing indexes
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.index_dir = os.path.join(self.base_dir, 'faiss_indexes')
        self.index_path = os.path.join(self.index_dir, 'faiss_index')
        
        # Create directory if it doesn't exist
        os.makedirs(self.index_dir, exist_ok=True)
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            model_kwargs={'device': 'cpu'}
        )
        self.vector_store = None

    def get_pdf_text(self, pdf_paths):
        text = ""
        for pdf_path in pdf_paths:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        extracted_text = page.extract_text(x_tolerance=2, y_tolerance=2)
                        if extracted_text:
                            text += extracted_text + "\n\n"
            except Exception as e:
                raise Exception(f"PDF படிக்க முடியவில்லை {os.path.basename(pdf_path)}: {str(e)}")
        return text.strip()

    def get_text_chunks(self, text):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", "।", ".", " ", ""],
            length_function=len
        )
        chunks = text_splitter.split_text(text)
        return [chunk for chunk in chunks if chunk.strip()]

    def get_vector_store(self, text_chunks):
        try:
            if not text_chunks:
                raise ValueError("உரைப் பகுதிகள் காலியாக உள்ளன")
            
            # Create and save vector store
            self.vector_store = FAISS.from_texts(text_chunks, embedding=self.embeddings)
            self.vector_store.save_local(self.index_path)
            
        except Exception as e:
            raise Exception(f"வெக்டார் ஸ்டோர் பிழை: {str(e)}")

    def get_conversational_chain(self):
        prompt_template = """நீங்கள் ஒரு தமிழ் உதவியாளர். கொடுக்கப்பட்ட சூழலை மட்டுமே பயன்படுத்தி கேள்விக்கு விரிவான பதில் அளிக்கவும்.
        பதில் முழுமையான தமிழில் இருக்க வேண்டும். சூழலில் தகவல் இல்லை என்றால் "மன்னிக்கவும், இந்த கேள்விக்கான தகவல் ஆவணங்களில் கிடைக்கவில்லை" என்று பதிலளிக்கவும்.
        
        சூழல்: {context}
        
        கேள்வி: {question}
        
        தமிழில் விரிவான பதில்:"""
        
        try:
            model = ChatGroq(
                api_key=groq_api_key,
                model_name="llama3-70b-8192",
                temperature=0.5,
                max_tokens=1000
            )
            prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
            return load_qa_chain(model, chain_type="stuff", prompt=prompt)
        except Exception as e:
            raise Exception(f"மாடல் ஏற்றுவதில் பிழை: {str(e)}")

    def process_question(self, user_question):
        try:
            if not os.path.exists(self.index_path):
                return "முதலில் PDF ஆவணங்களை பதிவேற்றவும்"
                
            if not user_question.strip():
                return "கேள்வியை உள்ளிடவும்"
            
            new_db = FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization=True)
            docs = new_db.similarity_search(user_question, k=4)
            
            if not docs:
                return "தொடர்புடைய தகவல்கள் கிடைக்கவில்லை"
                
            chain = self.get_conversational_chain()
            response = chain.invoke({
                "input_documents": docs,
                "question": user_question
            })
            
            return response["output_text"].strip()
            
        except Exception as e:
            return f"பிழை ஏற்பட்டது: {str(e)}"