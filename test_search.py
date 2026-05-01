import httpx, json, os

key = os.getenv("TAVILY_KEY", "")
if not key:
    raise RuntimeError("Set TAVILY_KEY in environment before running this script.")

r = httpx.post("https://api.tavily.com/search", json={
    "api_key": key,
    "query": "pune weather",
    "search_depth": "basic",
    "include_answer": True,
    "max_results": 3
})

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:500])