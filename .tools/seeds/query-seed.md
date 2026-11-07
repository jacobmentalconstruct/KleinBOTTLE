# query-seed.md

Extracted from the semantic query layer of a prior IT documentation project.
Source: abstracted from a snapshot-backed NL query system. All brand/project
references have been removed. This document is a seed for re-implementing the
same routing and measurement-translation approach in a new context.

---

## What This Seeds

Three reusable capabilities:

1. **NL → category router** — classifies a natural-language question into one of
   12 IT documentation categories using keyword matching (zero deps) or embedding
   similarity (sentence-transformers). Inject any router callable.
2. **NL → measurement contract** — translates a question into a structured
   `{operation, grain, predicate, cooccurrence, scope}` contract via a local Ollama
   model. Deterministic, schema-constrained, loopback-only.
3. **Snapshot term index + answer engine** — indexes a structured knowledge-base
   snapshot and answers NL questions with provenance. Coupling point: data must
   conform to the snapshot schema below.

---

## Snapshot Schema (Data Contract)

`term_index.build()` and `answer()` both consume a dict of this shape.
If your data source produces a different format, adapt the `build()` call.

```python
snapshot = {
    "metadata": {
        "kind": "live_snapshot",          # or "synthetic_sample"
        "captured_at": "2026-10-25T...",  # ISO timestamp
        "base_url": "https://..."         # source system URL
    },
    "companies": [
        {
            "list_record": {
                "id": 1,
                "name": "Acme Corp",
                "state": "TX",            # 2-letter state code (optional)
                "region": "Southwest",    # derived from state (optional)
                "archived": 0
            },
            "assets": [
                {
                    "list_record": {
                        "id": 101,
                        "name": "DC01",
                        "asset_type": "Servers & vms",
                        "archived": 0,
                        "fields": [
                            {"label": "Operating System", "value": "Windows Server 2022"},
                            {"label": "Host", "value": "Rack-A"},
                            {"label": "Notes", "value": "..."},   # free-text, not indexed
                        ]
                    }
                }
            ]
        }
    ]
}
```

The SQL-level schema (for a SQLite-backed implementation) is declared in
`schema.json` below.

---

## Pattern Vocabulary

12 routing targets. Used as embedding anchor descriptions in `EmbeddingRouter`
and as the key set for the keyword router. Add, remove, or rename patterns here
and both routers adapt automatically.

```python
PATTERNS = {
    "client_overview":  "full overview of a client company, all their assets and summary",
    "contacts_people":  "contacts, people, staff, employees at a client, who to call",
    "devices":          "workstations, laptops, desktops, computers, mobile devices, phones at a client",
    "servers":          "servers, virtual machines, VMs at a client",
    "network":          "network devices, routers, switches, firewalls, VLANs, subnets, IP addresses",
    "applications":     "applications, software, SaaS subscriptions, licenses at a client",
    "tech_stack":       "technology stack, programming languages, frameworks, databases, runtime",
    "locations":        "office locations, sites, addresses of a client",
    "vendors":          "vendors, suppliers, third-party relationships of a client",
    "contracts":        "contracts, SLAs, agreements, renewals",
    "certificates":     "SSL certificates, domains, expiry dates",
    "cross_client":     "which clients have a specific technology, OS, vendor, or expiring asset",
}
```

---

## Configuration: semantic-mappings.json

Maps asset type names (tenant/project vocabulary) to the 12 pattern categories.
This file is the only place where layout names live — runtime code holds no
tenant vocabulary. Load via env var `SEMANTIC_MAPPINGS=<path>` or default path.

**Format:**

```json
{
  "about": "Per-project semantic mappings for the query layer. ...",
  "asset_type_categories": [
    {
      "asset_type": "Servers & vms",
      "category": "servers",
      "source": "<fixture or review reference>"
    },
    {
      "asset_type": "Workstations",
      "category": "devices",
      "source": "<fixture or review reference>"
    }
  ],
  "unmapped_on_review": {
    "source": "<review reference>",
    "note": "Observed and deliberately left unmapped: no supported category fits.",
    "asset_types": [
      "Kubernetes clusters",
      "Backup & dr jobs",
      "Ci/cd pipelines"
    ]
  },
  "reference_labels": [
    {
      "label": "Assigned To",
      "source": "<review reference>; value names another asset the holder relates to"
    },
    {"label": "Host",    "source": "..."},
    {"label": "Owner",   "source": "..."},
    {"label": "Used By", "source": "..."},
    {"label": "Site",    "source": "..."}
  ],
  "free_text_labels": [
    {
      "label": "Notes",
      "source": "<review reference>; HTML free text, not indexed"
    }
  ]
}
```

