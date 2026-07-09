# System Architecture & Multi-Agent Design

The AI Research Lab Partner acts as an orchestration layer connecting LLMs, vector databases, document parsers, and external scholarly APIs through highly specialized LangGraph workflows. 

Below is the complete architectural diagram representing the entire system!

## Architecture Diagram (Mermaid)

```mermaid
graph TD
    %% Users & Entry Point
    User([Researcher / Client])
    API[FastAPI Gateway]
    User -- HTTP POST --> API

    %% Sub-Systems
    subgraph Observability
        LF[Langfuse]
    end

    subgraph External Dependencies
        ArXiv((ArXiv API))
        LlamaParse((LlamaParse Cloud))
        LLM((LLM API: OpenAI/Gemini))
    end

    subgraph Data Persistence
        PG[(PostgreSQL + pgvector)]
    end

    %% Modules
    subgraph Discovery Module
        DiscRoute[/POST /discover/]
        DiscClient(Discovery Client)
    end

    subgraph Ingestion Pipeline
        IngestRoute[/POST /ingest/]
        LlamaParser(LlamaParse Integration)
        Chunker(Semantic Chunker)
        Embedder(Text Embedder)
    end

    subgraph Query Agent Workflow
        QueryRoute[/POST /query/]
        MgrNode[Manager Node<br/>Intent Classifier]
        SpecNode[Specialist Node<br/>Summarize / Gap / Organize]
        RefNode[Reflection Node<br/>Evaluator & SLO Checker]
    end

    subgraph Compare Reflexion Workflow
        CompRoute[/POST /compare/]
        RetNode[Retriever Node]
        SynNode[Synthesizer Node]
        CritNode[Critic Node<br/>Evaluator]
        RevNode[Revision Node]
    end

    %% Routing
    API --> DiscRoute
    API --> IngestRoute
    API --> QueryRoute
    API --> CompRoute

    %% Discovery Data Flow
    DiscRoute --> DiscClient
    DiscClient -- HTTPS Search --> ArXiv

    %% Ingestion Data Flow
    IngestRoute --> LlamaParser
    LlamaParser -- PDF Extraction --> LlamaParse
    LlamaParser --> Chunker
    Chunker --> Embedder
    Embedder -- Vector Insert --> PG

    %% Query Data Flow
    QueryRoute --> MgrNode
    MgrNode -- Routes Intent --> SpecNode
    SpecNode -- Fetches Context --> PG
    SpecNode -- Generates Draft --> LLM
    SpecNode --> RefNode
    RefNode -- Scores Draft --> LF

    %% Compare Data Flow
    CompRoute --> RetNode
    RetNode -- Fetches Multi-Doc Context --> PG
    RetNode --> SynNode
    SynNode -- Drafts Comparison --> LLM
    SynNode --> CritNode
    CritNode -- Validates Draft --> LLM
    CritNode -- "Satisfactory: NO" --> RevNode
    RevNode -- Fixes Draft --> LLM
    RevNode --> CritNode
    CritNode -- "Satisfactory: YES" --> EndCompare((Return Response))

    %% Telemetry Links
    DiscClient -. Traces Latency .-> LF
    IngestRoute -. Traces Flow .-> LF
    QueryRoute -. Traces Flow .-> LF
    CompRoute -. Traces Flow .-> LF
```

### Key Highlights
- **Discovery**: A fast, stateless proxy to ArXiv via secure HTTPS.
- **Ingestion**: A linear data pipeline. LlamaParse handles complex multi-modal layout logic (tables/equations) before text chunking and vector storage.
- **Query (LangGraph)**: A 3-step sequential graph. The **Manager** dynamically routes the user to a specialized persona, the **Specialist** creates a grounded draft, and the **Reflector** acts as an AI judge to score the output against strict SLOs.
- **Compare (LangGraph Reflexion)**: A cyclic evaluation graph. The **Critic** operates in a `while` loop (up to `MAX_ITERATIONS`), forcefully returning the draft to the **Revisor** if it fails structural or accuracy checks.
- **Observability**: Every single node, network call, and LLM query acts as a span bubbling up to **Langfuse** for strict performance metrics.
