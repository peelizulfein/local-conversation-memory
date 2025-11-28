#!/usr/bin/env python3
"""
Recall relevant context from conversation memory.
Outputs plain text suitable for piping into an agent session.

Usage:
    python3 recall.py "how did we implement the grid system"
    python3 recall.py "ML training decisions" --project moneypenny -n 3
"""
import sys
import argparse
from embedding_manager import EmbeddingManager
from conversation_store import ConversationStore

def recall(query: str, n_results: int = 3, project: str = None):
    manager = EmbeddingManager()
    store = ConversationStore()
    results = manager.search(query, n_results=n_results, project=project)
    
    if not results:
        print(f"No relevant conversations found for: {query}")
        return
    
    print(f"=== RECALLED CONTEXT: {query} ===\n")
    
    for i, r in enumerate(results, 1):
        meta = r['metadata']
        conv_id = meta['conversation_id']
        
        # Get full conversation for date
        conv = store.get_conversation(conv_id)
        conv_date = conv['date'][:10] if conv else meta.get('timestamp', '')[:10]
        
        print(f"--- [{i}] {meta['conversation_title']} ---")
        print(f"Date: {conv_date} | Project: {meta['project']}")
        print(f"\n{r['text']}\n")
        
        # Generate brief summary of this chunk
        text = r['text']
        first_user = text.split("User:")[-1].split("Assistant:")[0].strip()[:150]
        print(f"Summary: User asked about {first_user}...")
        print()
    
    print("=== END RECALLED CONTEXT ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recall context from conversation memory")
    parser.add_argument("query", help="What to search for")
    parser.add_argument("-n", type=int, default=3, help="Number of results")
    parser.add_argument("--project", help="Filter by project")
    args = parser.parse_args()
    
    recall(args.query, args.n, args.project)
