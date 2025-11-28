#!/usr/bin/env python3
"""
Sync conversations from Q CLI SQLite database to conversation-memory JSON store.
Read-only access to Q CLI data - does not modify the source database.
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from conversation_store import ConversationStore

Q_CLI_DB = Path("~/Library/Application Support/amazon-q/data.sqlite3").expanduser()
KIRO_CLI_DB = Path("~/Library/Application Support/kiro-cli/data.sqlite3").expanduser()
CHAT_BACKUP_DIR = Path("~/Documents/code/chat").expanduser()

def get_q_conversations() -> List[Dict]:
    """Read conversations from Q CLI and Kiro CLI databases (read-only)"""
    conversations = []
    
    for db_path, source in [(Q_CLI_DB, "q-cli"), (KIRO_CLI_DB, "kiro-cli")]:
        if not db_path.exists():
            continue
        
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # Read-only
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM conversations")
        
        for key, value in cursor.fetchall():
            try:
                data = json.loads(value)
                data['_project_path'] = key
                data['_source'] = source
                conversations.append(data)
            except json.JSONDecodeError:
                continue
        
        conn.close()
    
    return conversations

def transform_conversation(q_conv: Dict) -> Optional[Dict]:
    """Transform Q CLI format to conversation-memory schema"""
    history = q_conv.get('history', [])
    if not history:
        return None
    
    project_path = q_conv.get('_project_path', '')
    source = q_conv.get('_source', 'q-cli')
    project_name = Path(project_path).name if project_path else 'unknown'
    
    messages = []
    for turn in history:
        # Extract user message
        user_data = turn.get('user', {})
        user_content = user_data.get('content', {})
        prompt = user_content.get('Prompt', {}).get('prompt', '')
        user_ts = user_data.get('timestamp', datetime.now().isoformat())
        
        if prompt:
            messages.append({
                "role": "user",
                "content": prompt,
                "timestamp": user_ts
            })
        
        # Extract assistant response
        assistant_data = turn.get('assistant', {})
        response = assistant_data.get('Response', {})
        assistant_content = response.get('content', '')
        
        if assistant_content:
            messages.append({
                "role": "assistant", 
                "content": assistant_content,
                "timestamp": user_ts  # Use user timestamp as proxy
            })
    
    if not messages:
        return None
    
    # Generate stable ID from project path
    path_hash = hashlib.sha256(project_path.encode()).hexdigest()[:8]
    first_ts = messages[0].get('timestamp') or datetime.now().isoformat()
    date_part = first_ts[:10].replace('-', '')
    conv_id = f"{date_part}-{path_hash}"
    
    return {
        "id": conv_id,
        "date": first_ts,
        "title": f"Q CLI: {project_name}",
        "messages": messages,
        "metadata": {
            "project": project_name,
            "project_path": project_path,
            "topics": [],
            "decisions": [],
            "related_conversations": [],
            "tags": [source],
            "artifacts": [],
            "source": source,
            "q_conversation_id": q_conv.get('conversation_id')
        }
    }

def get_browser_conversations() -> List[Dict]:
    """Read conversations from browser chat backup JSON files"""
    conversations = []
    
    if not CHAT_BACKUP_DIR.exists():
        return conversations
    
    for backup_file in CHAT_BACKUP_DIR.glob("chat-backup-*.json"):
        try:
            with open(backup_file) as f:
                data = json.load(f)
            
            for thread in data.get('indexedDB', {}).get('threads', []):
                thread['_source'] = 'browser-chat'
                thread['_backup_file'] = str(backup_file)
                conversations.append(thread)
        except (json.JSONDecodeError, KeyError):
            continue
    
    return conversations

def transform_browser_conversation(thread: Dict) -> Optional[Dict]:
    """Transform browser chat format to conversation-memory schema"""
    branches = thread.get('branches', [])
    if not branches:
        return None
    
    # Use first branch (main)
    branch = branches[0]
    raw_messages = branch.get('messages', [])
    if not raw_messages:
        return None
    
    messages = []
    for msg in raw_messages:
        role = "user" if msg.get('sender') == 'Human' else "assistant"
        content = msg.get('text', '')
        if content:
            messages.append({
                "role": role,
                "content": content,
                "timestamp": branch.get('createdAt', datetime.now().isoformat())
            })
    
    if not messages:
        return None
    
    # Generate stable ID from thread id
    thread_id = thread.get('id', '')
    id_hash = hashlib.sha256(thread_id.encode()).hexdigest()[:8]
    created = branch.get('createdAt', datetime.now().isoformat())
    date_part = created[:10].replace('-', '')
    conv_id = f"{date_part}-{id_hash}"
    
    return {
        "id": conv_id,
        "date": created,
        "title": thread.get('name', 'Browser Chat'),
        "messages": messages,
        "metadata": {
            "project": "browser-chat",
            "topics": [],
            "decisions": [],
            "related_conversations": [],
            "tags": ["browser-chat"],
            "artifacts": [],
            "source": "browser-chat",
            "thread_id": thread_id
        }
    }

def sync(index_embeddings: bool = True):
    """Main sync function"""
    print("Reading from Q CLI / Kiro CLI databases (read-only)...")
    q_convs = get_q_conversations()
    print(f"Found {len(q_convs)} CLI conversations")
    
    print("Reading browser chat backups...")
    browser_convs = get_browser_conversations()
    print(f"Found {len(browser_convs)} browser chat threads")
    
    store = ConversationStore()
    manager = None
    if index_embeddings:
        from embedding_manager import EmbeddingManager
        manager = EmbeddingManager()
    
    synced = 0
    
    # Sync CLI conversations
    for q_conv in q_convs:
        conv = transform_conversation(q_conv)
        if not conv:
            continue
        
        if _save_conversation(store, conv, manager):
            synced += 1
            print(f"✓ Synced: {conv['title']} ({len(conv['messages'])} messages)")
    
    # Sync browser conversations
    for thread in browser_convs:
        conv = transform_browser_conversation(thread)
        if not conv:
            continue
        
        if _save_conversation(store, conv, manager):
            synced += 1
            print(f"✓ Synced: {conv['title']} ({len(conv['messages'])} messages)")
    
    print(f"\nSync complete: {synced} conversations updated")

def _save_conversation(store, conv, manager) -> bool:
    """Save conversation if new or updated. Returns True if saved."""
    existing = store.get_conversation(conv['id'])
    if existing:
        if len(conv['messages']) <= len(existing.get('messages', [])):
            return False
    
    conv_file = store.conversations_dir / f"{conv['id']}.json"
    with open(conv_file, 'w') as f:
        json.dump(conv, f, indent=2)
    
    existing_ids = [c['id'] for c in store.index['conversations']]
    if conv['id'] not in existing_ids:
        store.index['conversations'].append({
            "id": conv['id'],
            "date": conv['date'],
            "title": conv['title'],
            "project": conv['metadata']['project'],
            "topics": [],
            "file": str(conv_file)
        })
        store._save_index()
    
    if manager:
        manager.index_conversation(conv['id'])
    
    return True
    
    print(f"\nSync complete: {synced} conversations updated")

if __name__ == "__main__":
    import sys
    index = "--no-index" not in sys.argv
    sync(index_embeddings=index)