**Supported categories** (fixed in code, layouts assigned via config):
`contacts_people`, `devices`, `servers`, `network`, `applications`,
`tech_stack`, `locations`, `vendors`, `contracts`, `certificates`

**Tenant-configurable exclusions** — `EXCLUDED_MENTION_LABELS` in `vocabulary.py`
defaults to `("Notes", "EOL Components", "Role")`. These are field label names
whose values are not counted as evidence even when they mention a technology.
Replace for your data source.

---

## schema.json (SQL-level, SQLite)

Declarative schema for the SQL implementation. `ops.py` may only touch
collections, fields, and relationships declared here. All identifiers are
checked against a strict pattern; nothing from user input reaches a statement
except as a bound parameter.

```json
{
  "schema_version": 1,
  "collections": {
    "companies": {
      "table": "companies",
      "identity_key": "company_id",
      "label_column": "name",
      "eligibility": {
        "non_archived": {"column": "archived", "op": "=", "value": 0}
      },
      "fields": {
        "state": {"kind": "json", "column": "detail_json", "path": "$.company.state"},
        "city":  {"kind": "json", "column": "detail_json", "path": "$.company.city"},
        "name":  {"kind": "column", "column": "name"}
      },
      "grain": "company"
    },
    "assets": {
      "table": "assets",
      "identity_key": "asset_id",
      "label_column": "name",
      "eligibility": {
        "non_archived": {"column": "archived", "op": "=", "value": 0}
      },
      "fields": {
        "asset_type": {"kind": "column", "column": "asset_type"},
        "name":       {"kind": "column", "column": "name"}
      },
      "attributes": {
        "table": "asset_fields",
        "key_column": "asset_id",
        "label_column": "label",
        "value_column": "value_text"
      },
      "grain": "asset"
    }
  },
  "relationships": {
    "asset.company_id -> company.id": {
      "from": "assets", "from_column": "company_id",
      "to": "companies", "to_column": "company_id",
      "cardinality": "many_to_one"
    }
  }
}
```

---

## Module: mappings.py

Loads semantic-mappings.json at runtime. Env var `SEMANTIC_MAPPINGS` overrides
the default config path. Cached by mtime so hot-reload works during development.

```python
"""Reviewed semantic mappings, loaded from configuration rather than held in code.

Runtime rules contain no tenant vocabulary. Which asset-type (layout) names
belong to a supported category, which field labels relate one record to another,
and which labels hold free text are per-tenant facts: each entry records its
source, and the file can be replaced or extended (SEMANTIC_MAPPINGS=<path>)
without code changes. An asset type that no entry names stays unmapped:
discoverable, reported, and never assigned a category by a word it happens
to contain.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "semantic-mappings.json"

SUPPORTED_CATEGORIES = (
    "contacts_people", "devices", "servers", "network", "applications", "tech_stack",
    "locations", "vendors", "contracts", "certificates",
)


def normalize_type(asset_type: str | None) -> str:
    return " ".join(str(asset_type or "").casefold().split())


@dataclass(frozen=True)
class Mappings:
    categories: dict
    reference_labels: frozenset
    free_text_labels: frozenset
    source: str
    sha256: str

    def category(self, asset_type: str | None) -> str | None:
        return self.categories.get(normalize_type(asset_type))

    def evidence(self) -> dict:
        return {"source": self.source, "sha256": self.sha256}


def from_dict(data: dict, source: str = "inline") -> Mappings:
    categories: dict[str, str] = {}
    for entry in data.get("asset_type_categories", []):
        key, cat = normalize_type(entry["asset_type"]), entry["category"]
        if cat not in SUPPORTED_CATEGORIES:
            raise ValueError(f"{source}: unknown category {cat!r} for asset type {entry['asset_type']!r}")
        if not entry.get("source"):
            raise ValueError(f"{source}: mapping for {entry['asset_type']!r} records no source")
        if categories.get(key, cat) != cat:
            raise ValueError(f"{source}: asset type {entry['asset_type']!r} mapped to two categories")
        categories[key] = cat
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return Mappings(
        categories=categories,
        reference_labels=frozenset(e["label"] for e in data.get("reference_labels", [])),
        free_text_labels=frozenset(e["label"] for e in data.get("free_text_labels", [])),
        source=source,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


_cache: dict[str, Mappings] = {}


def load(path: str | Path | None = None) -> Mappings:
    """Mappings from path, else $SEMANTIC_MAPPINGS, else config/semantic-mappings.json."""
    resolved = Path(path or os.environ.get("SEMANTIC_MAPPINGS") or DEFAULT_PATH)
    key = f"{resolved}:{resolved.stat().st_mtime_ns}"
    if key not in _cache:
        _cache[key] = from_dict(json.loads(resolved.read_text(encoding="utf-8")), source=str(resolved))
    return _cache[key]
```

