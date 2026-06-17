"""
Vector Store — Qdrant interface for storing and retrieving
embedded documents (news, fundamentals, macro data).
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, SearchRequest
)
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import uuid
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config.settings import (
    QDRANT_URL, QDRANT_API_KEY, QDRANT_LOCAL,
    COLLECTION_NAME, EMBEDDING_MODEL
)


class VectorStore:
    def __init__(self):
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self.vector_size = self.encoder.get_sentence_embedding_dimension()
        self._connect()
        self._ensure_collection()

    def _connect(self):
        """Connect to Qdrant (local or cloud)."""
        if QDRANT_LOCAL:
            self.client = QdrantClient(path="./data/qdrant_local")
            print("[VectorStore] Using local Qdrant storage")
        elif QDRANT_API_KEY:
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            print(f"[VectorStore] Connected to Qdrant cloud: {QDRANT_URL}")
        else:
            # In-memory for dev/testing
            self.client = QdrantClient(":memory:")
            print("[VectorStore] Using in-memory Qdrant (dev mode)")

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        from qdrant_client.models import PayloadSchemaType
        existing = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.vector_size,
                distance=Distance.COSINE
            )
        )
        print(f"[VectorStore] Created collection: {COLLECTION_NAME}")

        # Create payload indexes for filtering (required by Qdrant cloud)
        self.client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="ticker",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        self.client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="doc_type",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print(f"[VectorStore] Indexes ensured for ticker + doc_type")

    def embed(self, text: str) -> List[float]:
        """Encode a text string into an embedding vector."""
        return self.encoder.encode(text).tolist()

    def upsert(self, documents: List[Dict]):
        """
        Upsert documents into the vector store.
        Each document must have: text, metadata (ticker, doc_type, date)
        """
        points = []
        for doc in documents:
            text = doc["text"]
            metadata = doc.get("metadata", {})
            vector = self.embed(text)
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={**metadata, "text": text}
                )
            )

        if points:
            self.client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"[VectorStore] Upserted {len(points)} documents")

    def search(
        self,
        query: str,
        top_k: int = 5,
        ticker_filter: Optional[str] = None,
        doc_type_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Semantic search over the vector store.
        Optionally filter by ticker or document type.
        """
        query_vector = self.embed(query)

        # Build filters
        conditions = []
        if ticker_filter:
            conditions.append(
                FieldCondition(key="ticker", match=MatchValue(value=ticker_filter))
            )
        if doc_type_filter:
            conditions.append(
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type_filter))
            )

        search_filter = Filter(must=conditions) if conditions else None

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter,
        )

        return [
            {
                "text": hit.payload.get("text", ""),
                "score": round(hit.score, 4),
                "ticker": hit.payload.get("ticker", ""),
                "doc_type": hit.payload.get("doc_type", ""),
                "date": hit.payload.get("date", ""),
                "source": hit.payload.get("source", ""),
            }
            for hit in results
        ]

    def delete_by_ticker(self, ticker: str):
        """Remove all documents for a given ticker (for refresh)."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))]
            )
        )
        print(f"[VectorStore] Deleted documents for {ticker}")

    def get_collection_info(self) -> Dict:
        info = self.client.get_collection(COLLECTION_NAME)
        count = getattr(info, 'points_count', None) or getattr(info, 'vectors_count', None)
        return {
        "name": COLLECTION_NAME,
        "vectors_count": count,
        "points_count": count,
        }


# Singleton instance
_store = None

def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


if __name__ == "__main__":
    store = get_vector_store()
    # Test upsert and search
    store.upsert([
        {
            "text": "Reliance Industries reported strong Q3 results with 15% revenue growth driven by Jio and retail.",
            "metadata": {"ticker": "RELIANCE.NS", "doc_type": "news", "date": "2025-01-15", "source": "MoneyControl"}
        },
        {
            "text": "RBI keeps repo rate unchanged at 6.50% citing inflation concerns.",
            "metadata": {"ticker": "MARKET", "doc_type": "macro", "date": "2025-01-10", "source": "RBI"}
        }
    ])

    results = store.search("Reliance quarterly earnings growth", top_k=2)
    for r in results:
        print(f"[{r['score']}] {r['text'][:80]}...")

    print(store.get_collection_info())
