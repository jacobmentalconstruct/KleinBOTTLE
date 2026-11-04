# Microservice Codex — Index
Generated 2026-11-01 · 57 services · 161 endpoints · 9 layers

---

## Quick reference by layer

### CORE (25 services)

**ArchiveBotMS** `v1.1.0` — Creates timestamped .tar.gz backups of directory trees.
  tags: `utility` `backup` `filesystem`
  - `create_backup(source_path: str, output_dir: str, extra_exclusions: List[str], use_default_exclusions: bool) → {archive_path: str, file_count: int}` — Compresses a directory into a .tar.gz archive.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_ArchiveBotMS.py`

**AuthMS** `v1.0.0` — Manages user authentication and session tokens.
  tags: `auth` `security` `crypto`
  - `login(username: str, password: str) → {token: Optional[str]}` — Attempts to log in and returns a signed session token.
  - `validate_session(token: str) → {is_valid: bool}` — Checks whether a token is valid and not expired.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_AuthMS.py`

**CodeFormatterMS** `v1.0.0` — The Architect: Intelligent whitespace normalization and structural repair engine.
  tags: `formatting` `code` `utility`
  - `normalize_code(content: str, use_tabs: bool, spaces: int) → {normalized: str, patch: Dict}` — Takes raw code and returns the normalized version plus a JSON patch of changes.
  - `format_file(file_path: str, use_tabs: bool, spaces: int) → {status: str, changes: int}` — Reads a file, normalizes it, and overwrites it if changes are needed.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_CodeFormatterMS.py`

**CodeJanitorMS** `v2.2.0` — Fast version: Skips backup, high verbosity.
  tags: `maintenance`
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_CodeJanitorMS.py`

**CognitiveMemoryMS** `v1.0.0` — Manages Short-Term (Working) Memory and orchestrates flushing to Long-Term Memory.  · deps: pydantic
  tags: `memory` `history` `context`
  - `add_entry(role: str, content: str, metadata: Dict) → {entry: MemoryEntry}` — Adds an item to working memory and persists it.
  - `get_context(limit: int) → {context: str}` — Returns the most recent conversation history formatted for an LLM.
  - `commit_turn()` — Signals that a turn is complete; checks if memory flush is needed.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_CognitiveMemoryMS.py`

**ContentExtractorMS** `v1.0.0` — The Decoder: A specialist service for extracting clean text from complex formats like PDF and HTML.  · deps: beautifulsoup4, bs4, pypdf
  tags: `utility` `extraction` `nlp`
  - `get_health() → {status: str, pdf_support: bool, html_support: bool}` — Health check to verify which extraction backends are installed.
  - `extract_text(blob: bytes, mime_type: str) → {text: str}` — Unified entry point for text extraction. Routes to the correct parser based on mime_type.
  → `library\microservices\core\_ContentExtractorMS.py`

**ContextAggregatorMS** `v1.0.0` — Flattens a project folder into a single readable text file.
  tags: `filesystem` `context` `compilation`
  - `aggregate(root_path: str, output_file: str, extra_exclusions: Set[str], use_default_exclusions: bool) → {file_count: int}` — Aggregates project files into a single text dump.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_ContextAggregatorMS.py`

**ContextPackerMS** `v1.0.0` — Flattens a directory of source code into a single text file (useful for LLM context stuffing).
  tags: `filesystem` `export` `utility`
  - `pack_directory(root_path: str, output_filename: str, additional_excludes: Set[str]) → {output_path: str, file_count: int}` — Packs directory contents into a single text file.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_ContextPackerMS.py`

**EnvironmentManagerMS** `v1.0.0` — Manages Python runtime resolution and process execution.
  tags: `runtime` `python` `venv` `process`
  - `resolve_python(project_path: str, config_override: str) → {interpreter: str, source: str}` — Determines the absolute path to the Python interpreter for a given project.
  - `launch_script(project_path: str, script_rel_path: str, env_vars: Dict) → {pid: int}` — Launches a python script in a subprocess using the resolved environment.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_EnvironmentManagerMS.py`

**FingerprintScannerMS** `v1.0.0` — Scans a directory tree and generates a deterministic SHA-256 fingerprint.
  tags: `scanning` `integrity` `hashing`
  - `scan_project(root_path: str) → {state: Dict[str, Any]}` — Scans the project and returns a comprehensive state object (hashes + Merkle root).
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_FingerprintScannerMS.py`

**HeuristicSumMS** `v1.0.0` — Generates quick summaries of code/text files using regex heuristics (No AI).
  tags: `parsing` `summary` `heuristics`
  - `summarize(text: str, filename: str, max_chars: int) → {summary: str}` — Generates a summary string from the provided text.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_HeuristicSumMS.py`

