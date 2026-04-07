import httpx, json

key = "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"

r = httpx.post("https://api.tavily.com/search", json={
    "api_key": key,
    "query": "pune weather",
    "search_depth": "basic",
    "include_answer": True,
    "max_results": 3
})

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:500])