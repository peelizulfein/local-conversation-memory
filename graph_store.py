#!/usr/bin/env python3
"""
Graph-based conversation store using embedded Weaviate.
Enables cross-conversation relationships and topic tracking.
"""
import weaviate
from weaviate.classes.config import Configure, Property, DataType, ReferenceProperty
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.embedded import EmbeddedOptions
from pathlib import Path
from typing import List, Dict, Optional
import json

class GraphStore:
    def __init__(self, data_path: str = "~/.local/share/conversation-memory/weaviate"):
        self.data_path = Path(data_path).expanduser()
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        print("Starting embedded Weaviate...")
        self.client = weaviate.WeaviateClient(
            embedded_options=EmbeddedOptions(
                persistence_data_path=str(self.data_path),
            )
        )
        self.client.connect()
        self._init_schema()
        print("✓ Weaviate ready")
    
    def _init_schema(self):
        """Create schema if not exists"""
        # Topic collection
        if not self.client.collections.exists("Topic"):
            self.client.collections.create(
                name="Topic",
                vectorizer_config=Configure.Vectorizer.text2vec_transformers() if False else None,
                properties=[
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="description", data_type=DataType.TEXT),
                ]
            )
        
        # Conversation collection
        if not self.client.collections.exists("Conversation"):
            self.client.collections.create(
                name="Conversation",
                vectorizer_config=None,  # We'll use external embeddings
                properties=[
                    Property(name="conv_id", data_type=DataType.TEXT),
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="date", data_type=DataType.TEXT),
                    Property(name="project", data_type=DataType.TEXT),
                    Property(name="source", data_type=DataType.TEXT),
                    Property(name="summary", data_type=DataType.TEXT),
                    Property(name="topics", data_type=DataType.TEXT_ARRAY),
                    Property(name="tags", data_type=DataType.TEXT_ARRAY),
                ],
            )
        
        # Message chunk collection (for semantic search - full chunks)
        if not self.client.collections.exists("MessageChunk"):
            self.client.collections.create(
                name="MessageChunk",
                vectorizer_config=None,  # External embeddings
                properties=[
                    Property(name="conv_id", data_type=DataType.TEXT),
                    Property(name="chunk_index", data_type=DataType.INT),
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="timestamp", data_type=DataType.TEXT),
                    Property(name="project", data_type=DataType.TEXT),
                    Property(name="title", data_type=DataType.TEXT),
                ],
            )
        
        # Assistant-only chunks (for graph linking - cleaner signal)
        if not self.client.collections.exists("AssistantChunk"):
            self.client.collections.create(
                name="AssistantChunk",
                vectorizer_config=None,
                properties=[
                    Property(name="conv_id", data_type=DataType.TEXT),
                    Property(name="chunk_index", data_type=DataType.INT),
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="project", data_type=DataType.TEXT),
                    Property(name="title", data_type=DataType.TEXT),
                ],
            )
        
        # Decision collection
        if not self.client.collections.exists("Decision"):
            self.client.collections.create(
                name="Decision",
                vectorizer_config=None,
                properties=[
                    Property(name="conv_id", data_type=DataType.TEXT),
                    Property(name="decision", data_type=DataType.TEXT),
                    Property(name="rationale", data_type=DataType.TEXT),
                    Property(name="timestamp", data_type=DataType.TEXT),
                    Property(name="project", data_type=DataType.TEXT),
                ],
            )
    
    def add_conversation(self, conv: Dict, chunks: List[Dict], embeddings: List[List[float]],
                         assistant_chunks: List[Dict] = None, assistant_embeddings: List[List[float]] = None):
        """Add conversation with chunks and embeddings"""
        conv_collection = self.client.collections.get("Conversation")
        chunk_collection = self.client.collections.get("MessageChunk")
        assistant_collection = self.client.collections.get("AssistantChunk")
        
        # Check if exists
        existing = conv_collection.query.fetch_objects(
            filters=Filter.by_property("conv_id").equal(conv["id"]),
            limit=1
        )
        
        if existing.objects:
            # Delete existing data for this conversation
            chunk_collection.data.delete_many(
                where=Filter.by_property("conv_id").equal(conv["id"])
            )
            assistant_collection.data.delete_many(
                where=Filter.by_property("conv_id").equal(conv["id"])
            )
            conv_collection.data.delete_many(
                where=Filter.by_property("conv_id").equal(conv["id"])
            )
        
        # Add conversation
        conv_collection.data.insert({
            "conv_id": conv["id"],
            "title": conv.get("title", ""),
            "date": conv.get("date", ""),
            "project": conv.get("metadata", {}).get("project", ""),
            "source": conv.get("metadata", {}).get("source", ""),
            "summary": "",  # Can be populated later
            "topics": conv.get("metadata", {}).get("topics", []),
            "tags": conv.get("metadata", {}).get("tags", []),
        })
        
        # Add chunks with embeddings (for search)
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_collection.data.insert(
                properties={
                    "conv_id": conv["id"],
                    "chunk_index": i,
                    "content": chunk["text"],
                    "timestamp": chunk["metadata"].get("timestamp", ""),
                    "project": chunk["metadata"].get("project", ""),
                    "title": chunk["metadata"].get("conversation_title", ""),
                },
                vector=embedding
            )
        
        # Add assistant-only chunks (for graph linking)
        if assistant_chunks and assistant_embeddings:
            for i, (chunk, embedding) in enumerate(zip(assistant_chunks, assistant_embeddings)):
                assistant_collection.data.insert(
                    properties={
                        "conv_id": conv["id"],
                        "chunk_index": i,
                        "content": chunk["text"],
                        "project": chunk["metadata"].get("project", ""),
                        "title": chunk["metadata"].get("conversation_title", ""),
                    },
                    vector=embedding
                )
        
        # Add decisions if any
        decisions = conv.get("metadata", {}).get("decisions", [])
        if decisions:
            decision_collection = self.client.collections.get("Decision")
            for dec in decisions:
                decision_collection.data.insert({
                    "conv_id": conv["id"],
                    "decision": dec.get("decision", ""),
                    "rationale": dec.get("rationale", ""),
                    "timestamp": dec.get("timestamp", ""),
                    "project": conv.get("metadata", {}).get("project", ""),
                })
    
    def search(self, query_embedding: List[float], n_results: int = 5, 
               project: str = None, source: str = None) -> List[Dict]:
        """Semantic search across message chunks"""
        chunk_collection = self.client.collections.get("MessageChunk")
        
        filters = None
        if project:
            filters = Filter.by_property("project").equal(project)
        
        results = chunk_collection.query.near_vector(
            near_vector=query_embedding,
            limit=n_results,
            filters=filters,
            return_metadata=MetadataQuery(distance=True)
        )
        
        return [{
            "text": obj.properties["content"],
            "metadata": {
                "conversation_id": obj.properties["conv_id"],
                "conversation_title": obj.properties["title"],
                "project": obj.properties["project"],
                "timestamp": obj.properties["timestamp"],
            },
            "distance": obj.metadata.distance
        } for obj in results.objects]
    
    def find_related_conversations(self, conv_id: str, n_results: int = 5) -> List[Dict]:
        """Find conversations related by topic overlap"""
        conv_collection = self.client.collections.get("Conversation")
        
        # Get source conversation
        source = conv_collection.query.fetch_objects(
            filters=Filter.by_property("conv_id").equal(conv_id),
            limit=1
        )
        if not source.objects:
            return []
        
        source_topics = set(source.objects[0].properties.get("topics", []))
        source_project = source.objects[0].properties.get("project", "")
        
        # Find conversations with overlapping topics or same project
        all_convs = conv_collection.query.fetch_objects(limit=100)
        
        related = []
        for obj in all_convs.objects:
            if obj.properties["conv_id"] == conv_id:
                continue
            
            obj_topics = set(obj.properties.get("topics", []))
            topic_overlap = len(source_topics & obj_topics)
            same_project = obj.properties.get("project") == source_project
            
            if topic_overlap > 0 or same_project:
                related.append({
                    "conv_id": obj.properties["conv_id"],
                    "title": obj.properties["title"],
                    "project": obj.properties["project"],
                    "topic_overlap": topic_overlap,
                    "same_project": same_project,
                })
        
        # Sort by relevance
        related.sort(key=lambda x: (x["topic_overlap"], x["same_project"]), reverse=True)
        return related[:n_results]
    
    def get_all_decisions(self, project: str = None) -> List[Dict]:
        """Get all decisions, optionally filtered by project"""
        decision_collection = self.client.collections.get("Decision")
        
        filters = None
        if project:
            filters = Filter.by_property("project").equal(project)
        
        results = decision_collection.query.fetch_objects(
            filters=filters,
            limit=100
        )
        
        return [{
            "decision": obj.properties["decision"],
            "rationale": obj.properties["rationale"],
            "conv_id": obj.properties["conv_id"],
            "project": obj.properties["project"],
            "timestamp": obj.properties["timestamp"],
        } for obj in results.objects]
    
    def find_similar_across_conversations(self, conv_id: str, threshold: float = 0.85, top_k: int = 10) -> List[Dict]:
        """
        Find chunks from OTHER conversations that are similar to this conversation's chunks.
        Uses assistant-only embeddings for cleaner signal (avoids generic prompt matching).
        """
        chunk_collection = self.client.collections.get("AssistantChunk")
        
        # Get all chunks for this conversation
        source_chunks = chunk_collection.query.fetch_objects(
            filters=Filter.by_property("conv_id").equal(conv_id),
            include_vector=True,
            limit=100
        )
        
        if not source_chunks.objects:
            # Fall back to MessageChunk if no assistant chunks
            chunk_collection = self.client.collections.get("MessageChunk")
            source_chunks = chunk_collection.query.fetch_objects(
                filters=Filter.by_property("conv_id").equal(conv_id),
                include_vector=True,
                limit=100
            )
            if not source_chunks.objects:
                return []
        
        links = []
        seen_convs = set()
        
        for source_chunk in source_chunks.objects:
            # Find similar chunks from other conversations
            similar = chunk_collection.query.near_vector(
                near_vector=source_chunk.vector["default"],
                limit=top_k + 5,  # Extra to filter out same-conv matches
                return_metadata=MetadataQuery(distance=True)
            )
            
            for match in similar.objects:
                # Skip same conversation
                if match.properties["conv_id"] == conv_id:
                    continue
                
                # Skip if below threshold (distance, so lower = more similar)
                similarity = 1 - match.metadata.distance
                if similarity < threshold:
                    continue
                
                match_conv_id = match.properties["conv_id"]
                
                # Track best match per conversation
                if match_conv_id not in seen_convs:
                    seen_convs.add(match_conv_id)
                    links.append({
                        "conv_id": match_conv_id,
                        "title": match.properties["title"],
                        "project": match.properties["project"],
                        "similarity": similarity,
                        "source_snippet": source_chunk.properties["content"][:100],
                        "match_snippet": match.properties["content"][:100],
                    })
        
        # Sort by similarity
        links.sort(key=lambda x: x["similarity"], reverse=True)
        return links[:top_k]
    
    def build_conversation_graph(self, threshold: float = 0.8) -> Dict[str, List[Dict]]:
        """
        Build a graph of all conversation relationships based on embedding similarity.
        Returns adjacency list: {conv_id: [related_convs]}
        """
        conv_collection = self.client.collections.get("Conversation")
        all_convs = conv_collection.query.fetch_objects(limit=500)
        
        graph = {}
        for conv in all_convs.objects:
            conv_id = conv.properties["conv_id"]
            related = self.find_similar_across_conversations(conv_id, threshold=threshold, top_k=5)
            if related:
                graph[conv_id] = related
        
        return graph

    def get_topics_across_projects(self) -> Dict[str, List[str]]:
        """Get topic distribution across projects"""
        conv_collection = self.client.collections.get("Conversation")
        results = conv_collection.query.fetch_objects(limit=500)
        
        project_topics = {}
        for obj in results.objects:
            project = obj.properties.get("project", "unknown")
            topics = obj.properties.get("topics", [])
            if project not in project_topics:
                project_topics[project] = set()
            project_topics[project].update(topics)
        
        return {k: list(v) for k, v in project_topics.items()}
    
    def close(self):
        self.client.close()


if __name__ == "__main__":
    # Test
    store = GraphStore()
    print("Schema initialized")
    store.close()
