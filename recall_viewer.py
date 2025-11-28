#!/usr/bin/env python3
"""
Visual recall viewer - opens browser to review and filter results before use.
"""
import argparse
import json
import tempfile
import webbrowser
from pathlib import Path
from graph_store import GraphStore
from conversation_store import ConversationStore
from sentence_transformers import SentenceTransformer

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
<title>Recall: {query}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
h1 {{ color: #333; font-size: 1.4em; }}
.chunk {{ background: white; border-radius: 8px; padding: 16px; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.chunk.dismissed {{ opacity: 0.3; }}
.chunk-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
.chunk-title {{ font-weight: 600; color: #333; }}
.chunk-meta {{ font-size: 0.85em; color: #666; }}
.turn {{ margin: 12px 0; padding: 8px 12px; border-radius: 6px; }}
.turn-user {{ background: #e3f2fd; }}
.turn-assistant {{ background: #f5f5f5; }}
.turn-role {{ font-weight: 600; font-size: 0.8em; color: #666; margin-bottom: 4px; }}
.turn-content {{ white-space: pre-wrap; font-size: 0.9em; line-height: 1.5; }}
.dismiss-btn {{ background: #ff5252; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em; }}
.dismiss-btn:hover {{ background: #ff1744; }}
.dismissed .dismiss-btn {{ background: #4caf50; }}
.output-section {{ background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 8px; margin-top: 30px; }}
.output-section h2 {{ color: #fff; margin-top: 0; font-size: 1.1em; }}
#output {{ white-space: pre-wrap; font-family: monospace; font-size: 0.85em; max-height: 400px; overflow-y: auto; }}
.copy-btn {{ background: #2196f3; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 12px; }}
.copy-btn:hover {{ background: #1976d2; }}
.similarity {{ background: #e8f5e9; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }}
</style>
</head>
<body>
<h1>Recall: {query}</h1>
<p style="color:#666">Click "Dismiss" to remove irrelevant chunks. Copy the filtered output below.</p>

<div id="chunks">
{chunks_html}
</div>

<div class="output-section">
<h2>Filtered Output (copy this)</h2>
<pre id="output"></pre>
<button class="copy-btn" onclick="copyOutput()">Copy to Clipboard</button>
</div>

<script>
const chunks = {chunks_json};

function toggleDismiss(idx) {{
    chunks[idx].dismissed = !chunks[idx].dismissed;
    document.getElementById('chunk-' + idx).classList.toggle('dismissed');
    document.querySelector('#chunk-' + idx + ' .dismiss-btn').textContent = 
        chunks[idx].dismissed ? 'Restore' : 'Dismiss';
    updateOutput();
}}

function updateOutput() {{
    const active = chunks.filter(c => !c.dismissed);
    let out = '=== RECALLED CONTEXT ===\\n\\n';
    active.forEach((c, i) => {{
        out += '--- [' + (i+1) + '] ' + c.title + ' (' + c.date + ') ---\\n';
        out += 'Project: ' + c.project + '\\n\\n';
        c.turns.forEach(t => {{
            out += t.role.toUpperCase() + ':\\n' + t.content + '\\n\\n';
        }});
    }});
    out += '=== END RECALLED CONTEXT ===';
    document.getElementById('output').textContent = out;
}}

function copyOutput() {{
    navigator.clipboard.writeText(document.getElementById('output').textContent);
    document.querySelector('.copy-btn').textContent = 'Copied!';
    setTimeout(() => document.querySelector('.copy-btn').textContent = 'Copy to Clipboard', 2000);
}}

updateOutput();
</script>
</body>
</html>'''

def recall_visual(query: str, n_results: int = 5, project: str = None):
    print("Loading model...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')
    query_emb = model.encode(f"Represent this sentence for searching relevant passages: {query}").tolist()
    
    store = GraphStore()
    json_store = ConversationStore()
    
    results = store.search(query_emb, n_results=n_results, project=project)
    store.close()
    
    if not results:
        print(f"No results for: {query}")
        return
    
    chunks = []
    chunks_html = ""
    
    for i, r in enumerate(results):
        conv_id = r['metadata']['conversation_id']
        conv = json_store.get_conversation(conv_id)
        date = conv['date'][:10] if conv else ""
        
        # Parse turns from chunk text
        text = r['text']
        turns = []
        if "User:" in text and "Assistant:" in text:
            parts = text.split("Assistant:", 1)
            user_part = parts[0].replace("User:", "").strip()
            asst_part = parts[1].strip() if len(parts) > 1 else ""
            turns = [
                {"role": "user", "content": user_part},
                {"role": "assistant", "content": asst_part}
            ]
        
        chunk_data = {
            "title": r['metadata']['conversation_title'],
            "date": date,
            "project": r['metadata']['project'],
            "similarity": f"{(1 - r.get('distance', 0)) * 100:.0f}%",
            "turns": turns,
            "dismissed": False
        }
        chunks.append(chunk_data)
        
        turns_html = ""
        for t in turns:
            role_class = "turn-user" if t['role'] == 'user' else "turn-assistant"
            content_escaped = t['content'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            turns_html += f'''<div class="turn {role_class}">
                <div class="turn-role">{t['role'].upper()}</div>
                <div class="turn-content">{content_escaped}</div>
            </div>'''
        
        chunks_html += f'''<div class="chunk" id="chunk-{i}">
            <div class="chunk-header">
                <div>
                    <span class="chunk-title">{chunk_data['title']}</span>
                    <span class="similarity">{chunk_data['similarity']}</span>
                </div>
                <button class="dismiss-btn" onclick="toggleDismiss({i})">Dismiss</button>
            </div>
            <div class="chunk-meta">{date} · {chunk_data['project']}</div>
            {turns_html}
        </div>'''
    
    html = HTML_TEMPLATE.format(
        query=query,
        chunks_html=chunks_html,
        chunks_json=json.dumps(chunks)
    )
    
    # Write to temp file and open
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
        f.write(html)
        path = f.name
    
    print(f"Opening browser: {path}")
    webbrowser.open(f"file://{path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visual recall viewer")
    parser.add_argument("query", help="What to search for")
    parser.add_argument("-n", type=int, default=5, help="Number of results")
    parser.add_argument("--project", help="Filter by project")
    args = parser.parse_args()
    
    recall_visual(args.query, args.n, args.project)
