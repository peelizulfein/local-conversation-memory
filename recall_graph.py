#!/usr/bin/env python3
"""
Recall context using Weaviate graph store.
Supports cross-conversation relationships and topic tracking.

Usage:
    python3 recall_graph.py "how did we implement the grid system"
    python3 recall_graph.py "ML training decisions" --project moneypenny -n 3
    python3 recall_graph.py --decisions --project moneypenny
    python3 recall_graph.py --related 20251127-abc123
"""
import argparse
from graph_store import GraphStore
from conversation_store import ConversationStore
from sentence_transformers import SentenceTransformer

def recall(query: str, n_results: int = 3, project: str = None):
    print("Loading embedding model...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')
    
    # BGE query prefix
    query_text = f"Represent this sentence for searching relevant passages: {query}"
    query_embedding = model.encode(query_text).tolist()
    
    store = GraphStore()
    json_store = ConversationStore()
    
    results = store.search(query_embedding, n_results=n_results, project=project)
    
    if not results:
        print(f"No relevant conversations found for: {query}")
        store.close()
        return
    
    print(f"=== RECALLED CONTEXT: {query} ===\n")
    
    for i, r in enumerate(results, 1):
        meta = r['metadata']
        conv_id = meta['conversation_id']
        
        # Get full conversation for date
        conv = json_store.get_conversation(conv_id)
        conv_date = conv['date'][:10] if conv else meta.get('timestamp', '')[:10]
        
        print(f"--- [{i}] {meta['conversation_title']} ---")
        print(f"Date: {conv_date} | Project: {meta['project']}")
        print(f"\n{r['text']}\n")
        
        # Brief summary
        text = r['text']
        first_user = text.split("User:")[-1].split("Assistant:")[0].strip()[:150]
        print(f"Summary: User asked about {first_user}...")
        print()
    
    print("=== END RECALLED CONTEXT ===")
    store.close()

def show_decisions(project: str = None):
    store = GraphStore()
    decisions = store.get_all_decisions(project=project)
    
    if not decisions:
        print("No decisions found")
        store.close()
        return
    
    print(f"=== DECISIONS{' for ' + project if project else ''} ===\n")
    
    for d in decisions:
        print(f"• {d['decision']}")
        print(f"  Rationale: {d['rationale']}")
        print(f"  Project: {d['project']} | Conversation: {d['conv_id']}")
        print()
    
    store.close()

def show_similar(conv_id: str, threshold: float = 0.8):
    """Find conversations with semantically similar content"""
    store = GraphStore()
    similar = store.find_similar_across_conversations(conv_id, threshold=threshold)
    
    if not similar:
        print(f"No similar conversations found for {conv_id} (threshold: {threshold})")
        store.close()
        return
    
    print(f"=== SIMILAR TO {conv_id} (threshold: {threshold}) ===\n")
    
    for s in similar:
        print(f"• {s['title']} ({s['similarity']:.0%} similar)")
        print(f"  ID: {s['conv_id']} | Project: {s['project']}")
        print(f"  Source: \"{s['source_snippet']}...\"")
        print(f"  Match:  \"{s['match_snippet']}...\"")
        print()
    
    store.close()

def show_related(conv_id: str):
    store = GraphStore()
    related = store.find_related_conversations(conv_id)
    
    if not related:
        print(f"No related conversations found for {conv_id}")
        store.close()
        return
    
    print(f"=== RELATED TO {conv_id} ===\n")
    
    for r in related:
        overlap = f"{r['topic_overlap']} shared topics" if r['topic_overlap'] else ""
        same_proj = "same project" if r['same_project'] else ""
        reason = ", ".join(filter(None, [overlap, same_proj]))
        
        print(f"• {r['title']}")
        print(f"  ID: {r['conv_id']} | Project: {r['project']}")
        print(f"  Reason: {reason}")
        print()
    
    store.close()

def show_topics():
    store = GraphStore()
    topics = store.get_topics_across_projects()
    
    print("=== TOPICS BY PROJECT ===\n")
    for project, topic_list in topics.items():
        print(f"{project}:")
        for t in topic_list:
            print(f"  • {t}")
        print()
    
    store.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recall context from conversation graph")
    parser.add_argument("query", nargs="?", help="What to search for")
    parser.add_argument("-n", type=int, default=3, help="Number of results")
    parser.add_argument("--project", help="Filter by project")
    parser.add_argument("--decisions", action="store_true", help="Show all decisions")
    parser.add_argument("--related", metavar="CONV_ID", help="Find related conversations (by topic/project)")
    parser.add_argument("--similar", metavar="CONV_ID", help="Find similar conversations (by embedding)")
    parser.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold (0-1)")
    parser.add_argument("--topics", action="store_true", help="Show topics by project")
    
    args = parser.parse_args()
    
    if args.decisions:
        show_decisions(args.project)
    elif args.related:
        show_related(args.related)
    elif args.similar:
        show_similar(args.similar, args.threshold)
    elif args.topics:
        show_topics()
    elif args.query:
        recall(args.query, args.n, args.project)
    else:
        parser.print_help()