**IntakeServiceMS** `v1.3.0` — The Vacuum: Handles two-phase ingestion by scanning sources and processing selected paths into the cartridge.  · deps: bs4, requests
  tags: `ingestion` `scanner` `vfs`
  - `get_health() → {status: str, uptime: float, cartridge_connected: bool}` — Standardized health check to verify service status and cartridge connectivity.
  - `scan_path(root_path: str, web_depth: int) → {tree: dict}` — Scans a local directory or URL to build a hierarchical tree structure of available files.
  - `ingest_selected(file_list: list, root_path: str) → {stats: dict}` — Processes a specific list of files into the cartridge storage, handling text extraction and VFS indexing.
  → `library\microservices\core\_IntakeServiceMS.py`

**IsoProcessMS** `v1.0.0` — Spawns isolated processes with real-time logging feedback.
  tags: `process` `isolation` `safety`
  - `execute(payload: Any, config: Dict) → {result: Any}` — Executes a payload in an isolated child process.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_IsoProcessMS.py`

**LibrarianMS** `v3.0.0` — Uses a swarm of local AI models to generate a 'Card Catalogue' of the microservice library.  · deps: requests
  tags: `documentation` `ai` `catalog` `swarm`
  - `generate_catalog(output_file: str) → {path: str, service_count: int}` — Unleashes the AI swarm to generate a catalog.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_LibrarianMS.py`

**LibrarianMS** `v3.0.0` — Uses a swarm of local AI models to generate a 'Card Catalogue'.  · deps: requests
  tags: `documentation` `ai` `catalog` `swarm`
  - `generate_catalog(output_file: str) → {path: str, service_count: int}` — Unleashes the AI swarm to generate a catalog.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_LibrarianServiceMS.py`

**NeuralServiceMS** `v1.0.0` — The Brain Interface: Orchestrates local AI operations via Ollama.  · deps: requests
  tags: `ai` `neural` `inference` `ollama`
  - `update_models(fast_model: str, smart_model: str, embed_model: str) → {status: str}` — Updates the active model configurations on the fly.
  - `get_available_models() → {models: List[str]}` — Fetches a list of available models from the local Ollama instance.
  - `check_connection() → {is_alive: bool}` — Pings Ollama to verify connectivity.
  - `get_embedding(text: str) → {embedding: list}` — Generates a vector embedding for the provided text.
  - `request_inference(prompt: str, tier: str, format_json: bool) → {response: str}` — Requests synchronous text generation from a local LLM.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_NeuralServiceMS.py`

**ProjectForgeMS** `v1.0.0` — Scaffolding engine for creating new microservice projects or Python apps.
  tags: `scaffolding` `generator` `filesystem`
  - `forge_project(parent_path: str, project_name: str, dependencies: List[str], type: str) → {path: str, status: str}` — Creates a new standardized Python project with the given specifications.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_ProjectForgeMS.py`

**PromptOptimizerMS** `v1.0.0` — Uses an LLM to refine prompts or generate variations.
  tags: `llm` `prompt-engineering` `optimization`
  - `refine_prompt(draft_prompt: str, feedback: str) → {refined_prompt: str}` — Rewrites a prompt based on feedback.
  - `generate_variations(draft_prompt: str, num_variations: int, context_data: Dict) → {variations: List[str]}` — Generates multiple versions of a prompt for testing.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_PromptOptimizerMS.py`

**PromptVaultMS** `v1.0.0` — A persistent SQLite store for managing, versioning, and rendering AI prompts.  · deps: jinja2, pydantic
  tags: `prompt` `database` `versioning` `jinja`
  - `create_template(slug: str, title: str, content: str, author: str, tags: List[str]) → {template: Dict}` — Creates a new prompt template with an initial version.
  - `add_version(slug: str, content: str, author: str) → {template: Dict}` — Adds a new version to an existing template.
  - `get_template(slug: str) → {template: Optional[PromptTemplate]}` — Retrieves a full template with all history.
  - `render(slug: str, context: Dict) → {rendered_text: str}` — Fetches the latest version and renders it with Jinja2.
  - `list_slugs() → {slugs: List[str]}` — Lists all available prompt slugs.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_PromptVaultMS.py`

**RegexWeaverMS** `v1.0.0` — Fault-tolerant dependency extractor using Regex.
  tags: `parsing` `dependencies` `regex`
  - `extract_dependencies(content: str, language: str) → {dependencies: List[str]}` — Scans code content for import statements.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_RegexWeaverMS.py`

