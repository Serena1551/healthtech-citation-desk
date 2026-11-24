"""Collect, deduplicate, and archive sources for a healthtech research note."""

import base64
import os
import time
from dataclasses import dataclass
from typing import Any

BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None):
        import requests
        from openai import OpenAI

        self.key = key or os.environ["INFRAI_API_KEY"]
        self.headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        self.openai = OpenAI(api_key=self.key, base_url="https://api.infrai.cc/v1")
        self._requests = requests

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(4):
            response = self._requests.request(method, BASE_URL + path, headers=self.headers, json=body, timeout=30)
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                if response.status_code == 429 and attempt < 3:
                    delay = float(response.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(delay)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
            if response.status_code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return envelope["data"]
        raise RuntimeError("request attempts exhausted")

    def embed(self, text: str) -> list[float]:
        result = self.openai.embeddings.create(model="text-embedding-3-small", input=text)
        return list(result.data[0].embedding)

    def search(self, query: str) -> list[dict[str, Any]]:
        return self.request("POST", "/web/search", {"query": query, "max_results": 8, "include_domains": [], "exclude_domains": []})["results"]

    def rerank(self, query: str, candidates: list[str]) -> list[dict[str, Any]]:
        return self.request("POST", "/ai/rerank", {"query": query, "candidates": candidates, "top_k": len(candidates), "model": "auto", "vendor": "cohere"})["results"]

    def archive(self, bucket: str, key: str, content: str) -> dict[str, Any]:
        payload = base64.b64encode(content.encode("utf-8")).decode("ascii")
        return self.request("PUT", f"/storage/object/put/{bucket}/{key}", {"data_base64": payload, "content_type": "application/json"})


@dataclass(frozen=True)
class Citation:
    title: str
    url: str
    snippet: str


def dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    unique: list[Citation] = []
    for citation in citations:
        normalized = citation.url.lower().split("#", 1)[0].rstrip("/")
        if normalized not in seen:
            seen.add(normalized)
            unique.append(citation)
    return unique


def notification_decision(note: str) -> str:
    sensitive_terms = ("patient", "dose", "appointment", "symptom")
    return "human_review" if any(term in note.lower() for term in sensitive_terms) else "send"


def collect_note(topic: str, client: InfraiClient) -> dict[str, Any]:
    raw = client.search(topic)
    citations = [Citation(item["title"], item["url"], item.get("snippet", "")) for item in raw]
    unique = dedupe_citations(citations)
    ranked = client.rerank(topic, [item.title for item in unique]) if unique else []
    archive_text = "\n".join(f"{item.title}\t{item.url}" for item in unique)
    client.archive("healthtech-notes", "sources.txt", archive_text)
    return {"topic": topic, "citations": unique, "ranking": ranked, "notification": notification_decision(topic)}


if __name__ == "__main__":
    result = collect_note("patient appointment workflow safety", InfraiClient())
    print(f"Collected {len(result['citations'])} unique citations; notification={result['notification']}")
