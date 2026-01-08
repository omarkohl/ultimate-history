# ADR 001: Neo4j for Graph Storage

* **Status:** Accepted
* **Date:** 2025-01
* **Decision effort:** ~5 hours of reading and experimenting (not thorough)

## Context

The project needed a solution to support several workflows:
- Direct Anki editing with CrowdAnki exports
- Non-technical users editing CSV files
- Technical users doing sophisticated graph analysis
- LLM-assisted entity creation (works better via API than direct CSV manipulation)

CSVs remain the canonical source. The graph DB provides a more ergonomic interface for exploring and editing relationships between historical entities.

## Decision

Use **Neo4j** (hosted on AuraDB, with Bloom for UI editing).

## Alternatives Considered

### NocoDB (evaluated, rejected)

- **Pros:** More convenient UI than raw spreadsheets
- **Cons:**
  - Slow initial CSV import and relationship formation
  - Relationships require a junction table with descriptions, making editing require multiple UI jumps
  - Still fundamentally a spreadsheet interface, not a true graph

### Memgraph (evaluated, rejected)

- **Pros:** Open source, Cypher-compatible
- **Cons:** No UI for editing entities except through Cypher queries. Sometimes a double-click edit is all you need.
- **Note:** Did not evaluate Cypher compatibility, performance, or ecosystem in detail.

### SQLite with graph extension (not evaluated)

Considered but not evaluated due to time constraints. Might be worth revisiting.

### CSVs with custom scripts / SQLite cache (not evaluated)

Considered but not evaluated due to time constraints. Graph DBs seemed more promising for the use case. Might be worth revisiting.

### Airtable (not considered)

Commercial product, did not consider.

## Consequences

### Positive

- Graph structure matches the data model naturally
- Neo4j Bloom provides visual graph editing
- Cypher queries enable complex relationship analysis
- LLM integration via API works well

### Negative

- **Commercial risk:** AuraDB (hosted) and Bloom (UI) are commercial. Pricing or licensing changes could force migration.
- **Mitigation:** Core Neo4j is open source. Fallback plan is self-hosting with Docker and using Neo4j Browser (simpler but functional UI). If all fails, evaluate alternatives.
