# API Reference

The backend exposes a FastAPI REST interface available at `http://127.0.0.1:8000`. You can view the interactive Swagger UI at `http://127.0.0.1:8000/docs`.

---

## 1. Discovery API

### `POST /discover`
Search the ArXiv database for scientific literature.

**Request Payload:**
```json
{
  "query": "transformer agents",
  "limit": 5
}
```

**Response Payload:**
```json
{
  "results": [
    {
      "paper_id": "http://arxiv.org/abs/2305.12345",
      "title": "LLM Agents in Practice",
      "authors": ["John Doe", "Jane Smith"],
      "abstract": "This paper discusses...",
      "url": "http://arxiv.org/abs/2305.12345",
      "pdf_url": "http://arxiv.org/pdf/2305.12345.pdf"
    }
  ],
  "processing_time_sec": 1.25,
  "cached": false
}
```

---

## 2. Ingestion API

### `POST /ingest/url`
Download a PDF from a URL, parse it using LlamaParse, chunk the text, and store the embeddings in pgvector.

**Request Payload:**
```json
{
  "url": "http://arxiv.org/pdf/2305.12345.pdf"
}
```

**Response Payload:**
```json
{
  "status": "completed",
  "document_id": "doc_12345678",
  "file_hash": "a1b2c3d4e5f6...",
  "chunks_indexed": 42,
  "chunks_failed": 0,
  "figures_processed": 3,
  "tables_processed": 1,
  "metadata": {},
  "processing_time_sec": 45.3
}
```

---

## 3. Query API

### `POST /query`
Ask a question about a specific ingested document. Invokes the Sequential Evaluator LangGraph workflow.

**Request Payload:**
```json
{
  "document_id": "doc_12345678",
  "question": "What are the limitations of this method?",
  "thread_id": "optional-uuid-for-conversations"
}
```

**Response Payload:**
```json
{
  "query_id": "q_a1b2c3d4",
  "answer": "The main limitations are X and Y [chunk_42].",
  "citations": [
    {
      "chunk_id": "chunk_42",
      "page": 4,
      "snippet_ref": "text"
    }
  ],
  "confidence": 0.85,
  "faithfulness": 0.9,
  "relevance": 0.9,
  "agent_used": "gap_finder",
  "needs_clarification": false,
  "clarification_prompt": null,
  "escalated": false,
  "thread_id": "optional-uuid-for-conversations",
  "processing_time_sec": 8.5,
  "cached": true
}
```

---

## 4. Compare API

### `POST /compare`
Compare multiple documents. Invokes the Cyclic Reflexion LangGraph workflow.

**Request Payload:**
```json
{
  "document_ids": ["doc_12345678", "doc_87654321"],
  "question": "Compare the evaluation datasets used in these papers."
}
```

**Response Payload:**
```json
{
  "query_id": "cmp_z9y8x7w6",
  "answer": "## Comparison\nDocument A uses Dataset 1 [chunk_12], while Document B uses Dataset 2 [chunk_55].",
  "citations": [
    {
      "chunk_id": "chunk_12",
      "page": 2,
      "snippet_ref": "text"
    },
    {
      "chunk_id": "chunk_55",
      "page": 6,
      "snippet_ref": "text"
    }
  ],
  "processing_time_sec": 15.2,
  "cached": false
}
```