---

## Module: translate.py

Translates a NL question into a structured measurement contract using a local
Ollama model. Loopback-only by design — refuses non-local endpoints. No external
data is ever sent to the model; predicate names are opaque tokens.

```python
"""T3 — local Ollama translator: question -> proposed measurement contract.

The model's only job is to choose one of four supported measurements, or to
refuse. It is given the enum vocabulary and the one semantic distinction that
matters (same asset vs same owner). It is deliberately NOT given:

  * any data, field value or record from the knowledge base,
  * any expected count,
  * any permission or means to express a query.

Predicate names are opaque tokens, so the model never needs to know how
"Windows Server" is spelled in the snapshot. Inference is local only; the
endpoint defaults to loopback and no remote service is contacted.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT = 60.0

SYSTEM_PROMPT = """\
You translate a question about an IT documentation snapshot into one measurement \
contract. You do not answer the question, compute anything, or write any query.

Reply with ONE JSON object and nothing else. Two shapes are allowed.

Supported measurement:
{"operation":"count","grain":<grain>,"predicate":<predicate>,"cooccurrence":<cooccurrence>,"scope":"non_archived"}

Not supported:
{"outcome":"unsupported","reason":"<a few words>"}

Decide the fields in this order.

1. PREDICATE - which technologies the question is about.
   "windows_server"         the Windows Server operating system
   "python_and_postgresql"  Python and PostgreSQL, both of them
   Any other technology is not supported, however obviously it belongs in an
   IT estate and however plainly it may be recorded. Return the unsupported
   shape instead.

2. GRAIN - what is being counted, not what the sentence is about.
   "asset"    counting machines, assets, devices, hosts, boxes, endpoints,
              servers - individual pieces of equipment
   "company"  counting companies, clients, customers, organisations, tenants -
              the owners of equipment

3. COOCCURRENCE - a property of the predicate, not of the wording.

   For "windows_server" it is ALWAYS "not_applicable". Words such as
   "anywhere", "somewhere", "on any asset" or "across their estate" do NOT
   change this. One technology has nothing to co-occur with, so those words
   only mean "at least one".

   For "python_and_postgresql", choose by how the question positions the
   two technologies relative to each other:
     "same_asset"           both together on one asset.
     "across_owned_assets"  spread over the assets a company owns, or no
                            single shared asset named at all.

4. SCOPE is always "non_archived".

OPERATION is always "count".

Return the unsupported shape for anything else:
- a technology outside the two predicates above;
- an operation that is not a count;
- anything that returns a list, a name, a superlative or a date;
- any scope other than non-archived.
"""


class TranslatorError(Exception):
    """The local model could not be reached or returned unusable bytes."""


def build_payload(question: str, model: str, seed: int = 0) -> dict:
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "format": {
            "type": "object",
            "properties": {
                "operation":    {"type": "string", "enum": ["count"]},
                "grain":        {"type": "string", "enum": ["asset", "company"]},
                "predicate":    {"type": "string", "enum": ["windows_server", "python_and_postgresql"]},
                "cooccurrence": {"type": "string", "enum": ["not_applicable", "same_asset", "across_owned_assets"]},
                "scope":        {"type": "string", "enum": ["non_archived"]},
                "outcome":      {"type": "string", "enum": ["unsupported"]},
                "reason":       {"type": "string"},
            },
        },
        "options": {"temperature": 0, "seed": seed, "num_predict": 200},
    }


def propose(
    question: str,
    model: str,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
    seed: int = 0,
) -> tuple[object, dict]:
    """Return (parsed_candidate, trace). Never raises on model nonsense."""
    if not endpoint.startswith(("http://127.0.0.1", "http://localhost")):
        raise TranslatorError(f"Refusing non-local inference endpoint: {endpoint}")

    payload = build_payload(question, model, seed)
    request = urllib.request.Request(
        f"{endpoint}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode())
    except urllib.error.URLError as exc:
        raise TranslatorError(f"Local Ollama unreachable at {endpoint}: {exc}") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise TranslatorError(f"Local Ollama returned no usable response: {exc}") from exc

    content = (body.get("message") or {}).get("content", "")
    trace = {
        "endpoint": endpoint,
        "model": body.get("model", model),
        "seed": seed,
        "temperature": 0,
        "raw_content": content,
        "eval_count": body.get("eval_count"),
    }
    try:
        return json.loads(content), trace
    except json.JSONDecodeError:
        return None, trace


def list_models(endpoint: str = DEFAULT_ENDPOINT, timeout: float = 10.0) -> list[str]:
    try:
        with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=timeout) as response:
            body = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise TranslatorError(f"Local Ollama unreachable at {endpoint}: {exc}") from exc
    return [m.get("name", "") for m in body.get("models", [])]
```