**ScoutMS** `v1.0.0` — The Scout: A depth-aware utility for recursively walking local file systems or crawling websites.  · deps: bs4, requests
  tags: `utility` `scanner` `crawler`
  - `scan_directory(root_path: str, web_depth: int) → {tree: dict}` — Main entry point to perform a recursive scan of a directory or a web crawl.
  - `flatten_tree(tree_node: dict) → {file_list: list}` — Flattens a hierarchical tree node structure into a simple list of paths.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_ScoutMS.py`

**ServiceRegistryMS** `v1.0.0` — Scans a library of Python microservices and generates standardized JSON Service Tokens.
  tags: `introspection` `registry` `parsing`
  - `scan(save_to: str) → {registry: List[Dict]}` — Scans the file system for microservices and builds a registry.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_ServiceRegistryMS.py`

**SysInspectorMS** `v1.0.0` — Gathers hardware and environment statistics via shell commands.
  tags: `system` `audit` `hardware`
  - `generate_report() → {report: str}` — Runs the full audit and returns a formatted string report.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_SysInspectorMS.py`

**TreeMapperMS** `v1.0.0` — Generates ASCII-art style directory maps of the file system.
  tags: `filesystem` `map` `visualization`
  - `generate_tree(root_path: str, additional_exclusions: Set[str], use_default_exclusions: bool) → {tree_map: str}` — Generates an ASCII tree map of the directory.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_TreeMapperMS.py`

**WebScraperMS** `v1.0.0` — Fetches URLs and extracts main content using Readability (stripping ads/nav).  · deps: httpx, readability
  tags: `scraper` `web` `readability`
  - `scrape(url: str) → {data: Dict[str, Any]}` — Fetches and cleans a URL.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\core\_WebScraperMS.py`


### DB (5 services)

**DiffEngineMS** `v1.0.0` — Implements hybrid versioning (Head + Diff History) for file content.
  tags: `version-control` `diff` `db`
  - `update_file(path: str, new_content: str, author: str) → {status: str, file_id: str}` — Updates a file, creating a diff history entry and updating the head state.
  - `get_head(path: str) → {content: Optional[str]}` — Fast retrieval of current content.
  - `get_history(path: str) → {history: List[Dict]}` — Retrieves the full evolution history of a file.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\db\_DiffEngineMS.py`

**LexicalSearchMS** `v1.0.0` — Lightweight BM25 keyword search using SQLite FTS5 (No AI required).
  tags: `search` `index` `sqlite`
  - `add_document(doc_id: str, text: str, metadata: Dict)` — Adds or updates a document in the FTS index.
  - `search(query: str, top_k: int) → {results: List[Dict]}` — Performs a BM25 ranked keyword search.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\db\_LexicalSearchMS.py`

**RoleManagerMS** `v1.0.0` — Manages Agent Personas (Roles), including System Prompts and Memory Settings.  · deps: pydantic
  tags: `roles` `personas` `db`
  - `create_role(name: str, system_prompt: str, description: str, kbs: List[str]) → {role: Dict}` — Creates a new Agent Persona.
  - `get_role(name_or_id: str) → {role: Optional[RoleModel]}` — Retrieves a role by Name or ID.
  - `list_roles() → {roles: List[Dict]}` — Lists all available roles.
  - `delete_role(name: str)` — Deletes a role by name.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\db\_RoleManagerMS.py`

