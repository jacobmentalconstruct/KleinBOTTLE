# .microservice-library

A self-contained Python microservice toolbox for AI agents and local development.
Clone as `.microservice-library/` into any project and use it over CLI or MCP.

## What it is

56 focused microservices covering file scanning, chunking, vector search, RAG ingestion,
SQLite storage, Git operations, Tkinter UI widgets, and more — each decorated with
`@service_metadata` and `@service_endpoint` so agents can discover and call them
without reading source code.

All inference uses **local models via [ollama](https://ollama.com)** — no API keys,
no cloud calls.

Default models:
- **Embeddings**: `nomic-embed-text:latest` (swap to `mxbai-embed-large:latest` or `all-minilm:latest`)
- **Generation**: `llama3.1:8b` (swap to `deepseek-r1:14b` or any local model)

## Quick install (sidecar)

```bash
gh repo clone jacobmentalconstruct/.microservice-library .microservice-library
```

or

```bash
git clone https://github.com/jacobmentalconstruct/.microservice-library .microservice-library
```

## CLI

```bash
# list all services
python .microservice-library/cli.py list

# describe a service — full schema, inputs, outputs
python .microservice-library/cli.py describe ScoutMS

# call an endpoint directly
python .microservice-library/cli.py call ScoutMS scan_path root_path=/some/dir depth=3
python .microservice-library/cli.py call FingerprintScannerMS scan_project root_path=.
python .microservice-library/cli.py call SysInspector get_health
```

## MCP server

Wire into Claude Desktop or any MCP client:

```json
{
  "mcpServers": {
    "ms-toolbox": {
      "command": "python",
      "args": ["/absolute/path/to/.microservice-library/mcp_server.py"]
    }
  }
}
```

Every `@service_endpoint` is automatically registered as an MCP tool named
`ServiceName__method_name` with a proper input schema. No configuration needed.

```
pip install mcp
```

## Service index

See [codex.md](codex.md) for a full index of all 56 services with descriptions,
endpoint signatures, and tags — designed for agent lookup without reading source code.

## Structure

```
.microservice-library/
  services/                  ← service files + runtime
    microservice_std_lib.py  ← decorator contract (@service_metadata, @service_endpoint)
    base_service.py          ← base class
    _ScoutMS.py              ← one file per service
    _SearchEngineMS.py
    ...
  cli.py                     ← CLI entry point
  mcp_server.py              ← MCP stdio server
  codex.md                   ← full service index (agent-readable)
  pyproject.toml
  LICENSE.md
```

## Service layers

| Layer | Services | Notes |
|---|---|---|
| core | ScoutMS, FingerprintScannerMS, ContextPacker, TreeMapper, ... | Zero heavy deps |
| pipeline | IngestEngineMS, SemanticChunkerMS | ollama embeddings |
| meaning | SearchEngineMS, VectorFactoryMS | sqlite-vec + ollama |
| storage | CartridgeServiceMS | SQLite knowledge graph |
| db | DiffEngineMS, LexicalSearchMS, TaskVaultMS, ... | SQLite only |
| relation | NeuralGraphEngineMS, CodeGrapher, NetworkLayout | pygame optional |
| ui | TkinterAppShell, GitPilotMS, ExplorerWidget, ... | Tkinter |

## Requirements

```
Python 3.11+
ollama              # local LLM runtime (install from https://ollama.com)
requests            # HTTP to ollama API
numpy               # vector math (NumpyVectorStore backend)
```

Optional (unlock specific services):

```
sqlite-vec          # vector search in SearchEngineMS
pygame-ce           # NeuralGraphEngineMS renderer
faiss-cpu           # FAISS vector backend in VectorFactoryMS
chromadb            # Chroma vector backend in VectorFactoryMS
mcp                 # MCP server surface
```

## Integration with project-mapper

Pairs naturally with [.project-mapper](https://github.com/jacobmentalconstruct/.project-mapper).
project-mapper scans and snapshots your project; this library's RAG pipeline
(`IngestEngineMS` → `CartridgeServiceMS` → `SearchEngineMS`) can operate on
those snapshots to give agents semantic search over your codebase.

## License

MIT — see [LICENSE.md](LICENSE.md).
