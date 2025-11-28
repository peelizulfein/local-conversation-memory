# Conversation Memory

> Cross-reference your AI conversations and recall topics across tools—without giving up your privacy.

Your chat history is scattered across Claude, ChatGPT, Q CLI, and other tools. Each conversation lives in its own silo. This tool unifies them locally, letting you search semantically across everything and discover connections between conversations—all without sending your data anywhere.

**Key features:**
- 🔗 Cross-reference conversations across any tool
- 🔍 Semantic topic recall—find related discussions you forgot about
- 🏠 100% local—your context stays private, no cloud, no API calls
- 📦 Portable JSON format—bring your own chat exports
- 🤖 Agent-friendly output for context injection

## Quick Start

```bash
git clone https://github.com/youruser/conversation-memory.git
cd conversation-memory

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Sync your Q CLI / Kiro CLI conversations
python3 sync_from_q.py

# Search!
python3 recall.py "how did we implement the grid system" -n 3
```

## How It Works

```
Source Chats → Portable JSON → Embeddings (search index)
     ↓              ↓                    ↓
  Q CLI         conversations/      ChromaDB/Weaviate
  Kiro CLI      ├── index.json
  Browser       └── *.json
```

1. **Sync** pulls conversations from source databases (read-only)
2. **Transform** converts to a portable JSON format
3. **Index** generates BGE embeddings for semantic search
4. **Recall** finds relevant context across all your chats

## Usage

### Sync conversations

```bash
# Sync from all sources and index embeddings
python3 sync_from_q.py

# Sync without indexing (faster, JSON only)
python3 sync_from_q.py --no-index
```

### Recall context

```bash
# Plain text output (pipe to your agent)
python3 recall.py "ML training decisions" --project myproject -n 3

# Visual viewer - opens browser to review/filter before copying
python3 recall_viewer.py "architecture decisions" -n 5
```

The visual viewer lets you dismiss irrelevant chunks before copying - useful when you want to audit what context gets fed to an LLM.

### Search & browse

```bash
python3 query.py search "grid indexing" --project myproject -n 3
python3 query.py list --project myproject
python3 query.py show 20251127-abc123
```

## Graph Store (Optional)

For cross-conversation relationships, use the Weaviate graph store:

```bash
# Migrate to Weaviate
python3 migrate_to_weaviate.py

# Find semantically similar conversations
python3 recall_graph.py --similar 20251127-abc123 --threshold 0.8
```

Uses assistant-only embeddings for linking, avoiding false matches from generic prompts like "help me with X".

## Supported Sources

| Source | Location | Auto-synced |
|--------|----------|-------------|
| Q CLI | `~/Library/Application Support/amazon-q/data.sqlite3` | ✓ |
| Kiro CLI | `~/Library/Application Support/kiro-cli/data.sqlite3` | ✓ |
| Browser Chat | `~/Documents/code/chat/chat-backup-*.json` | ✓ |

### Adding your own source

All conversations use a portable JSON format. See [FORMAT.md](FORMAT.md) for the spec.

```json
{
  "id": "20251127-abc123",
  "date": "2025-11-27T09:00:00",
  "title": "Project Discussion",
  "messages": [
    {"role": "user", "content": "...", "timestamp": "..."},
    {"role": "assistant", "content": "...", "timestamp": "..."}
  ],
  "metadata": {"project": "my-project", "source": "my-tool"}
}
```

Map your chat export to this format and drop it in `conversations/`.

## Technical Details

**Embedding Model:** BAAI/bge-large-en-v1.5 (1024 dims, ~1.3GB, runs locally)

**Performance:**
- Indexing: ~100ms per conversation
- Search: <100ms
- Storage: ~1KB/message JSON, ~4KB/chunk embeddings

**Stack:**
- ChromaDB for vector search
- Weaviate (embedded) for graph relationships
- Sentence Transformers for embeddings

## License

MIT