**SandboxManagerMS** `v1.0.0` — The Safety Harness: Manages a 'Sandbox' mirror of a 'Live' project for safe experimentation.
  tags: `filesystem` `safety` `versioning`
  - `init_sandbox(force: bool)` — Creates or resets the sandbox by mirroring the live project.
  - `reset_sandbox()` — Discards all sandbox changes and re-syncs from live.
  - `get_diff() → {diff: Dict[str, List[str]]}` — Compares Sandbox vs Live. Returns added, modified, and deleted files.
  - `promote_changes() → {added: int, modified: int, deleted: int}` — Applies changes from Sandbox to Live.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\db\_SandboxManagerMS.py`

**TasklistVaultMS** `v1.0.0` — Persistent SQLite engine for hierarchical task management.
  tags: `tasks` `db` `project-management`
  - `create_list(name: str) → {list_id: str}` — Creates a new task list and returns its ID.
  - `get_lists() → {lists: List[Dict]}` — Returns metadata for all task lists.
  - `add_task(list_id: str, content: str, parent_id: Optional[str]) → {task_id: str}` — Adds a task (or sub-task) to a list.
  - `update_task(task_id: str, content: str, status: str, result: str)` — Updates a task's details.
  - `get_full_tree(list_id: str) → {tree: Dict[str, Any]}` — Fetches a list and reconstructs the full hierarchy of tasks.
  - `delete_list(list_id: str)` — Deletes a task list and all its tasks.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\db\_TasklistVaultMS.py`


### MEANING (2 services)

**SearchEngineMS** `v1.0.0` — The Oracle: Performs Hybrid Search (Vector Similarity + Keyword Matching) on SQLite databases.  · deps: requests, sqlite_vec
  tags: `search` `vector` `hybrid` `rag`
  - `search(db_path: str, query: str, limit: int) → {results: List[Dict]}` — Main entry point. Returns a list of results sorted by relevance (RRF).
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\meaning\_SearchEngineMS.py`

**VectorFactoryMS** `v1.0.0` — Factory for creating VectorStore instances (FAISS, Chroma).  · deps: chromadb, faiss, numpy
  tags: `vector` `factory` `db`
  - `create(backend: str, config: Dict) → {store: VectorStore}` — Creates and returns a configured VectorStore instance.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\meaning\_VectorFactoryMS.py`


### OBSERVABILITY (1 services)

**TelemetryServiceMS** `v1.0.0` — The Nervous System: Watches the thread-safe LogQueue and updates GUI components with real-time status.
  tags: `utility` `logging` `telemetry`
  - `get_health() → {status: str, uptime: float, queue_depth: int}` — Standardized health check to verify the operational state of the telemetry pipeline.
  - `start()` — Initiates the telemetry service and begins the asynchronous GUI log-polling loop.
  - `ping() → {alive: bool, heartbeat: int}` — Verifies that the GUI polling loop is actively processing the log queue.
  → `library\microservices\observability\_TelemetryServiceMS.py`


### PIPELINE (2 services)

**IngestEngineMS** `v1.0.0` — Reads files, chunks text, fetches embeddings, and weaves graph edges.  · deps: requests
  tags: `ingest` `rag` `parsing` `embedding`
  - `process_files(file_paths: List[str], model_name: str) → {status: IngestStatus}` — Processes a list of files, ingesting them into the knowledge graph.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\pipeline\_IngestEngineMS.py`

**SemanticChunkerMS** `v1.0.0` — The Surgeon: Intelligent Code Splitter that parses source code into logical semantic units (Classes, Functions) using AST.
  tags: `utility` `nlp` `parser`
  - `chunk_file(content: str, filename: str) → {chunks: List[Dict]}` — Main entry point to split a file into semantic chunks based on its extension and content.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\pipeline\_SemanticChunkerMS.py`


### RELATION (4 services)

**CodeGrapherMS** `v1.0.0` — Parses Python code to extract symbols (nodes) and call relationships (edges).
  tags: `parsing` `graph` `analysis`
  - `scan_directory(root_path: str) → {graph_data: Dict[str, Any]}` — Recursively scans a directory for .py files and builds the graph.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\relation\_CodeGrapherMS.py`

**NetworkLayoutMS** `v1.0.0` — Calculates visual (x,y) coordinates for graph nodes using NetworkX.  · deps: networkx
  tags: `graph` `layout` `visualization`
  - `calculate_layout(nodes: List[str], edges: List[Tuple], algorithm: str) → {positions: Dict[str, Tuple]}` — Computes (x, y) coordinates for the given graph nodes and edges.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\relation\_NetworkLayoutMS.py`

**NeuralGraphEngineMS** `v1.1.0` — The Cartographer: A physics-driven rendering engine for visualizing complex neural relationships in a 2D force-directed graph.  · deps: pygame
  tags: `visualization` `graph` `pygame`
  - `get_health() → {status: str, uptime: float, nodes: int, settled: bool}` — Standardized health check to verify the operational state of the graph renderer.
  - `set_data(nodes: list, links: list)` — Injects new node and edge data into the engine and wakes up the physics simulation.
  - `step_physics() → {settled: bool}` — Performs one iteration of the force-directed physics calculation.
  - `get_image_bytes() → {raw_data: bytes}` — Renders the current frame to a byte buffer for display in UI components.
  → `library\microservices\relation\_NeuralGraphEngineMS.py`

