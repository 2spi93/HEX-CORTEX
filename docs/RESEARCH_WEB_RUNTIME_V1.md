# Research Web Runtime v1

This rail connects HEX-CORTEX to a localhost-only SearXNG instance and refuses to declare the web-search adapter operational until a live query returns at least one valid cited URL.

## Safety contract

- SearXNG endpoint must use explicit `http://localhost:<port>/search` or loopback equivalents.
- Network execution requires the CLI `--network` flag.
- Queries, raw SearXNG responses, and raw page content are not persisted by the adapter.
- A successful HTTP response without citations remains blocked.
- The global runtime fact is not silently mutated. The live audit emits an evidence-backed override proposal.
- Crawl4AI remains packaged but is not required for the first search/citation gate.

## Start the packaged services on Windows

Validate the compose file and create a local ignored secret without starting containers:

```powershell
powershell -ExecutionPolicy Bypass `
  -File scripts\start_research_stack.ps1 `
  -ProjectRoot "$PWD"
```

Start the services after review:

```powershell
powershell -ExecutionPolicy Bypass `
  -File scripts\start_research_stack.ps1 `
  -ProjectRoot "$PWD" `
  -PullImages `
  -Start
```

The compose file binds SearXNG to `127.0.0.1:8888` and Crawl4AI to `127.0.0.1:11235`.

## Cold plan

```powershell
hexcortex-research audit `
  "HEX-CORTEX architecture" `
  --pretty
```

This performs no network call and returns `network_execution_not_authorized`.

## Live citation audit

```powershell
$Receipt = ".hex-cortex\research\searxng-live-audit.json"

hexcortex-research audit `
  "HEX-CORTEX architecture" `
  --endpoint http://127.0.0.1:8888/search `
  --max-items 5 `
  --timeout-seconds 15 `
  --network `
  --output "$Receipt" `
  --pretty
```

Operational evidence requires:

```text
status: operational
operational_ready: true
citation_count: >= 1
valid_citation_url_count == citation_count
runtime_fact_override.web_search_adapter_configured: true
```

Only after that evidence exists may the operator pass the fact into the filesystem-only wiring probe:

```powershell
hexcortex wiring-auto `
  --project-root . `
  --overrides-json '{"web_search_adapter_configured":true}'
```

## Direct cited search

```powershell
hexcortex-research search `
  "SearXNG JSON search API" `
  --network `
  --pretty
```

The result includes a ranked citation pack with title, URL, domain, source classification, ranking score, content hash, and bounded snippet.

## Stop services

```powershell
Push-Location deploy\research
docker compose down
Pop-Location
```
