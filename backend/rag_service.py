"""
RAG (Retrieval Augmented Generation) Service

Retrieves relevant knowledge from Pinecone vector database to augment LLM responses.
This is read-only - it retrieves information but doesn't store conversations.

Flow:
1. User asks a question
2. Question is converted to embedding vector
3. Pinecone searches for similar vectors (semantic search)
4. Returns the original text from metadata
5. Text is added to system prompt for LLM
"""

from pinecone_service import get_or_create_index, get_embedding
import os


def retrieve_character_knowledge(query: str, top_k: int = 3) -> str:
    """
    Retrieve relevant knowledge from Pinecone based on user query.
    
    This performs semantic search - finds knowledge chunks that are semantically
    similar to the query, even if they don't contain exact keywords.
    
    Args:
        query: User's question or message
        top_k: Number of most relevant chunks to retrieve (default: 3)
    
    Returns:
        str: Formatted string with relevant knowledge chunks, or empty string if:
             - Pinecone is not configured
             - No relevant knowledge found
             - Error occurred
    
    Note:
        - Uses cosine similarity to find semantically similar chunks
        - Returns full text from metadata (original text is stored there)
        - Chunks are separated by double newlines for readability
    """
    try:
        # Get Pinecone index
        index = get_or_create_index()
        if index is None:
            return ""  # Pinecone not configured, return empty (graceful failure)
        
        # Convert query to embedding vector
        # This allows semantic search (finding similar meaning, not just keywords)
        query_embedding = get_embedding(query)
        
        # Search Pinecone for relevant knowledge chunks
        # Pinecone finds vectors with highest cosine similarity to query
        results = index.query(
            vector=query_embedding,
            top_k=top_k,  # Get top K most similar chunks
            include_metadata=True  # Include metadata (which contains the original text)
        )
        
        # Extract relevant knowledge from results
        knowledge_parts = []
        for match in results.matches:
            if match.metadata:
                # Get the original text from metadata
                # This is the full chunk text that was stored during upload
                content = match.metadata.get("content") or match.metadata.get("text") or ""
                if content:
                    knowledge_parts.append(content)
        
        # Combine chunks with double newlines for readability
        if knowledge_parts:
            return "\n\n".join(knowledge_parts)
        return ""  # No knowledge found
        
    except Exception as e:
        print(f"Warning: RAG retrieval failed: {str(e)}")
        return ""  # Return empty on error (graceful failure)
