# the-cell-seed.md

Extracted from `the-cell/src/microservices/`. Tkinter UI, app shell, and Backend
orchestration stripped. Three portable pieces remain: the service decorator system,
the memory tier, and the spawn-child concept (reimplementation note below).

---

## What's Useful Here

- **`microservice_std_lib.py`** — `@service_metadata` + `@service_endpoint` decorators.
  Makes any class AI-introspectable: an agent can call `extract_service_schema(cls)` and
  get a JSON description of every endpoint, its inputs/outputs, and side effects. Zero deps.
- **`_CognitiveMemoryMS.py`** — Short-term memory → long-term flush. JSONL persistence,
  pydantic `MemoryEntry`, configurable summarizer + ingestor callbacks. Dep: `pydantic`.
- **`spawn_child` concept** — in the-cell this emits a signal to open a Tkinter window.
  The useful idea: bundle the parent's last N context entries + artifact and pass them to a
  new agent instance. Reimplement without the signal bus (see note below).

---

## Module: microservice_std_lib.py

Pure Python, no external deps. Decorators that tag classes and methods so a
coordinator or agent can discover what services exist and how to call them.

```python
"""
LIBRARY: Microservice Standard Lib v2.1.0
ROLE: Provides decorators for tagging Python classes as AI-discoverable services.
"""
import functools
import inspect
from typing import Dict, List, Any, Optional, Type


def service_metadata(
    name: str,
    version: str,
    description: str,
    tags: List[str],
    capabilities: Optional[List[str]] = None,
    internal_dependencies: Optional[List[str]] = None,
    external_dependencies: Optional[List[str]] = None,
    side_effects: Optional[List[str]] = None,
    **_ignored_kwargs,          # forward-compat: ignores unknown keys
):
    """Class decorator. Labels a service class with catalog metadata."""
    def decorator(cls):
        cls._is_microservice = True
        cls._service_info = {
            "name": name, "version": version, "description": description,
            "tags": tags, "capabilities": capabilities or [],
            "internal_dependencies": internal_dependencies or [],
            "external_dependencies": external_dependencies or [],
            "side_effects": side_effects or [],
        }
        return cls
    return decorator


def service_endpoint(
    inputs: Dict[str, str],
    outputs: Dict[str, str],
    description: str,
    tags: Optional[List[str]] = None,
    side_effects: Optional[List[str]] = None,
    mode: str = "sync",         # "sync" | "async" (informational)
):
    """Method decorator. Defines a callable socket for coordinators/agents."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._is_endpoint = True
        wrapper._endpoint_info = {
            "name": func.__name__, "inputs": inputs, "outputs": outputs,
            "description": description, "tags": tags or [],
            "side_effects": side_effects or [], "mode": mode,
        }
        return wrapper
    return decorator


def extract_service_schema(service_cls: Type) -> Dict[str, Any]:
    """Returns JSON-serializable schema of a service: metadata + all endpoints.
    This is what an agent uses to 'read the manual' for a service."""
    if not getattr(service_cls, "_is_microservice", False):
        raise ValueError(f"{service_cls.__name__} is not decorated with @service_metadata")
    schema = {"meta": getattr(service_cls, "_service_info", {}), "endpoints": []}
    for _, method in inspect.getmembers(service_cls, predicate=inspect.isfunction):
        if getattr(method, "_endpoint_info", None):
            schema["endpoints"].append(method._endpoint_info)
    return schema
```

---

## Module: base_service.py

```python
import logging
from typing import Dict, Any

class BaseService:
    """Standard parent class. Provides consistent logging and identity."""
    def __init__(self, name: str):
        self._service_info = {"name": name, "id": name.lower().replace(" ", "_")}
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
        self.logger = logging.getLogger(name)

    def log_info(self, message: str):    self.logger.info(message)
    def log_error(self, message: str):   self.logger.error(message)
    def log_warning(self, message: str): self.logger.warning(message)
```

---

## Module: _CognitiveMemoryMS.py

Dep: `pydantic`. The "hippocampus": short-term working memory → long-term flush.
Configurable summarizer and ingestor callbacks — no inference hardcoded.

