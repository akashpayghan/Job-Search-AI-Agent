import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict
from pypdf import PdfReader
from datetime import datetime
from config import Config
import streamlit as st

class ResumeDatabase:
    """Handles ChromaDB operations for resume storage and retrieval"""
    
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Use OpenAI text-embedding-3-small model (faster and cheaper)
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=Config.OPENAI_API_KEY,
            model_name="text-embedding-3-small"
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME,
            embedding_function=self.embedding_function
        )
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF resume"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if not text.strip():
                raise ValueError("No text could be extracted from the PDF")
            
            return text.strip()
        except Exception as e:
            st.error(f"Error extracting text from PDF: {e}")
            raise
    
    def store_resume(self, resume_text: str, metadata: Dict = None):
        """Store resume in ChromaDB with embeddings"""
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text is empty")
        
        if metadata is None:
            metadata = {
                "type": "resume", 
                "timestamp": datetime.now().isoformat(),
                "length": len(resume_text)
            }
        
        try:
            # Check if resume already exists
            existing = self.collection.get(ids=["resume_001"])
            
            if existing and existing['ids']:
                # Update existing resume
                self.collection.update(
                    documents=[resume_text],
                    metadatas=[metadata],
                    ids=["resume_001"]
                )
                st.success(f"✅ Resume updated! ({len(resume_text)} characters)")
            else:
                # Add new resume
                self.collection.add(
                    documents=[resume_text],
                    metadatas=[metadata],
                    ids=["resume_001"]
                )
                st.success(f"✅ Resume stored! ({len(resume_text)} characters)")
            
            # Verify storage
            verification = self.collection.get(ids=["resume_001"])
            if not verification['documents']:
                raise ValueError("Resume storage verification failed")
            
            return True
            
        except Exception as e:
            st.error(f"Error storing resume: {e}")
            raise
    
    def get_resume_context(self, query: str, n_results: int = 1) -> str:
        """Retrieve relevant resume sections based on job query"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if results and results['documents'] and len(results['documents']) > 0:
                if results['documents'][0]:
                    return results['documents'][0][0]
            return ""
        except Exception as e:
            st.warning(f"Error retrieving resume context: {e}")
            return ""
    
    def get_full_resume(self) -> str:
        """Get complete resume text"""
        try:
            results = self.collection.get(ids=["resume_001"])
            
            if results and 'documents' in results and results['documents']:
                if len(results['documents']) > 0:
                    resume_text = results['documents'][0]
                    st.info(f"📄 Resume retrieved: {len(resume_text)} characters")
                    return resume_text
            
            # If not found, return empty string
            st.warning("⚠️ No resume found in database")
            return ""
            
        except Exception as e:
            st.error(f"❌ Error retrieving resume: {e}")
            return ""
    
    def check_resume_exists(self) -> bool:
        """Check if resume exists in database"""
        try:
            results = self.collection.get(ids=["resume_001"])
            return bool(results and results['documents'] and len(results['documents']) > 0)
        except:
            return False
    
    def delete_resume(self):
        """Delete resume from database"""
        try:
            self.collection.delete(ids=["resume_001"])
            st.success("Resume deleted successfully")
            return True
        except Exception as e:
            st.error(f"Error deleting resume: {e}")
            return False
