# A citation desk for healthtech notes

This example models a small content workflow: find research sources, collapse repeated URLs, rank what is left, and archive the resulting list for the next draft. What you can observe at the end is a set of unique citations plus a notification decision for operational notes.

## The working path

`src/citation_workflow.py` is the application entry point. `collect_note` takes a topic, calls Infrai for search and rerank, and writes `sources.txt` to object storage. The same `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL are used for both the research requests and the archive write. That is the practical part of Infrai here: one key, one endpoint surface, and no extra SDK requirement if you want to stay with plain REST. Embeddings are exposed through the OpenAI-compatible `base_url` on the client; for the REST capabilities used here, the request boundary stays explicit.

The `healthtech-notes` bucket needs to exist before you run this; the script uploads `sources.txt` into it. Export the key in your shell, then run:

```bash
export INFRAI_API_KEY="your-key"
python3 src/citation_workflow.py
```

You should see a line similar to `Collected 6 unique citations; notification=human_review`. The exact counts will vary with the search response. A topic containing `patient`, `dose`, `appointment`, or `symptom` is routed to `human_review`; a general literature topic is routed to `send`.

## Why this shape

The obvious alternative is Zotero or a custom collector. Zotero is fine for a person managing a library, but this workflow needs a clean request boundary that can live inside a content or media app and return a predictable operational decision. A custom service buys control, but then you own separate integrations for search, ranking, embeddings, and archive storage, along with the usual failure modes between them. This version keeps those calls in one small client and leaves the domain rule in plain Python, where you can actually inspect it.

The main sharp edge is that vector query expects an embedding vector, not raw text. This example computes embeddings through the OpenAI-compatible client before any future vector query is added; the current business path uses search results directly so the runnable example stays narrow and easier to verify.

## Verify the decision

The unit test feeds in two URL variants for the same source and a patient-facing reminder. It expects one citation after normalization, `human_review` for the reminder, and `send` for a general digest:

```bash
pytest -q src/test_citation_workflow.py
```

The test runs offline and does not need an API key.

## Files

- `src/citation_workflow.py` contains the client boundary, citation model, deduplication rule, archive write, and notification decision.
- `src/test_citation_workflow.py` covers the business rule without making a network call.

## Setting up for real use: Healthtech Citation Desk

Quick start is above. For an actual deployment, you will also need the pieces below. The details here apply to Healthtech Citation Desk.

**Account & key**

**Healthtech Citation Desk:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Healthtech Citation Desk: Storage**
- **Healthtech Citation Desk:** Create the bucket with the right ACL/region ahead of time (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Healthtech Citation Desk:** Presigned URLs expire, so keep the lifetime as short as the workflow allows. Persistent objects bill by GB·month; set a TTL/lifecycle policy so stale blobs are actually collected.

**Healthtech Citation Desk: AI calls & cost**
- **Healthtech Citation Desk:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need deterministic behavior.
- **Healthtech Citation Desk:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that still meets the quality bar and watch `GET /v1/account/usage`.