```python
"""
SERVICE_NAME: _CognitiveMemoryMS
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: pydantic
"""
import datetime, json, logging, uuid, os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from .microservice_std_lib import service_metadata, service_endpoint
from .base_service import BaseService

DEFAULT_MEMORY_FILE = Path("working_memory.jsonl")
FLUSH_THRESHOLD = 5   # flush to long-term after N entries

class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


@service_metadata(
    name="CognitiveMemory", version="1.0.0",
    description="Manages Short-Term (Working) Memory and orchestrates flushing to Long-Term Memory.",
    tags=["memory", "history", "context"],
    internal_dependencies=["base_service", "microservice_std_lib"],
    external_dependencies=["pydantic"],
)
class CognitiveMemoryMS(BaseService):
    """Short-term working memory with configurable long-term flush."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("CognitiveMemory")
        self.config = config or {}
        self.file_path = Path(self.config.get("persistence_path", DEFAULT_MEMORY_FILE))
        self.summarizer = self.config.get("summarizer_func")   # Callable[[str], str]
        self.ingestor   = self.config.get("long_term_ingest_func")  # Callable[[str, dict], None]
        self.working_memory: List[MemoryEntry] = []
        self._load_working_memory()

    def add_entry(self, role: str, content: str, metadata: Dict = None) -> MemoryEntry:
        """Add item to working memory and persist to JSONL."""
        entry = MemoryEntry(role=role, content=content, metadata=metadata or {})
        self.working_memory.append(entry)
        self._append_to_file(entry)
        return entry

    def get_context(self, limit: int = 10) -> str:
        """Most recent N entries formatted for LLM injection: 'ROLE: content'"""
        return "\n".join(f"{e.role.upper()}: {e.content}" for e in self.working_memory[-limit:])

    def get_full_history(self) -> List[Dict]:
        return [e.dict() for e in self.working_memory]

    def commit_turn(self):
        """Signal turn complete. Flushes to long-term if FLUSH_THRESHOLD reached."""
        if len(self.working_memory) >= FLUSH_THRESHOLD:
            self._flush_to_long_term()

    def _flush_to_long_term(self):
        """Summarize working memory → ingest → rotate log."""
        if not self.summarizer or not self.ingestor:
            return
        full_text = "\n".join(f"{e.role}: {e.content}" for e in self.working_memory)
        summary = self.summarizer(full_text)
        meta = {"source": "cognitive_memory_flush",
                "date": datetime.datetime.utcnow().isoformat(),
                "original_entry_count": len(self.working_memory)}
        self.ingestor(summary, meta)
        self.working_memory.clear()
        self._rotate_log_file()

    def _load_working_memory(self):
        if not self.file_path.exists():
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.working_memory.append(MemoryEntry.parse_raw(line))

    def _append_to_file(self, entry: MemoryEntry):
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(entry.json() + "\n")

    def _rotate_log_file(self):
        if self.file_path.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.file_path.rename(self.file_path.with_name(f"memory_archive_{ts}.jsonl"))
```

**Usage:**

```python
mem = CognitiveMemoryMS({
    "persistence_path": "ws-agent-1/memory.jsonl",
    "summarizer_func": lambda text: llm_call(f"Summarize: {text}"),
    "long_term_ingest_func": lambda summary, meta: vector_store.add(summary, meta),
})

mem.add_entry("user", "What is the failing test?")
mem.add_entry("assistant", "test_contract.py line 42 assertion error")
context = mem.get_context(limit=5)  # → "USER: What is...\nASSISTANT: test_contract..."
mem.commit_turn()  # flushes if >= FLUSH_THRESHOLD
```

---

## spawn_child — Reimplementation Note

In the-cell, `spawn_child()` emits `SIGNAL_SPAWN_REQUESTED` to the Tkinter AppShell
which opens a new GUI window. The portable concept underneath:

```python
def spawn_child(memory: CognitiveMemoryMS, parent_artifact: dict) -> dict:
    """Bundle parent context for handoff to a new agent instance.
    
    Returns a child_payload dict the caller passes to bootstrap_workspace()
    or injects as inherited context into the new agent's first prompt.
    """
    return {
        "source_artifact": parent_artifact,
        "inherited_context": memory.get_context(limit=10),
        "spawn_timestamp": datetime.datetime.utcnow().isoformat(),
    }
```

In a swarm: call `spawn_child()`, then `bootstrap_workspace()` for the child,
write `child_payload` as `files/inherited-context.json` in the child workspace,
and reference it via `$step_id` in the child's first workflow step.
