#!/usr/bin/env python3
"""
CLI tool for querying conversation memory
"""
import sys
import argparse
from embedding_manager import EmbeddingManager
from conversation_store import ConversationStore

def search_conversations(args):
    """Search for relevant conversations"""
    manager = EmbeddingManager()
    
    results = manager.search(
        query=args.query,
        n_results=args.n,
        project=args.project,
        topic=args.topic
    )
    
    print(f"\nFound {len(results)} relevant conversations:\n")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['metadata']['conversation_title']}")
        print(f"   ID: {result['metadata']['conversation_id']}")
        print(f"   Project: {result['metadata']['project']}")
        print(f"   Topics: {result['metadata']['topics']}")
        print(f"   Date: {result['metadata']['timestamp'][:10]}")
        print(f"\n   {result['text'][:300]}...")
        print("-" * 80)

def list_conversations(args):
    """List all conversations"""
    store = ConversationStore()
    
    conversations = store.list_conversations(
        project=args.project,
        topic=args.topic,
        tag=args.tag
    )
    
    print(f"\nFound {len(conversations)} conversations:\n")
    
    for conv in conversations:
        print(f"• {conv['title']}")
        print(f"  ID: {conv['id']}")
        print(f"  Date: {conv['date'][:10]}")
        print(f"  Project: {conv.get('project', 'N/A')}")
        print(f"  Topics: {', '.join(conv.get('topics', []))}")
        print()

def show_conversation(args):
    """Show full conversation"""
    store = ConversationStore()
    conv = store.get_conversation(args.id)
    
    if not conv:
        print(f"Conversation {args.id} not found")
        return
    
    print(f"\n{conv['title']}")
    print("=" * 80)
    print(f"Date: {conv['date']}")
    print(f"Project: {conv['metadata'].get('project', 'N/A')}")
    print(f"Topics: {', '.join(conv['metadata'].get('topics', []))}")
    print("\nMessages:")
    print("-" * 80)
    
    for msg in conv["messages"]:
        print(f"\n{msg['role'].upper()}:")
        print(msg['content'])
        print()
    
    if conv['metadata'].get('decisions'):
        print("\nDecisions Made:")
        print("-" * 80)
        for decision in conv['metadata']['decisions']:
            print(f"• {decision['decision']}")
            print(f"  Rationale: {decision['rationale']}")
            print()

def rebuild_index(args):
    """Rebuild embedding index from JSON files"""
    manager = EmbeddingManager()
    manager.rebuild_index()

def main():
    parser = argparse.ArgumentParser(description="Query conversation memory")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search conversations')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('-n', type=int, default=5, help='Number of results')
    search_parser.add_argument('--project', help='Filter by project')
    search_parser.add_argument('--topic', help='Filter by topic')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List conversations')
    list_parser.add_argument('--project', help='Filter by project')
    list_parser.add_argument('--topic', help='Filter by topic')
    list_parser.add_argument('--tag', help='Filter by tag')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show full conversation')
    show_parser.add_argument('id', help='Conversation ID')
    
    # Rebuild command
    rebuild_parser = subparsers.add_parser('rebuild', help='Rebuild embedding index')
    
    args = parser.parse_args()
    
    if args.command == 'search':
        search_conversations(args)
    elif args.command == 'list':
        list_conversations(args)
    elif args.command == 'show':
        show_conversation(args)
    elif args.command == 'rebuild':
        rebuild_index(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