---

## Module: vocabulary.py

Declared field/value vocabulary for measurement predicates. The **normalized
authority boundary**: every rule is a reviewable mapping. Values are matched by
exact equality, never substring or case folding. Changing a set here changes
what the measurements mean.

**Replace `EXCLUDED_MENTION_LABELS` for your data source** — the defaults below
are example field label names from IT documentation tooling.

```python
"""Declared field/value vocabulary for the measurement predicates."""
from __future__ import annotations

OS_LABEL = "Operating System"

WINDOWS_SERVER_VALUES = (
    "Windows Server 2012 R2 (EOL)",
    "Windows Server 2016",
    "Windows Server 2019",
    "Windows Server 2022",
    "Windows Server 2025",
)

# Retained as executable counterexamples: workstation Windows must never qualify.
WINDOWS_NON_SERVER_VALUES = (
    "Windows 10 LTSC",
    "Windows 10 Pro",
    "Windows 11 Pro",
)

LANGUAGE_LABEL = "Language"
PYTHON_VALUES = ("Python",)

DATABASE_LABEL = "Database"
POSTGRESQL_VALUES = ("PostgreSQL",)

# Field labels that mention these technologies but are not admissible evidence.
# Replace for your data source.
EXCLUDED_MENTION_LABELS = ("Notes", "EOL Components", "Role")

if set(WINDOWS_SERVER_VALUES) & set(WINDOWS_NON_SERVER_VALUES):
    raise AssertionError("Windows Server and workstation value sets overlap")
if not (WINDOWS_SERVER_VALUES and PYTHON_VALUES and POSTGRESQL_VALUES):
    raise AssertionError("Predicate vocabulary is empty; measurements would silently return 0")
```

---

## Module: redact.py

Generic secret redaction and prompt-injection neutralization. No data-source
coupling. Drop into any context bundle pipeline to sanitize text before it
reaches a model.

**Detects and redacts:** PEM private keys, AWS access keys, Stripe/Braintree
keys, GitHub tokens, Slack tokens, Google API keys, JWTs, URL credentials,
labelled secrets (password, api_key, token, etc.), credential statements,
user/password patterns, SSNs, Luhn-valid card numbers.

