#!/usr/bin/env python3
"""
Conversation storage manager - JSON as source of truth
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class ConversationStore:
    def __init__(self, base_path: str = "~/Documents/code/conversation-memory"):
        self.base_path = Path(base_path).expanduser()
        self.conversations_dir = self.base_path / "conversations"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.conversations_dir / "index.json"
        self._load_index()
    
    def _load_index(self):
        """Load conversation index"""
        if self.index_file.exists():
            with open(self.index_file) as f:
                self.index = json.load(f)
        else:
            self.index = {"conversations": []}
    
    def _save_index(self):
        """Save conversation index"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def add_conversation(
        self,
        messages: List[Dict],
        title: str,
        project: Optional[str] = None,
        topics: Optional[List[str]] = None,
        decisions: Optional[List[Dict]] = None,
        related_conversations: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        artifacts: Optional[List[Dict]] = None
    ) -> str:
        """
        Add a new conversation to the store
        
        Returns:
            conversation_id: Unique ID for this conversation
        """
        # Generate ID
        date = datetime.now()
        content_hash = hashlib.sha256(
            json.dumps(messages, sort_keys=True).encode()
        ).hexdigest()[:8]
        conv_id = f"{date.strftime('%Y%m%d')}-{content_hash}"
        
        # Build conversation object
        conversation = {
            "id": conv_id,
            "date": date.isoformat(),
            "title": title,
            "messages": messages,
            "metadata": {
                "project": project,
                "topics": topics or [],
                "decisions": decisions or [],
                "related_conversations": related_conversations or [],
                "tags": tags or [],
                "artifacts": artifacts or []
            }
        }
        
        # Save individual conversation file
        conv_file = self.conversations_dir / f"{conv_id}.json"
        with open(conv_file, 'w') as f:
            json.dump(conversation, f, indent=2)
        
        # Update index
        self.index["conversations"].append({
            "id": conv_id,
            "date": date.isoformat(),
            "title": title,
            "project": project,
            "topics": topics or [],
            "file": str(conv_file)
        })
        self._save_index()
        
        return conv_id
    
    def get_conversation(self, conv_id: str) -> Optional[Dict]:
        """Retrieve a conversation by ID"""
        conv_file = self.conversations_dir / f"{conv_id}.json"
        if conv_file.exists():
            with open(conv_file) as f:
                return json.load(f)
        return None
    
    def list_conversations(
        self,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[Dict]:
        """List conversations with optional filters"""
        results = []
        for conv_meta in self.index["conversations"]:
            if project and conv_meta.get("project") != project:
                continue
            if topic and topic not in conv_meta.get("topics", []):
                continue
            if tag:
                conv = self.get_conversation(conv_meta["id"])
                if tag not in conv["metadata"].get("tags", []):
                    continue
            results.append(conv_meta)
        return results
    
    def get_all_conversations(self) -> List[Dict]:
        """Get all conversations (for rebuilding embeddings)"""
        conversations = []
        for conv_meta in self.index["conversations"]:
            conv = self.get_conversation(conv_meta["id"])
            if conv:
                conversations.append(conv)
        return conversations
    
    def update_metadata(self, conv_id: str, metadata_updates: Dict):
        """Update conversation metadata"""
        conv = self.get_conversation(conv_id)
        if conv:
            conv["metadata"].update(metadata_updates)
            conv_file = self.conversations_dir / f"{conv_id}.json"
            with open(conv_file, 'w') as f:
                json.dump(conv, f, indent=2)
            
            # Update index
            for conv_meta in self.index["conversations"]:
                if conv_meta["id"] == conv_id:
                    conv_meta.update({
                        "project": conv["metadata"].get("project"),
                        "topics": conv["metadata"].get("topics", [])
                    })
            self._save_index()


if __name__ == "__main__":
    # Example usage
    store = ConversationStore()
    
    # Add a conversation
    conv_id = store.add_conversation(
        messages=[
            {"role": "user", "content": "Help me with fragment layout", "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": "Sure! Let's discuss...", "timestamp": datetime.now().isoformat()}
        ],
        title="Fragment Layout Discussion",
        project="moneypenny",
        topics=["visual-annotation", "ml-training", "fragment-placement"],
        decisions=[
            {
                "decision": "Use 1-indexed coordinates for annotation tool",
                "rationale": "Matches human intuition",
                "timestamp": datetime.now().isoformat()
            }
        ],
        tags=["architecture", "indexing"],
        artifacts=[
            {
                "type": "code",
                "path": "visual-annotation/app.js",
                "description": "Updated grid validation"
            }
        ]
    )
    
    print(f"Created conversation: {conv_id}")
    
    # List conversations
    convs = store.list_conversations(project="moneypenny")
    print(f"Found {len(convs)} moneypenny conversations")