**RefineryServiceMS** `v1.1.0` — The Night Shift: Processes 'RAW' files into semantic chunks and weaves them into a knowledge graph.
  tags: `processing` `refinery` `graph` `RAG`
  - `get_health() → {status: str, uptime: float, cartridge_health: str}` — Standardized health check to verify the operational state of the Refinery service.
  - `process_pending(batch_size: int) → {processed_count: int}` — Polls the database for files with 'RAW' status and processes them into chunks and graph nodes.
  → `library\microservices\relation\_RefineryServiceMS.py`


### STORAGE (1 services)

**CartridgeServiceMS** `v1.1.0` — The Source of Truth. Manages the Unified Neural Cartridge Format (UNCF v1.0).  · deps: sqlite_vec
  tags: `storage` `database` `RAG`
  - `get_status_flags() → {ingest_complete: bool, refine_complete: bool, cartridge_health: str}` — Returns key manifest status flags (ingest/refine status and health) in a single call.
  - `get_directory_tree(root: str) → {tree: dict}` — Builds a nested directory tree structure for UI navigation or context mapping.
  - `search_embeddings(query_vector: list, limit: int) → {results: list}` — Performs semantic vector search using sqlite-vec against the cartridge chunks.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\storage\_CartridgeServiceMS.py`


### STRUCTURE (4 services)

**ChunkingRouterMS** `v1.1.0` — The Dispatcher: Routes files to specialized chunkers based on extension (AST for Python, Recursive for Prose).
  tags: `orchestration` `chunking` `nlp`
  - `chunk_file(text: str, filename: str, max_size: int, overlap: int) → {chunks: list}` — Routes text to the appropriate specialist. Returns a list of CodeChunk objects or raw strings.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\structure\_ChunkingRouterMS.py`

**CodeChunkerMS** `v1.0.0` — Splits code into semantic blocks (Classes, Functions) using indentation and regex heuristics.
  tags: `parsing` `chunking` `code`
  - `chunk_file(file_path: str, max_chars: int) → {chunks: List[Dict]}` — Reads a file and breaks it into logical blocks based on indentation.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\structure\_CodeChunkerMS.py`

**PythonChunkerMS** `v1.2.0` — The Python Surgeon: Specialist in Abstract Syntax Tree (AST) parsing for Python source code.
  tags: `chunking` `python` `ast`
  - `get_health() → {status: str, uptime: float, specialty: str}` — Standardized health check for the Python specialist service.
  - `chunk(content: str) → {chunks: List[Dict]}` — Primary entry point for high-fidelity Python-specific AST chunking.
  → `library\microservices\structure\_PythonChunkerMS.py`

**TextChunkerMS** `v1.0.0` — Splits text into chunks using various strategies (chars, lines).
  tags: `chunking` `nlp` `rag`
  - `chunk_by_chars(text: str, chunk_size: int, chunk_overlap: int) → {chunks: List[str]}` — Standard sliding window split by character count.
  - `chunk_by_lines(text: str, max_lines: int, max_chars: int) → {chunks: List[Dict]}` — Line-preserving chunker, best for code.
  - `chunk_by_paragraphs(text: str, target_chars: int, overlap_paragraphs: int) → {chunks: List[str]}` — Prose-aware paragraph chunking with overlap between windows.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\structure\_TextChunkerMS.py`


### UI (13 services)

**ChalkBoardMS** `v2.0.1` — Integrated HTML5/CSS3 Digital Signage Engine  · deps: webview
  tags: `ui` `webview` `obs`
  - `update_sign(text: str, theme: str)` — Updates the embedded HTML via JS injection.
  - `trigger_effect(effect: str)` — Triggers CSS animations like 'shake'.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_ChalkBoardMS.py`

**ExplorerWidgetMS** `v1.0.0` — A standalone file system tree viewer widget.  · deps: ttk
  tags: `ui` `filesystem` `widget`
  - `refresh_tree()` — Rescans the directory and refreshes the tree view.
  - `get_selected_paths() → {selected_paths: List[str]}` — Returns a list of currently checked folder paths.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_ExplorerWidgetMS.py`

