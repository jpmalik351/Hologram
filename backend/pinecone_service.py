"""
Pinecone Service - Vector database operations

Provides:
- Index management (get or create)
- Text embeddings (using OpenAI)
- Vector storage and retrieval

Note: This service handles both document chunks and conversation storage,
though currently only document chunks are used for RAG.
"""

from pinecone import Pinecone, ServerlessSpec
import os
from dotenv import load_dotenv
import openai

load_dotenv()

# Initialize Pinecone client
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Initialize OpenAI client for embeddings
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configuration
index_name = os.getenv("PINECONE_INDEX_NAME", "hologram-conversations")
dimension = 1024  # Match your Pinecone index dimension


def get_or_create_index():
    """
    Get existing Pinecone index or create a new one if it doesn't exist.
    
    Returns:
        pinecone.Index: The Pinecone index object, or None if Pinecone is not configured
    
    Note:
        - Creates index with cosine similarity metric (good for text embeddings)
        - Uses serverless spec (AWS, us-east-1 by default)
        - Index is persistent - same index every time
    """
    try:
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            return None
            
        # Check if index exists
        existing_indexes = pc.list_indexes()
        if index_name in existing_indexes.names():
            # Index exists, return it
            return pc.Index(index_name)
        else:
            # Index doesn't exist, create it
            pc.create_index(
                name=index_name,
                dimension=dimension,  # 1536 for OpenAI embeddings
                metric="cosine",  # Cosine similarity for text embeddings
                spec=ServerlessSpec(
                    cloud="aws",
                    region=os.getenv("PINECONE_REGION", "us-east-1")
                )
            )
            return pc.Index(index_name)
    except Exception as e:
        print(f"Pinecone index setup failed: {str(e)}")
        return None


def get_embedding(text: str) -> list:
    """
    Get embedding vector for text using OpenAI embeddings.
    
    Args:
        text: Text to embed
    
    Returns:
        list: 1024-dimensional embedding vector
    
    Raises:
        Exception: If embedding generation fails
    
    Note:
        - Uses text-embedding-3-small model with 1024 dimensions
        - Returns a list of 1024 floats
        - These vectors capture semantic meaning of the text
        - Used for BOTH storing documents AND querying (same function)
    """
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=1024  # Match your Pinecone index dimension
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Embedding error: {str(e)}")



def delete_chunks(chunk_ids: list):
    """
    Delete chunks from Pinecone index by their IDs.
    
    Args:
        chunk_ids: List of chunk IDs to delete
    
    Raises:
        Exception: If deletion fails
    
    Note:
        - Used when deleting files or overwriting duplicates
        - Removes vectors permanently from Pinecone
        - Cannot be undone
    """
    try:
        if not chunk_ids:
            return
        
        index = get_or_create_index()
        if index is None:
            raise Exception("Pinecone index not available")
        
        # Delete vectors by ID
        index.delete(ids=chunk_ids)
        
    except Exception as e:
        raise Exception(f"Failed to delete chunks from Pinecone: {str(e)}")
