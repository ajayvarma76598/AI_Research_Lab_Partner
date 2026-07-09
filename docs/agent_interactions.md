# Agent Interaction Design

The AI Research Lab Partner utilizes **LangGraph** to coordinate multi-agent workflows. This allows specific LLM personas to handle specialized tasks autonomously, ensuring high accuracy and strict quality control.

There are two primary multi-agent workflows in the system.

---

## 1. Query Workflow (Sequential Evaluator Pattern)
Used for single-document queries (`POST /query`). This is a 3-stage sequential graph where a routing agent selects a specialist, which is then judged by an evaluator.

### 🧑‍💼 Manager Node (The Router)
- **Role:** Classifies the user's intent.
- **Behavior:** Receives the raw question and uses a strict system prompt to classify it as either `summarization`, `comparison`, `gap_finder`, or `knowledge_organizer`. It outputs exactly one word.

### 🕵️‍♂️ Specialist Node (The Generator)
- **Role:** Generates the grounded answer.
- **Behavior:** Dynamically assumes the persona chosen by the Manager. It fetches context chunks from PostgreSQL, strictly abides by the rule to answer ONLY using the context, and injects exact `[chunk_id]` citations into the text. If the context is empty or irrelevant, it explicitly refuses to answer.

### ⚖️ Reflection Node (The Evaluator)
- **Role:** Scores the Specialist's draft against strict Service Level Objectives (SLOs).
- **Behavior:** Evaluates the draft for **Faithfulness** (is it grounded?) and **Relevance** (does it answer the question?). It computes a final **Confidence** score. If the score fails to meet the configured thresholds, it sets `slo_met=False` (which allows the frontend to request human clarification).

---

## 2. Compare Workflow (Cyclic Reflexion Pattern)
Used for multi-document comparisons (`POST /compare`). This is a loop-based graph that forces the LLM to recursively critique and revise its own work until it passes a quality check.

### 📚 Retriever Node
- **Role:** Data aggregator.
- **Behavior:** Iterates through all provided `document_ids`, fetches the relevant context chunks from the vector database, and concatenates them while explicitly tagging which chunks belong to which paper.

### ✍️ Synthesizer Node
- **Role:** First draft generator.
- **Behavior:** Reviews the concatenated context and drafts an initial comparison using Markdown formatting.

### 🧐 Critic Node (The Gatekeeper)
- **Role:** Validates the draft.
- **Behavior:** Inspects the draft against a strict checklist: (1) Does it answer the question? (2) Does it mention both papers? (3) Is it accurate?
- **Decision:** It outputs `SATISFACTORY: YES` or `SATISFACTORY: NO`, alongside a detailed critique. 
  - If **YES**: The graph ends.
  - If **NO**: The graph routes to the Revision Node.

### 🛠️ Revision Node
- **Role:** The fixer.
- **Behavior:** Receives the failed draft, the original context, and the Critic's feedback. It rewrites the draft specifically addressing the feedback, then loops back to the Critic Node for re-evaluation. (This loop is capped at `MAX_ITERATIONS` to prevent infinite loops).