**GitPilotMS** `v1.0.0` — A Tkinter GUI panel for Git operations (Stage, Commit, Push, Pull).  · deps: git
  tags: `ui` `git` `version-control` `widget`
  - `set_repo(path: Path)` — Sets the active repository path and refreshes status.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_GitPilotMS.py`

**LogViewMS** `v1.0.0` — A thread-safe log viewer widget for Tkinter.
  tags: `ui` `logs` `widget`
  - `clear()` — Clears the log console.
  - `save()` — Opens a dialog to save logs to a file.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_LogViewMS.py`

**MonacoHostMS** `v1.1.0` — Hosts an embedded Monaco Editor instance using PyWebview.  · deps: webview
  tags: `ui` `editor` `webview`
  - `launch(title: str, width: int, height: int)` — Launches the editor window. Blocking call.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_MonacoHostMS.py`

**NeuralGraphViewerMS** `v1.0.0` — The Lens: A Tkinter-based UI component that hosts the neural graph engine and provides search/highlighting overlays.  · deps: PIL
  tags: `ui` `visualization` `tkinter`
  - `run_search(event: any)` — Triggers a neural search based on the entry field and highlights resulting nodes in the viewer.
  - `load_from_db(db_path: str)` — Loads graph nodes and edges from a Cartridge database and triggers the physics engine.
  - `animate()` — The primary heartbeat loop that orchestrates frame-by-frame physics steps and UI blitting.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_NeuralGraphViewerMS.py`

**SpinnerThingyMaBobberMS** `v1.0.0` — Interactive visual spinner widget for OBS/UI overlays.
  tags: `ui` `widget` `visuals`
  - `launch()` — Launches the GUI main loop.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_SpinnerThingyMaBobberMS.py`

**ThoughtStreamMS** `v1.0.0` — A UI widget for displaying a stream of AI thoughts/logs.
  tags: `ui` `stream` `logs` `widget`
  - `add_thought_bubble(filename: str, chunk_id: int, content: str, vector_preview: List[float], color: str)` — Adds a new thought bubble to the visual stream.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_ThoughtStreamMS.py`

**TkinterAppShellMS** `v2.0.0` — The Application Container. Manages the root window, main loop, and global layout.
  tags: `ui` `core` `lifecycle`
  - `launch()` — Starts the GUI Main Loop.
  - `get_main_container() → {container: tk.Frame}` — Returns the main content area for other services to dock into.
  - `shutdown()` — Gracefully shuts down the application.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_TkinterAppShellMS.py`

**TkinterSmartExplorerMS** `v1.0.0` — A hierarchical tree viewer capable of displaying file systems or JSON data structures.
  tags: `ui` `widget` `explorer`
  - `load_data(data: Dict)` — Populates the tree view with a nested dictionary structure (Standard 'Node' format).
  - `get_ui_schema() → {schema: Dict}` — Returns a headless UI schema for this explorer widget.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_TkinterSmartExplorerMS.py`

**TkinterThemeManagerMS** `v1.2.0` — Centralized modern Tkinter theme tokens and icon maps used by UI microservices.
  tags: `ui` `config` `theme`
  - `get_theme() → {theme: dict}` — Return active theme token dictionary.
  - `get_node_icons() → {icons: dict}` — Return active node icon map.
  - `get_legacy_aliases() → {aliases: dict}` — Return legacy theme alias map for compatibility with older Tkinter components.
  - `update_key(key: str, value: Any) → {ok: bool}` — Update a single theme token at runtime.
  - `update_icon(node_type: str, icon: str) → {ok: bool}` — Update or add icon mapping for a node type.
  - `get_health() → {status: str, uptime: float, token_count: int, icon_count: int}` — Standardized health check for theme manager state.
  → `library\microservices\ui\_TkinterThemeManagerMS.py`

**TkinterUniButtonMS** `v1.0.0` — A unified button group (Left/Right/Link) where linking merges the actions.
  tags: `ui` `widget` `button`
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_TkinterUniButtonMS.py`

**WorkbenchLayoutMS** `v1.0.0` — A declarative layout engine that builds resizable, nested Workbenches (Rows/Cols) from a config dictionary.
  tags: `ui` `layout` `framework`
  - `build_from_manifest(manifest: Dict)` — Builds the UI structure based on the provided dictionary layout.
  - `get_health() → {status: str, uptime: float}` — Standardized health check for service status.
  → `library\microservices\ui\_WorkbenchLayoutMS.py`

