# Conversation Format Specification

This document describes the portable JSON format used by the conversation-memory system. Any chat tool can be integrated by mapping its export format to this schema.

## File Structure

Each conversation is stored as a single JSON file in `conversations/`:

```
conversations/
├── index.json              # Lookup index (auto-generated)
├── 20251127-abc123.json    # Individual conversation files
└── 20251128-def456.json
```

## Conversation Schema

```json
{
  "id": "20251127-abc123",
  "date": "2025-11-27T09:00:00",
  "title": "Project Discussion",
  "messages": [
    {
      "role": "user",
      "content": "Your message here",
      "timestamp": "2025-11-27T09:00:00"
    },
    {
      "role": "assistant", 
      "content": "Assistant response here",
      "timestamp": "2025-11-27T09:01:00"
    }
  ],
  "metadata": {
    "project": "my-project",
    "topics": ["topic1", "topic2"],
    "decisions": [],
    "related_conversations": [],
    "tags": ["source-tag"],
    "artifacts": [],
    "source": "source-identifier"
  }
}
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier. Recommended format: `YYYYMMDD-hash` |
| `date` | string | ISO 8601 timestamp of conversation start |
| `title` | string | Human-readable title |
| `messages` | array | Array of message objects |

### Message Object

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | Either `"user"` or `"assistant"` |
| `content` | string | The message text |
| `timestamp` | string | ISO 8601 timestamp (can be null) |

## Optional Metadata

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Project name for filtering |
| `topics` | array | Topic tags |
| `decisions` | array | Key decisions made (see below) |
| `related_conversations` | array | IDs of related conversations |
| `tags` | array | Freeform tags |
| `artifacts` | array | Files created/modified (see below) |
| `source` | string | Origin of the conversation (e.g., "q-cli", "browser-chat") |

### Decision Object

```json
{
  "decision": "Use 1-indexed coordinates",
  "rationale": "Matches human intuition",
  "timestamp": "2025-11-27T09:15:00"
}
```

### Artifact Object

```json
{
  "type": "code",
  "path": "src/app.js",
  "description": "Updated validation logic"
}
```

Type can be: `code`, `document`, `data`, `config`

## Generating IDs

Recommended approach for stable, unique IDs:

```python
import hashlib
from datetime import datetime

def generate_id(unique_key: str, date: str = None) -> str:
    """Generate conversation ID from unique key and date."""
    date_part = (date or datetime.now().isoformat())[:10].replace('-', '')
    hash_part = hashlib.sha256(unique_key.encode()).hexdigest()[:8]
    return f"{date_part}-{hash_part}"

# Examples:
generate_id("/path/to/project")           # From file path
generate_id("thread-uuid-123")            # From thread ID
generate_id("user@email.com-2025-11-27")  # From user + date
```

## Mapping From Other Formats

### Example: Browser Chat Export

Browser chat tools often export in this format:

```json
{
  "threads": [
    {
      "id": "uuid",
      "name": "Thread Title",
      "messages": [
        {"text": "...", "sender": "Human"},
        {"text": "...", "sender": "Assistant"}
      ],
      "createdAt": "2025-11-27T09:00:00Z"
    }
  ]
}
```

Mapping:
- `thread.name` → `title`
- `thread.id` → use for ID generation
- `thread.createdAt` → `date`
- `message.text` → `content`
- `message.sender == "Human"` → `role: "user"`
- `message.sender == "Assistant"` → `role: "assistant"`

### Example: Q CLI / Kiro CLI

Q CLI stores conversations in SQLite with this structure:

```json
{
  "conversation_id": "uuid",
  "history": [
    {
      "user": {
        "content": {"Prompt": {"prompt": "..."}},
        "timestamp": "..."
      },
      "assistant": {
        "Response": {"content": "..."}
      }
    }
  ]
}
```

Mapping:
- `history[].user.content.Prompt.prompt` → user message `content`
- `history[].assistant.Response.content` → assistant message `content`
- `history[].user.timestamp` → `timestamp`
- Working directory path → `project`

## Index File

The `index.json` file is auto-generated and provides fast lookups:

```json
{
  "conversations": [
    {
      "id": "20251127-abc123",
      "date": "2025-11-27T09:00:00",
      "title": "Project Discussion",
      "project": "my-project",
      "topics": ["topic1"],
      "file": "/path/to/20251127-abc123.json"
    }
  ]
}
```

You don't need to create this manually - it's updated automatically when conversations are added.

## Adding Custom Sources

To add support for a new chat source:

1. Write a transform function that converts your format to this schema
2. Add it to `sync_from_q.py` or create a separate import script
3. Use a unique `source` tag in metadata for filtering

See `sync_from_q.py` for examples of `transform_conversation()` and `transform_browser_conversation()`.
