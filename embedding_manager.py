#!/usr/bin/env python3
"""
Embedding manager - ChromaDB with BGE embeddings
"""
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
from typing import List, Dict, Optional
from conversation_store import ConversationStore

class EmbeddingManager:
    def __init__(self, base_path: str = "~/Documents/code/conversation-memory"):
        self.base_path = Path(base_path).expanduser()
        self.db_path = self.base_path / "embeddings"
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize BGE model
        print("Loading BGE embedding model...")
        self.model = SentenceTransformer('BAAI/bge-large-en-v1.5')
        print("✓ Model loaded")
        
        self.store = ConversationStore(base_path)
    
    def _encode_query(self, query: str) -> List[float]:
        """Encode query with BGE instruction prefix"""
        instruction = "Represent this sentence for searching relevant passages: "
        return self.model.encode(instruction + query).tolist()
    
    def _encode_document(self, text: str) -> List[float]:
        """Encode document (no prefix needed)"""
        return self.model.encode(text).tolist()
    
    def _chunk_conversation(self, conversation: Dict) -> List[Dict]:
        """
        Chunk conversation into semantic segments
        
        Strategy:
        1. Each message is a chunk
        2. Group consecutive messages by topic (if >3 messages)
        3. Include metadata for filtering
        """
        chunks = []
        messages = conversation["messages"]
        
        # Simple strategy: each user-assistant pair is a chunk
        for i in range(0, len(messages), 2):
            if i + 1 < len(messages):
                user_msg = messages[i]
                assistant_msg = messages[i + 1]
                
                chunk_text = f"User: {user_msg['content']}\n\nAssistant: {assistant_msg['content']}"
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "conversation_id": conversation["id"],
                        "conversation_title": conversation.get("title") or "",
                        "project": conversation["metadata"].get("project") or "",
                        "topics": ",".join(conversation["metadata"].get("topics", [])),
                        "timestamp": user_msg.get("timestamp") or "",
                        "chunk_index": i // 2
                    }
                })
        
        return chunks
    
    def index_conversation(self, conv_id: str):
        """Index a single conversation"""
        conversation = self.store.get_conversation(conv_id)
        if not conversation:
            print(f"Conversation {conv_id} not found")
            return
        
        chunks = self._chunk_conversation(conversation)
        
        for chunk in chunks:
            chunk_id = f"{conv_id}_chunk_{chunk['metadata']['chunk_index']}"
            embedding = self._encode_document(chunk["text"])
            
            self.collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk["text"]],
                metadatas=[chunk["metadata"]]
            )
        
        print(f"✓ Indexed {len(chunks)} chunks from {conv_id}")
    
    def rebuild_index(self):
        """Rebuild entire index from JSON files"""
        print("Rebuilding embedding index from JSON files...")
        
        # Clear existing collection
        self.client.delete_collection("conversations")
        self.collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Index all conversations
        conversations = self.store.get_all_conversations()
        for conv in conversations:
            self.index_conversation(conv["id"])
        
        print(f"✓ Rebuilt index with {len(conversations)} conversations")
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        project: Optional[str] = None,
        topic: Optional[str] = None
    ) -> List[Dict]:
        """
        Semantic search across conversations
        
        Returns:
            List of relevant chunks with metadata
        """
        query_embedding = self._encode_query(query)
        
        # Build filter
        where = {}
        if project:
            where["project"] = project
        if topic:
            where["topics"] = {"$contains": topic}
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None
        )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None
            })
        
        return formatted
    
    def get_related_conversations(self, conv_id: str, n_results: int = 5) -> List[str]:
        """Find conversations related to a given conversation"""
        conversation = self.store.get_conversation(conv_id)
        if not conversation:
            return []
        
        # Use conversation title + topics as query
        query = f"{conversation['title']} {' '.join(conversation['metadata'].get('topics', []))}"
        
        results = self.search(query, n_results=n_results + 1)  # +1 to exclude self
        
        # Extract unique conversation IDs (excluding the query conversation)
        related_ids = []
        for result in results:
            related_id = result["metadata"]["conversation_id"]
            if related_id != conv_id and related_id not in related_ids:
                related_ids.append(related_id)
        
        return related_ids[:n_results]


if __name__ == "__main__":
    # Example usage
    manager = EmbeddingManager()
    
    # Search for relevant context
    results = manager.search(
        "How did we decide on grid indexing?",
        project="moneypenny",
        n_results=3
    )
    
    print("\nSearch results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['metadata']['conversation_title']}")
        print(f"   Project: {result['metadata']['project']}")
        print(f"   Topics: {result['metadata']['topics']}")
        print(f"   Text: {result['text'][:200]}...")