**Detects and removes:** common prompt-injection phrases ("ignore previous
instructions", "your new task", role-prefix injections, etc.).

```python
import re
from typing import Dict, Any

REDACTED = "[REDACTED SECRET]"
INJECTION_REMOVED = "[REMOVED: instruction-like text]"

TOKEN_SHAPES = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
]

# ... (full implementation: redact_secrets, neutralize_injection, clean_text)
# See redact.py in source for the complete 219-line implementation.
```

**Public API:**
- `redact_secrets(text: str) -> {"text": str, "count": int}`
- `neutralize_injection(text: str) -> {"text": str, "count": int}`
- `clean_text(text: str) -> {"text": str, "redactions": int, "injections": int}`

---

## Router: keyword + embedding

Two injectable router implementations. Both implement `(question: str) ->
(pattern_id: str, confidence: float)`. Use either as the `router=` argument to
`answer()`.

### Keyword router (no ML deps)

```python
def make_keyword_router() -> Callable[[str], tuple[str, float]]:
    """Deterministic, no ML. confidence=0.9 on keyword hit, 0.5 fallback."""
    _KEYWORDS = [
        ("tech_stack",      ["tech stack", "language", "framework", "database", "runtime"]),
        ("network",         ["network device", "vlan", "subnet", "router", "switch", "firewall"]),
        ("contacts_people", ["contact", "person", "people", "staff", "employee"]),
        ("devices",         ["workstation", "laptop", "computer", "mobile", "phone", "iphone"]),
        ("servers",         ["server", "vm", "virtual machine"]),
        ("applications",    ["application", "saas", "subscription", "license", "software"]),
        ("locations",       ["location", "site", "office",
                             r"(?<!ip )(?<!mac )(?<!wan )(?<!gateway )(?<!email )address"]),
        ("vendors",         ["vendor", "supplier"]),
        ("contracts",       ["contract", "sla", "agreement", "renewal"]),
        ("certificates",    ["certificate",
                             r"domain(?!\s+(?:controller|admin|join|user|account))",
                             "ssl", "expir"]),
        ("client_overview", ["overview", "full picture", "everything about"]),
    ]
    # ... compile + CROSS_SCOPE_RE check -> (pattern_id, 0.9 | 0.5)
```

### Embedding router (sentence-transformers)

```python
class EmbeddingRouter:
    """Cosine-similarity router backed by sentence-transformers/all-MiniLM-L6-v2."""

    def __init__(self, patterns: dict[str, str] | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self._patterns = patterns or PATTERNS
        ids = list(self._patterns.keys())
        self._ids = ids
        self._embeddings = self._model.encode(
            [self._patterns[k] for k in ids], convert_to_numpy=True
        )

    def __call__(self, question: str) -> tuple[str, float]:
        q_emb = self._model.encode([question], convert_to_numpy=True)[0]
        sims = self._embeddings @ q_emb / (
            np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(q_emb) + 1e-10
        )
        best = int(np.argmax(sims))
        return self._ids[best], float(sims[best])

def make_router(patterns=None) -> EmbeddingRouter:
    return EmbeddingRouter(patterns)
```

### Hybrid router

```python
def make_hybrid_router():
    """Keyword fires first (0.9 = silent). Embedding used for disambiguation (capped 0.6 = always asks)."""
    kw = make_keyword_router()
    try:
        emb = make_router()
    except RuntimeError:
        return kw  # sentence-transformers not installed; keyword only

    def _hybrid(question):
        kw_pattern, kw_conf = kw(question)
        if kw_conf >= 0.9:
            return kw_pattern, kw_conf
        emb_pattern, emb_conf = emb(question)
        return emb_pattern, min(emb_conf, 0.6)  # cap: never silent, better routing

    return _hybrid
```

### Confidence thresholds

```python
_THRESHOLD_SILENT = 0.75   # answer without asking
_THRESHOLD_SINGLE = 0.50   # ask one clarifying question
# < 0.50: full disambiguation prompt
```

---

## answer() — Public API

```python
def answer(
    snapshot: dict,
    question: str,
    *,
    router: Callable[[str], tuple[str, float]],   # required
    warn_age_days: float | None = 7.0,
    term_index: TermIndex | None = None,
    mappings: Mappings | None = None,
) -> dict:
```

Returns:
```python
{
    "pattern_id":            str,        # router's chosen pattern
    "confidence":            float,
    "company_filter":        str | None, # company name extracted from question
    "scope":                 str,        # "cross_client" | "company" | "unscoped"
    "category":              str | None,
    "value_term":            str | None, # specific thing asked about (e.g. "Fortinet")
    "negated":               bool,
    "results":               list[dict], # [{company, company_id, asset, asset_id}]
    "count":                 int,
    "answer_grain":          str,        # "asset" | "company"
    "answer_shape":          str,        # "count" | "list" | "detail" | "exists"
    "qualifying_company_ids": list | None,
    "qualifying_asset_ids":   list | None,
    "source_provenance":     dict,
    "needs_clarification":   bool,
    "clarification_prompt":  str | None,
    "category_membership":   dict,       # which layouts mapped, which unmapped
    "terms":                 dict | None # term index evidence (if term_index given)
}
```

---

## Notes on Adapting to a New Data Source

1. **Snapshot shape**: produce `{"companies": [...]}` conforming to the schema
   above, or rewrite `term_index.build()` to traverse your own structure.
2. **Mappings**: review your asset type names and map them to the 12 categories
   in a new `semantic-mappings.json`. Every entry needs a `source` field.
3. **Vocabulary**: update `EXCLUDED_MENTION_LABELS` for your field label names.
4. **Env var**: `SEMANTIC_MAPPINGS=<path>` to point at a custom mappings file.
5. **Router**: both routers are data-independent; inject via `router=` argument.
6. **translate.py**: the SYSTEM_PROMPT predicates (`windows_server`,
   `python_and_postgresql`) are examples. Replace with your measurement
   vocabulary and update the `format` schema in `build_payload()`.
