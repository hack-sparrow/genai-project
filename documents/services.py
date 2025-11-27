import os
from pathlib import Path
from typing import List, Optional
from django.conf import settings
import traceback

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

try:
    from openai import RateLimitError, AuthenticationError, APIError
except ImportError:
    # Fallback for older versions
    RateLimitError = Exception
    AuthenticationError = Exception
    APIError = Exception


class DocumentProcessingService:
    """Service for processing documents and managing embeddings."""
    
    def __init__(self):
        """Initialize the service with embeddings model."""
        if not settings.OPENAI_API_KEY:
            self.embeddings = None
        else:
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=settings.OPENAI_API_KEY
            )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
    
    def load_pdf(self, file_path: str) -> List[Document]:
        """Load PDF file and extract text."""
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        return documents
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks."""
        return self.text_splitter.split_documents(documents)
    
    def create_vectorstore(self, documents: List[Document], vectorstore_path: str) -> FAISS:
        """Create FAISS vector store from documents."""
        try:
            vectorstore = FAISS.from_documents(documents, self.embeddings)
            vectorstore.save_local(vectorstore_path)
            return vectorstore
        except (RateLimitError, AuthenticationError, APIError) as e:
            # Handle OpenAI API errors
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
                error_msg = (
                    "OpenAI API rate limit exceeded or insufficient quota. "
                    "Please check your OpenAI account billing and plan. "
                    "You may need to add credits or upgrade your plan."
                )
                raise ValueError(error_msg) from e
            elif "authentication" in error_str or "401" in error_str:
                error_msg = (
                    "OpenAI API authentication failed. "
                    "Please check that your OPENAI_API_KEY is correct and valid."
                )
                raise ValueError(error_msg) from e
            else:
                error_msg = f"OpenAI API error: {str(e)}"
                raise ValueError(error_msg) from e
        except Exception as e:
            # Catch any other exceptions and check if they're OpenAI-related
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
                error_msg = (
                    "OpenAI API rate limit exceeded or insufficient quota. "
                    "Please check your OpenAI account billing and plan. "
                    "You may need to add credits or upgrade your plan."
                )
                raise ValueError(error_msg) from e
            elif "authentication" in error_str or "401" in error_str:
                error_msg = (
                    "OpenAI API authentication failed. "
                    "Please check that your OPENAI_API_KEY is correct and valid."
                )
                raise ValueError(error_msg) from e
            # Re-raise if it's not an OpenAI error
            raise
    
    def load_vectorstore(self, vectorstore_path: str) -> FAISS:
        """Load existing FAISS vector store."""
        if not os.path.exists(vectorstore_path):
            raise FileNotFoundError(f"Vector store not found at {vectorstore_path}")
        return FAISS.load_local(
            vectorstore_path,
            self.embeddings,
            allow_dangerous_deserialization=True
        )
    
    def process_document(self, file_path: str, document_id: int) -> str:
        """
        Process a document: load, split, create embeddings, and save to FAISS.
        
        Returns:
            Path to the saved vectorstore
        """
        if not self.embeddings:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        
        # Load PDF
        documents = self.load_pdf(file_path)
        
        # Add metadata to documents
        for doc in documents:
            doc.metadata['document_id'] = document_id
            doc.metadata['source'] = os.path.basename(file_path)
        
        # Split into chunks
        chunks = self.split_documents(documents)
        
        # Create vectorstore path
        vectorstore_dir = Path(settings.MEDIA_ROOT) / "vectorstores"
        vectorstore_dir.mkdir(parents=True, exist_ok=True)
        vectorstore_path = str(vectorstore_dir / f"doc_{document_id}")
        
        # Create and save vectorstore
        self.create_vectorstore(chunks, vectorstore_path)
        
        return vectorstore_path
    
    def search_documents(self, query: str, vectorstore_path: str, k: int = None) -> List[Document]:
        """
        Search for similar documents in the vectorstore.
        
        Args:
            query: Search query
            vectorstore_path: Path to the FAISS vectorstore
            k: Number of results to return (defaults to settings.SIMILARITY_SEARCH_K)
        
        Returns:
            List of similar documents
        """
        if not self.embeddings:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        
        if k is None:
            k = settings.SIMILARITY_SEARCH_K
        
        try:
            vectorstore = self.load_vectorstore(vectorstore_path)
            results = vectorstore.similarity_search(query, k=k)
            return results
        except (RateLimitError, AuthenticationError, APIError) as e:
            # Handle OpenAI API errors
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
                error_msg = (
                    "OpenAI API rate limit exceeded. "
                    "Please wait a moment and try again, or check your OpenAI account billing."
                )
                raise ValueError(error_msg) from e
            elif "authentication" in error_str or "401" in error_str:
                error_msg = (
                    "OpenAI API authentication failed. "
                    "Please check that your OPENAI_API_KEY is correct."
                )
                raise ValueError(error_msg) from e
            else:
                error_msg = f"OpenAI API error during search: {str(e)}"
                raise ValueError(error_msg) from e
        except Exception as e:
            # Catch any other exceptions and check if they're OpenAI-related
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
                error_msg = (
                    "OpenAI API rate limit exceeded. "
                    "Please wait a moment and try again, or check your OpenAI account billing."
                )
                raise ValueError(error_msg) from e
            elif "authentication" in error_str or "401" in error_str:
                error_msg = (
                    "OpenAI API authentication failed. "
                    "Please check that your OPENAI_API_KEY is correct."
                )
                raise ValueError(error_msg) from e
            # Re-raise if it's not an OpenAI error
            raise
    
    def search_all_documents(self, query: str, document_ids: List[int], k: int = None) -> List[Document]:
        """
        Search across multiple document vectorstores.
        
        Args:
            query: Search query
            document_ids: List of document IDs to search
            k: Number of results per document
        
        Returns:
            Combined list of similar documents from all vectorstores
        """
        if k is None:
            k = settings.SIMILARITY_SEARCH_K
        
        all_results = []
        vectorstore_dir = Path(settings.MEDIA_ROOT) / "vectorstores"
        
        for doc_id in document_ids:
            vectorstore_path = str(vectorstore_dir / f"doc_{doc_id}")
            if os.path.exists(vectorstore_path):
                try:
                    results = self.search_documents(query, vectorstore_path, k=k)
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error searching document {doc_id}: {e}")
        
        # Sort by relevance (FAISS returns results sorted by similarity)
        return all_results[:k * len(document_ids)]


# Global service instance (will be initialized when needed)
document_service = None

def get_document_service():
    """Get or create the document service instance."""
    global document_service
    if document_service is None:
        document_service = DocumentProcessingService()
    return document_service

