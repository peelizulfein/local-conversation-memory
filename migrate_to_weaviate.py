#!/usr/bin/env python3
"""
Migrate conversations from JSON store to Weaviate graph store.
"""
from conversation_store import ConversationStore
from graph_store import GraphStore
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple

def chunk_conversation(conversation: Dict) -> Tuple[List[Dict], List[Dict]]:
    """
    Chunk conversation into:
    1. Full user-assistant pairs (for search)
    2. Assistant-only responses (for graph linking)
    """
    full_chunks = []
    assistant_chunks = []
    messages = conversation.get("messages", [])
    
    for i in range(0, len(messages), 2):
        if i + 1 < len(messages):
            user_msg = messages[i].get('content', '')
            asst_msg = messages[i + 1].get('content', '')
            
            # Full chunk for search
            full_chunks.append({
                "text": f"User: {user_msg}\n\nAssistant: {asst_msg}",
                "metadata": {
                    "conversation_id": conversation["id"],
                    "conversation_title": conversation.get("title") or "",
                    "project": conversation.get("metadata", {}).get("project") or "",
                    "timestamp": messages[i].get("timestamp") or "",
                    "chunk_index": i // 2
                }
            })
            
            # Assistant-only for graph linking (skip short responses)
            if len(asst_msg) > 50:
                assistant_chunks.append({
                    "text": asst_msg,
                    "metadata": {
                        "conversation_id": conversation["id"],
                        "conversation_title": conversation.get("title") or "",
                        "project": conversation.get("metadata", {}).get("project") or "",
                        "chunk_index": i // 2
                    }
                })
    
    return full_chunks, assistant_chunks

def migrate():
    print("Loading embedding model...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')
    print("✓ Model loaded")
    
    json_store = ConversationStore()
    graph_store = GraphStore()
    
    conversations = json_store.get_all_conversations()
    print(f"Found {len(conversations)} conversations to migrate")
    
    for conv in conversations:
        full_chunks, assistant_chunks = chunk_conversation(conv)
        if not full_chunks:
            continue
        
        # Generate embeddings for full chunks (search)
        full_texts = [c["text"] for c in full_chunks]
        full_embeddings = model.encode(full_texts).tolist()
        
        # Generate embeddings for assistant chunks (graph linking)
        assistant_embeddings = []
        if assistant_chunks:
            assistant_texts = [c["text"] for c in assistant_chunks]
            assistant_embeddings = model.encode(assistant_texts).tolist()
        
        # Add to graph store
        graph_store.add_conversation(
            conv, full_chunks, full_embeddings,
            assistant_chunks, assistant_embeddings
        )
        print(f"✓ Migrated: {conv.get('title', conv['id'])[:45]} ({len(full_chunks)} chunks, {len(assistant_chunks)} asst)")
    
    print(f"\n✓ Migration complete: {len(conversations)} conversations")
    graph_store.close()

if __name__ == "__main__":
    migrate()
