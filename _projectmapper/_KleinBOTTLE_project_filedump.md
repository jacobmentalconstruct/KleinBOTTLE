# Project Filedump

- Source root: `C:\Jacob\_GameDESIGN\_KleinBOTTLE`
- Snapshot: `_KleinBOTTLE_snapshot.sqlite3`
- Generated: `2026-11-04T10:23:23`
- Captured files: `87`

---

## FILE: `.microservice-library/services/_ArchiveBotMS.py`

```python
"""
SERVICE_NAME: _ArchiveBotMS
ENTRY_POINT: _ArchiveBotMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import datetime
import fnmatch
import logging
import os
import tarfile
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from microservice_std_lib import service_metadata, service_endpoint, BaseService
import time
SERVICE_TITLE = 'ArchiveBot'
SERVICE_VERSION = '1.1.0'
LOG_LEVEL = logging.INFO
DEFAULT_IGNORE_DIRS: Set[str] = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env', '.mypy_cache', '.pytest_cache', '.idea', '.vscode', 'dist', 'build', 'coverage', 'target', 'out', 'bin', 'obj'}
DEFAULT_IGNORE_FILES: Set[str] = {'.DS_Store', 'Thumbs.db', '*.pyc', '*.pyo', '*.log', '*.tmp'}
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(SERVICE_TITLE)

@service_metadata(name=SERVICE_TITLE, version=SERVICE_VERSION, description='Creates timestamped .tar.gz backups of directory trees.', tags=['utility', 'backup', 'filesystem'], capabilities=['filesystem:read', 'filesystem:write'], side_effects=['filesystem:write'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=[])
class ArchiveBotMS(BaseService):

    def __init__(self, config: Optional[Dict[str, Any]]=None) -> None:
        super().__init__(SERVICE_TITLE)
        self.config = config or {}

    @service_endpoint(inputs={'source_path': 'str', 'output_dir': 'str', 'extra_exclusions': 'List[str]', 'use_default_exclusions': 'bool'}, outputs={'archive_path': 'str', 'file_count': 'int'}, description='Compresses a directory into a .tar.gz archive.', tags=['action', 'backup'], side_effects=['filesystem:write'])
    def create_backup(self, source_path: str, output_dir: str, extra_exclusions: Optional[Set[str]]=None, use_default_exclusions: bool=True) -> Dict[str, Any]:
        src = Path(source_path).resolve()
        out = Path(output_dir).resolve()
        if not src.exists():
            logger.error(f'Source not found: {src}')
            raise FileNotFoundError(f'Source path does not exist: {src}')
        out.mkdir(parents=True, exist_ok=True)
        exclude_patterns: Set[str] = set()
        if use_default_exclusions:
            exclude_patterns.update(DEFAULT_IGNORE_DIRS)
            exclude_patterns.update(DEFAULT_IGNORE_FILES)
        if extra_exclusions:
            exclude_patterns.update(extra_exclusions)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        archive_name = f'backup_{src.name}_{timestamp}.tar.gz'
        archive_path = out / archive_name
        file_count = 0
        try:
            with tarfile.open(archive_path, 'w:gz') as tar:
                for root, dirs, files in os.walk(src):
                    dirs[:] = [d for d in dirs if not self._is_excluded(d, exclude_patterns)]
                    for file_name in files:
                        if self._is_excluded(file_name, exclude_patterns):
                            continue
                        full_path = Path(root) / file_name
                        if full_path == archive_path:
                            continue
                        rel_path = full_path.relative_to(src)
                        tar.add(full_path, arcname=rel_path)
                        file_count += 1
            logger.info(f'Archive created: {archive_path} ({file_count} files)')
            return {'archive_path': str(archive_path), 'file_count': file_count}
        except Exception as exc:
            logger.exception(f'Backup failed: {exc}')
            if archive_path.exists():
                try:
                    archive_path.unlink()
                except Exception:
                    pass
            raise exc

    def _is_excluded(self, name: str, patterns: Set[str]) -> bool:
        for pattern in patterns:
            if name == pattern or fnmatch.fnmatch(name, pattern):
                return True
        return False
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import tempfile
    bot = ArchiveBotMS()
    print(f'Service Ready: {bot}')
    with tempfile.TemporaryDirectory() as tmp_source:
        with tempfile.TemporaryDirectory() as tmp_out:
            p = Path(tmp_source) / 'test_file.txt'
            p.write_text('Hello Archive')
            print(f'Backing up {tmp_source} to {tmp_out}...')
            result = bot.create_backup(tmp_source, tmp_out)
            print(f'Result: {result}')
```

---

## FILE: `.microservice-library/services/_AuthMS.py`

```python
"""
SERVICE_NAME: _AuthMS
ENTRY_POINT: _AuthMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import base64
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional
from microservice_std_lib import service_metadata, service_endpoint
'\nSERVICE: Auth\nROLE: Manage user authentication and signed session tokens.\nINPUTS:\n  - username: Login identifier.\n  - password: Secret credential.\n  - token: Serialized session token string.\nOUTPUTS:\n  - token: Signed session token (str) or None on failure.\n  - is_valid: Boolean indicating whether a token is valid and not expired.\nNOTES:\n  This is a simplified in-memory auth system intended for local tools and\n  pipelines, not production-grade security.\n'
logger = logging.getLogger(__name__)
DEFAULT_SECRET_KEY = 'super_secret_cortex_key'
DEFAULT_SALT = 'cortex_salt'

@service_metadata(name='Auth', version='1.0.0', description='Manages user authentication and session tokens.', tags=['auth', 'security', 'crypto'], capabilities=['crypto'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class AuthMS:
    """
    ROLE: Simple authentication microservice providing username/password login
          and signed session tokens.

    INPUTS:
      - config: Optional configuration dict. Recognized keys:
          - 'secret_key': Secret used to sign tokens.

    OUTPUTS:
      - Exposes `login` and `validate_session` endpoints for use in pipelines.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None) -> None:
        self.config = config or {}
        self.secret_key: str = self.config.get('secret_key', DEFAULT_SECRET_KEY)
        self.users_db: Dict[str, str] = {'admin': self._hash_password('admin123')}

    @service_endpoint(inputs={'username': 'str', 'password': 'str'}, outputs={'token': 'Optional[str]'}, description='Attempts to log in and returns a signed session token.', tags=['auth', 'security', 'session'])
    def login(self, username: str, password: str) -> Optional[str]:
        """
        Attempt to log in with the provided username and password.

        :param username: Login identifier.
        :param password: Plain-text password.
        :returns: Signed session token if successful, None otherwise.
        """
        if username not in self.users_db:
            return None
        stored_hash = self.users_db[username]
        if self._verify_password(password, stored_hash):
            return self._create_token(username)
        return None

    @service_endpoint(inputs={'token': 'str'}, outputs={'is_valid': 'bool'}, description='Checks whether a token is valid and not expired.', tags=['auth', 'security'])
    def validate_session(self, token: str) -> bool:
        """
        Check if a serialized token is valid and not expired.

        :param token: Session token string.
        :returns: True if token is valid and not expired, False otherwise.
        """
        payload = self._decode_token(token)
        return payload is not None

    def _hash_password(self, password: str) -> str:
        """
        Securely hashes a password using SHA-256 with a static salt.
        """
        return hashlib.sha256((password + DEFAULT_SALT).encode('utf-8')).hexdigest()

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a provided password against the stored hash.
        """
        return self._hash_password(plain_password) == hashed_password

    def _create_token(self, user_id: str, expires_in: int=3600) -> str:
        """
        Generates a signed session token.

        Payload includes:
          - 'sub' (subject)
          - 'exp' (expiration time)
          - 'iat' (issued-at time)
          - 'scope' (authorization scope)
        """
        now = int(time.time())
        payload = {'sub': user_id, 'exp': now + expires_in, 'iat': now, 'scope': 'admin'}
        json_payload = json.dumps(payload).encode('utf-8')
        token_part = base64.b64encode(json_payload).decode('utf-8')
        signature = hashlib.sha256((token_part + self.secret_key).encode('utf-8')).hexdigest()
        return f'{token_part}.{signature}'

    def _decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Parses and validates the incoming token.

        Returns the payload if valid, None otherwise.
        """
        try:
            if not token or '.' not in token:
                return None
            token_part, signature = token.split('.', 1)
            recalc_signature = hashlib.sha256((token_part + self.secret_key).encode('utf-8')).hexdigest()
            if signature != recalc_signature:
                return None
            payload_json = base64.b64decode(token_part).decode('utf-8')
            payload: Dict[str, Any] = json.loads(payload_json)
            if payload.get('exp', 0) < time.time():
                return None
            return payload
        except Exception:
            logger.exception('Failed to decode or validate auth token.')
            return None
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    svc = AuthMS()
    print('Service ready:', svc)
```

---

## FILE: `.microservice-library/services/_CartridgeServiceMS.py`

```python
"""
SERVICE_NAME: _CartridgeServiceMS
ENTRY_POINT: _CartridgeServiceMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: sqlite_vec
"""
import datetime
import json
import os
import sqlite3
import struct
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None
from microservice_std_lib import service_metadata, service_endpoint
from base_service import BaseService

@service_metadata(name='CartridgeServiceMS', version='1.1.0', description='The Source of Truth. Manages the Unified Neural Cartridge Format (UNCF v1.0).', tags=['storage', 'database', 'RAG'], capabilities=['sqlite', 'vector-search', 'graph-storage'], side_effects=['filesystem:read', 'filesystem:write'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=['sqlite_vec'])
class CartridgeServiceMS(BaseService):
    """
    The Source of Truth.
    Manages the Unified Neural Cartridge Format (UNCF v1.0).
    """
    SCHEMA_VERSION = 'uncf_v1.0'

    def __init__(self, db_path: str):
        super().__init__('CartridgeServiceMS')
        self.db_path = Path(db_path)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        if sqlite_vec:
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except Exception as e:
                self.log_error(f'Failed to load sqlite-vec: {e}')
        return conn

    def get_vector_dim(self) -> int:
        """Retrieves the expected vector dimension from the manifest spec."""
        spec = self.get_manifest('embedding_spec') or {}
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except:
                spec = {}
        return int(spec.get('dim', 0))

    def _init_db(self):
        """Initializes the standard Schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('CREATE TABLE IF NOT EXISTS manifest (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute("\n            CREATE TABLE IF NOT EXISTS directories (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                vfs_path TEXT UNIQUE NOT NULL,\n                parent_path TEXT,\n                metadata TEXT DEFAULT '{}'\n            )\n        ")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dir_parent ON directories(parent_path)')
        cursor.execute('\n            CREATE TABLE IF NOT EXISTS files (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                vfs_path TEXT NOT NULL,       -- Portable path (e.g. "src/main.py")\n                origin_path TEXT,             -- Provenance (e.g. "C:/Users/...")\n                origin_type TEXT,             -- \'filesystem\', \'web\', \'github\'\n                content TEXT,                 -- Text content (UTF-8)\n                blob_data BLOB,               -- Binary content (Images, PDFs)\n                mime_type TEXT,\n                status TEXT DEFAULT \'RAW\',    -- RAW, REFINED, ERROR, SKIPPED\n                metadata TEXT DEFAULT \'{}\',   -- JSON tags, summaries\n                last_updated TIMESTAMP\n            )\n        ')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_vfs ON files(vfs_path)')
        cursor.execute('\n            CREATE TABLE IF NOT EXISTS chunks (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                file_id INTEGER,\n                chunk_index INTEGER,\n                content TEXT,\n                embedding BLOB,\n                name TEXT,\n                type TEXT,\n                start_line INTEGER,\n                end_line INTEGER,\n                FOREIGN KEY(file_id) REFERENCES files(id)\n            )\n        ')
        if sqlite_vec:
            dim = self.get_vector_dim()
            if dim > 0:
                try:
                    cursor.execute(f'CREATE VIRTUAL TABLE IF NOT EXISTS vec_items USING vec0(embedding float[{dim}])')
                except Exception as e:
                    self.log_error(f'Vector Table Init Error: {e}')
            else:
                self.log_info('Vector table creation deferred: No dimensions found in manifest yet.')
        cursor.execute('CREATE TABLE IF NOT EXISTS graph_nodes (id TEXT PRIMARY KEY, type TEXT, label TEXT, data_json TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS graph_edges (source TEXT, target TEXT, relation TEXT, weight REAL)')
        cursor.execute('CREATE TABLE IF NOT EXISTS logs (timestamp REAL, level TEXT, message TEXT, context TEXT)')
        conn.commit()
        conn.close()
        self.initialize_manifest()

    def initialize_manifest(self):
        """Populates the boot sector with strict RagFORGE Cartridge Schema (UNCF) v1.1."""
        if not self.get_manifest('cartridge_id'):
            now = datetime.datetime.utcnow().isoformat()
            self.set_manifest('schema_name', 'ragforge_cartridge')
            self.set_manifest('schema_version', '1.1.0')
            self.set_manifest('cartridge_id', str(uuid.uuid4()))
            self.set_manifest('created_at_utc', now)
            self.set_manifest('created_by_app', 'RagFORGE')
            self.set_manifest('sources', [])
            self.set_manifest('source_policies', {'binary_policy': 'Extract Text', 'web_depth': 0})
            self.set_manifest('embedding_spec', {'provider': 'unknown', 'model': 'pending_init', 'dim': 0, 'dtype': 'unknown', 'distance': 'unknown'})
            self.set_manifest('chunking_spec', {'strategy': 'semantic_hybrid', 'python_ast': True, 'generic_window': 1500})
            self.set_manifest('vfs', {'root_label': '', 'directories': {'count': 0}, 'files': {'count': 0, 'by_origin_type': {}, 'by_mime': {}}, 'index_built': False})
            self.set_manifest('content_stats', {'chunks': {'count': 0}, 'vector_index': {'enabled': False, 'table': 'vec_items', 'backend': 'sqlite-vec', 'dims': 0, 'status': 'unknown'}, 'graph': {'nodes': 0, 'edges': 0}})
            self.set_manifest('capabilities', {'tables': {'manifest': True, 'directories': True, 'files': True, 'chunks': True, 'vec_items': True, 'graph_nodes': True, 'graph_edges': True, 'logs': True}, 'navigation': {'vfs_path': 'files.vfs_path', 'directory_index': 'directories.vfs_path', 'list_files_query': 'SELECT vfs_path, mime_type, origin_type, status FROM files ORDER BY vfs_path', 'list_directories_query': 'SELECT vfs_path, parent_path FROM directories ORDER BY vfs_path'}, 'retrieval': {'raw_file_content_query': 'SELECT content, blob_data, mime_type FROM files WHERE vfs_path=?', 'chunks_by_file_query': 'SELECT chunk_index, name, type, start_line, end_line, content FROM chunks WHERE file_id=? ORDER BY chunk_index', 'vector_search': 'sqlite-vec on vec_items if available'}, 'python_helper_api': {'note': 'Optional convenience layer for agents running inside Python. For non-Python consumers, use the SQL queries above.', 'methods': ['CartridgeServiceMS.get_status_flags', 'CartridgeServiceMS.list_files', 'CartridgeServiceMS.list_directories', 'CartridgeServiceMS.get_file_record', 'CartridgeServiceMS.get_directory_tree', 'CartridgeServiceMS.get_status_summary', 'CartridgeServiceMS.add_node', 'CartridgeServiceMS.add_edge', 'CartridgeServiceMS.search_embeddings']}})
            self.set_manifest('cartridge_health', 'FRESH')
            self.set_manifest('ingest_complete', False)
            self.set_manifest('refine_complete', False)
            self.set_manifest('last_ingest_at_utc', '')
            self.set_manifest('last_refine_at_utc', '')
            self.set_manifest('last_error', '')
            self.set_manifest('locks', {'write_lock_expected': False, 'notes': 'If DB locks occur, consider batching writes and shorter-lived connections.'})

    def set_manifest(self, key: str, value: Any):
        """Upsert metadata key."""
        conn = self._get_conn()
        val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        conn.execute('INSERT OR REPLACE INTO manifest (key, value) VALUES (?, ?)', (key, val_str))
        conn.commit()
        conn.close()

    def get_manifest(self, key: str) -> Optional[str]:
        """Retrieve metadata key."""
        conn = self._get_conn()
        row = conn.execute('SELECT value FROM manifest WHERE key=?', (key,)).fetchone()
        conn.close()
        return row[0] if row else None

    def validate_cartridge(self) -> Dict[str, Any]:
        """Quality Control: Checks if the cartridge is Agent-Safe."""
        report = {'valid': True, 'health': 'OK', 'errors': []}
        required = ['schema_name', 'schema_version', 'cartridge_id', 'created_at_utc', 'created_by_app', 'embedding_spec', 'chunking_spec', 'capabilities']
        for key in required:
            if not self.get_manifest(key):
                report['valid'] = False
                report['errors'].append(f'Missing Manifest Key: {key}')
        conn = self._get_conn()
        vec_enabled = False
        vec_status = 'unknown'
        try:
            conn.execute('SELECT count(*) FROM vec_items').fetchone()
            vec_enabled = True
            vec_status = 'available'
        except Exception:
            vec_enabled = False
            vec_status = 'unavailable'
            report['errors'].append('Vector Index (vec_items) missing or not loaded.')
            report['health'] = 'WARN_NO_VECTORS'
        finally:
            conn.close()
        try:
            content_stats = self.get_manifest('content_stats') or {}
            if isinstance(content_stats, str):
                try:
                    content_stats = json.loads(content_stats)
                except:
                    content_stats = {}
            vec = content_stats.get('vector_index', {}) if isinstance(content_stats, dict) else {}
            embed_spec = self.get_manifest('embedding_spec') or {}
            if isinstance(embed_spec, str):
                try:
                    embed_spec = json.loads(embed_spec)
                except:
                    embed_spec = {}
            spec_dim = 0
            if isinstance(embed_spec, dict):
                spec_dim = int(embed_spec.get('dim', 0) or 0)
            vec['enabled'] = bool(vec_enabled)
            vec['status'] = vec_status
            if spec_dim > 0:
                vec['dims'] = spec_dim
            if 'table' not in vec:
                vec['table'] = 'vec_items'
            if 'backend' not in vec:
                vec['backend'] = 'sqlite-vec'
            content_stats['vector_index'] = vec
            self.set_manifest('content_stats', content_stats)
        except Exception as e:
            report['errors'].append(f'Failed to stamp vector_index status into manifest: {e}')
            report['health'] = 'WARN_MANIFEST_STAMP_FAIL'
        return report

    def store_file(self, vfs_path: str, origin_path: str, content: str=None, blob: bytes=None, mime_type: str='text/plain', origin_type: str='filesystem'):
        """
        The Universal Input Method.
        Stores raw data. If file exists, updates it and resets status to 'RAW' for re-refining.
        """
        conn = self._get_conn()
        try:
            conn.execute("\n                INSERT OR REPLACE INTO files \n                (vfs_path, origin_path, origin_type, content, blob_data, mime_type, status, last_updated)\n                VALUES (?, ?, ?, ?, ?, ?, 'RAW', ?)\n            ", (vfs_path, origin_path, origin_type, content, blob, mime_type, time.time()))
            conn.commit()
            return True
        except Exception as e:
            self.log_error(f'DB Store Error ({vfs_path}): {e}')
            return False
        finally:
            conn.close()

    def get_pending_files(self, limit: int=10) -> List[Dict]:
        """Fetches files waiting for the Refinery."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM files WHERE status = 'RAW' LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_status(self, file_id: int, status: str, metadata: dict=None):
        conn = self._get_conn()
        if metadata:
            conn.execute('UPDATE files SET status = ?, metadata = ? WHERE id = ?', (status, json.dumps(metadata), file_id))
        else:
            conn.execute('UPDATE files SET status = ? WHERE id = ?', (status, file_id))
        conn.commit()
        conn.close()

    def ensure_directory(self, vfs_path: str):
        """Idempotent insert for VFS directories."""
        if not vfs_path:
            return
        parent = os.path.dirname(vfs_path).replace('\\', '/')
        if parent == vfs_path:
            parent = ''
        conn = self._get_conn()
        try:
            conn.execute('INSERT OR IGNORE INTO directories (vfs_path, parent_path) VALUES (?, ?)', (vfs_path, parent))
            conn.commit()
        except:
            pass
        finally:
            conn.close()

    def _coerce_bool(self, v: Any) -> bool:
        """Best-effort conversion for manifest values stored as strings."""
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ('1', 'true', 'yes', 'y', 'on')

    @service_endpoint(inputs={}, outputs={'ingest_complete': 'bool', 'refine_complete': 'bool', 'cartridge_health': 'str'}, description='Returns key manifest status flags (ingest/refine status and health) in a single call.', tags=['status', 'health'])
    def get_status_flags(self) -> Dict[str, Any]:
        """Returns key manifest status flags in a single call."""
        ingest_complete = self._coerce_bool(self.get_manifest('ingest_complete'))
        refine_complete = self._coerce_bool(self.get_manifest('refine_complete'))
        health = self.get_manifest('cartridge_health') or 'UNKNOWN'
        return {'ingest_complete': ingest_complete, 'refine_complete': refine_complete, 'cartridge_health': health, 'schema_name': self.get_manifest('schema_name') or '', 'schema_version': self.get_manifest('schema_version') or '', 'cartridge_id': self.get_manifest('cartridge_id') or ''}

    def list_files(self, prefix: str='', status: Optional[str]=None, limit: Optional[int]=None) -> List[Dict[str, Any]]:
        """Enumerate files in the cartridge (optionally filtered by VFS prefix and/or status)."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            sql = 'SELECT id, vfs_path, origin_path, origin_type, mime_type, status, last_updated, metadata FROM files'
            clauses = []
            params = []
            if prefix:
                clauses.append('vfs_path LIKE ?')
                params.append(prefix.rstrip('/') + '/%')
            if status:
                clauses.append('status = ?')
                params.append(status)
            if clauses:
                sql += ' WHERE ' + ' AND '.join(clauses)
            sql += ' ORDER BY vfs_path'
            if limit is not None:
                sql += ' LIMIT ?'
                params.append(int(limit))
            rows = conn.execute(sql, tuple(params)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d['metadata'] = json.loads(d.get('metadata') or '{}')
                except Exception:
                    d['metadata'] = {}
                out.append(d)
            return out
        finally:
            conn.close()

    def get_file_record(self, vfs_path: str) -> Optional[Dict[str, Any]]:
        """Fetch a single file record by VFS path."""
        if not vfs_path:
            return None
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute('SELECT id, vfs_path, origin_path, origin_type, content, blob_data, mime_type, status, metadata, last_updated FROM files WHERE vfs_path = ?', (vfs_path,)).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d['metadata'] = json.loads(d.get('metadata') or '{}')
            except Exception:
                d['metadata'] = {}
            return d
        finally:
            conn.close()

    def list_directories(self, prefix: str='') -> List[Dict[str, Any]]:
        """Enumerate directories in the cartridge VFS."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            if prefix:
                rows = conn.execute('SELECT id, vfs_path, parent_path, metadata FROM directories WHERE vfs_path LIKE ? ORDER BY vfs_path', (prefix.rstrip('/') + '/%',)).fetchall()
            else:
                rows = conn.execute('SELECT id, vfs_path, parent_path, metadata FROM directories ORDER BY vfs_path').fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d['metadata'] = json.loads(d.get('metadata') or '{}')
                except Exception:
                    d['metadata'] = {}
                out.append(d)
            return out
        finally:
            conn.close()

    @service_endpoint(inputs={'root': 'str'}, outputs={'tree': 'dict'}, description='Builds a nested directory tree structure for UI navigation or context mapping.', tags=['vfs', 'navigation'])
    def get_directory_tree(self, root: str='') -> Dict[str, Any]:
        """Builds a nested directory tree starting at `root` ("" for full tree)."""
        dirs = self.list_directories(prefix=root) if root else self.list_directories()
        files = self.list_files(prefix=root) if root else self.list_files()

        def new_node():
            return {'_dirs': {}, '_files': []}
        tree = new_node()
        for d in dirs:
            path = (d.get('vfs_path') or '').strip('/')
            if not path:
                continue
            parts = path.split('/')
            cur = tree
            for p in parts:
                cur = cur['_dirs'].setdefault(p, new_node())
        for f in files:
            path = (f.get('vfs_path') or '').strip('/')
            if not path:
                continue
            parts = path.split('/')
            fname = parts[-1]
            cur = tree
            for p in parts[:-1]:
                cur = cur['_dirs'].setdefault(p, new_node())
            cur['_files'].append({'name': fname, 'vfs_path': f.get('vfs_path'), 'mime_type': f.get('mime_type'), 'origin_type': f.get('origin_type'), 'status': f.get('status')})
        return tree

    def get_status_summary(self) -> Dict[str, Any]:
        """Counts files by status and provides a quick cartridge overview."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute('SELECT status, COUNT(*) as n FROM files GROUP BY status').fetchall()
            by_status = {r['status']: r['n'] for r in rows}
            dcnt = conn.execute('SELECT COUNT(*) FROM directories').fetchone()[0]
            fcnt = conn.execute('SELECT COUNT(*) FROM files').fetchone()[0]
            ccnt = conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
            ncnt = conn.execute('SELECT COUNT(*) FROM graph_nodes').fetchone()[0]
            ecnt = conn.execute('SELECT COUNT(*) FROM graph_edges').fetchone()[0]
            return {'directories': int(dcnt), 'files': int(fcnt), 'chunks': int(ccnt), 'graph_nodes': int(ncnt), 'graph_edges': int(ecnt), 'files_by_status': by_status, 'flags': self.get_status_flags()}
        finally:
            conn.close()

    def add_node(self, node_id: str, node_type: str, label: str, data: dict=None):
        conn = self._get_conn()
        conn.execute('INSERT OR REPLACE INTO graph_nodes (id, type, label, data_json) VALUES (?, ?, ?, ?)', (node_id, node_type, label, json.dumps(data or {})))
        conn.commit()
        conn.close()

    def add_edge(self, source: str, target: str, relation: str='related', weight: float=1.0):
        conn = self._get_conn()
        conn.execute('INSERT OR IGNORE INTO graph_edges (source, target, relation, weight) VALUES (?, ?, ?, ?)', (source, target, relation, weight))
        conn.commit()
        conn.close()

    @service_endpoint(inputs={'query_vector': 'list', 'limit': 'int'}, outputs={'results': 'list'}, description='Performs semantic vector search using sqlite-vec against the cartridge chunks.', tags=['search', 'vector'])
    def search_embeddings(self, query_vector: List[float], limit: int=5) -> List[Dict]:
        """Performs semantic search using sqlite-vec."""
        if not sqlite_vec or not query_vector:
            return []
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        results = []
        try:
            rows = conn.execute('\n                SELECT\n                    rowid,\n                    distance\n                FROM vec_items\n                WHERE embedding MATCH ?\n                ORDER BY distance\n                LIMIT ?\n            ', (json.dumps(query_vector), limit)).fetchall()
            for r in rows:
                chunk_id = r['rowid']
                query = '\n                    SELECT c.*, f.vfs_path \n                    FROM chunks c \n                    JOIN files f ON c.file_id = f.id \n                    WHERE c.id=?\n                '
                chunk = conn.execute(query, (chunk_id,)).fetchone()
                if chunk:
                    res = dict(chunk)
                    res['score'] = r['distance']
                    results.append(res)
        except Exception as e:
            self.log_error(f'Vector Search Error: {e}')
        finally:
            conn.close()
        return results
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = os.path.join(tmp_dir, 'test_cartridge.db')
        print(f'Initializing service at: {db_file}')
        svc = CartridgeServiceMS(db_file)
        print(f'Service Ready: {svc}')
        status = svc.get_status_flags()
        print(f'Initial Status: {status}')
```

---

## FILE: `.microservice-library/services/_ChalkBoardMS.py`

```python
"""
SERVICE_NAME: _ChalkBoardMS
ENTRY_POINT: _ChalkBoardMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: webview
"""
import json
import os
import webview
from microservice_std_lib import service_metadata, service_endpoint, BaseService
import time
HTML_CONTENT = '\n<!DOCTYPE html>\n<html lang="en">\n<head>\n    <meta charset="UTF-8">\n    <title>OBS Signboard</title>\n    <link href="https://fonts.googleapis.com/css2?family=Neonderthaw&family=Press+Start+2P&family=Fredericka+the+Great&family=Orbitron:wght@700&family=Special+Elite&display=swap" rel="stylesheet">\n    <style>\n        body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; display: flex; justify-content: center; align-items: center; transition: all 0.5s ease; }\n        #sign-container { width: 90%; text-align: center; outline: none; cursor: text; transition: transform 0.2s; }\n        \n        /* --- THEME 1: NEON NIGHTS --- */\n        body.neon { background-color: #050505; font-family: \'Neonderthaw\', cursive; }\n        body.neon #sign-container { color: #fff; font-size: 8rem; text-shadow: 0 0 7px #fff, 0 0 42px #bc13fe, 0 0 102px #bc13fe; animation: flicker 1.5s infinite alternate; }\n\n        /* --- THEME 2: 8-BIT HACKER --- */\n        body.terminal { background-color: #000; font-family: \'Press Start 2P\', cursive; }\n        body.terminal #sign-container { color: #00ff41; font-size: 3.5rem; text-shadow: 0 0 10px #00ff41; text-transform: uppercase; }\n        body.terminal #sign-container::after { content: \'_\'; animation: blink 1s step-end infinite; }\n\n        /* --- THEME 3: CHALKBOARD --- */\n        body.chalk { background-color: #2b3a28; font-family: \'Fredericka the Great\', cursive; background-image: radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 20px 20px; }\n        body.chalk #sign-container { color: rgba(255,255,255,0.9); font-size: 6rem; transform: rotate(-1deg); }\n\n        /* --- NEW THEME 4: BLUEPRINT (Technical) --- */\n        body.blueprint { background-color: #003366; font-family: \'Orbitron\', sans-serif; background-image: linear-gradient(#004080 1px, transparent 1px), linear-gradient(90deg, #004080 1px, transparent 1px); background-size: 50px 50px; }\n        body.blueprint #sign-container { color: #00d9ff; font-size: 5rem; text-transform: uppercase; border: 2px solid #00d9ff; padding: 20px; box-shadow: 0 0 15px #00d9ff; }\n\n        /* --- NEW THEME 5: RETRO WOOD --- */\n        body.retro { background-color: #3d2b1f; font-family: \'Special Elite\', serif; background-image: repeating-linear-gradient(90deg, transparent, transparent 40px, rgba(0,0,0,0.1) 41px); }\n        body.retro #sign-container { color: #e6b450; font-size: 5.5rem; text-shadow: 2px 2px 0px #20150d; }\n\n        /* --- NEW THEME 6: CYBERPUNK (Yellow/Black) --- */\n        body.cyber { background-color: #fcee0a; font-family: \'Orbitron\', sans-serif; }\n        body.cyber #sign-container { color: #000; font-size: 5rem; font-weight: 900; text-transform: uppercase; font-style: italic; background: #000; color: #fcee0a; padding: 10px 40px; clip-path: polygon(0% 0%, 100% 0%, 95% 100%, 5% 100%); }\n\n        /* ANIMATIONS & EFFECTS */\n        @keyframes flicker { 0%, 19%, 21%, 100% { opacity: 1; } 20% { opacity: 0.5; } }\n        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }\n        .shake { animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both; }\n        @keyframes shake { 10%, 90% { transform: translate3d(-1px, 0, 0); } 20%, 80% { transform: translate3d(2px, 0, 0); } 30%, 50%, 70% { transform: translate3d(-4px, 0, 0); } 40%, 60% { transform: translate3d(4px, 0, 0); } }\n    </style>\n</head>\n<body class="neon">\n    <div id="sign-container" contenteditable="true" spellcheck="false">ON AIR</div>\n\n    <script>\n        const container = document.getElementById(\'sign-container\');\n        \n        function updateDisplay(text, theme) {\n            container.innerText = text;\n            document.body.className = theme;\n        }\n\n        function triggerEffect(effect) {\n            if (effect === \'shake\') {\n                container.classList.add(\'shake\');\n                setTimeout(() => container.classList.remove(\'shake\'), 500);\n            }\n        }\n\n        // Notify Python on load\n        window.addEventListener(\'pywebviewready\', () => {\n            window.pywebview.api.loaded().then(state => {\n                updateDisplay(state.text, state.theme);\n            });\n        });\n\n        document.addEventListener(\'keydown\', (e) => {\n            const themes = { \'F1\': \'neon\', \'F2\': \'terminal\', \'F3\': \'chalk\', \'F4\': \'blueprint\', \'F5\': \'retro\', \'F6\': \'cyber\' };\n            if (themes[e.key]) {\n                document.body.className = themes[e.key];\n                window.pywebview.api.log_action(\'switch_theme_\' + themes[e.key]);\n            }\n        });\n    </script>\n</body>\n</html>\n'

@service_metadata(name='ChalkboardWeb', version='2.0.1', description='Integrated HTML5/CSS3 Digital Signage Engine', tags=['ui', 'webview', 'obs'], capabilities=['ui:gui'], side_effects=['ui:update'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=['webview'])
class ChalkBoardMS(BaseService):

    def __init__(self):
        super().__init__('ChalkboardWeb')
        self._window = None
        self.state = {'text': 'ON AIR', 'theme': 'neon'}

    def loaded(self):
        """Called by JS when the page is ready."""
        print('Frontend handshake complete.')
        return self.state

    def log_action(self, action_name):
        """Called by JS when user interacts."""
        print(f'Webview Event: {action_name}')

    @service_endpoint(inputs={'text': 'str', 'theme': 'str'}, outputs={}, description='Updates the embedded HTML via JS injection.', tags=['ui', 'display'])
    def update_sign(self, text: str, theme: str='neon'):
        """Updates the embedded HTML via JS injection."""
        self.state['text'] = text
        self.state['theme'] = theme
        if self._window:
            sanitized_text = json.dumps(text)
            self._window.evaluate_js(f"updateDisplay({sanitized_text}, '{theme}')")

    @service_endpoint(inputs={'effect': 'str'}, outputs={}, description="Triggers CSS animations like 'shake'.", tags=['ui', 'animation'])
    def trigger_effect(self, effect: str):
        """Triggers CSS animations like 'shake'."""
        if self._window:
            self._window.evaluate_js(f"triggerEffect('{effect}')")
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    api = ChalkBoardMS()
    print(f'Service Ready: {api}')
    window = webview.create_window('OBS Signboard v2', html=HTML_CONTENT, js_api=api, width=1000, height=700, background_color='#000000')
    api._window = window
    webview.start(debug=True)
```

---

## FILE: `.microservice-library/services/_ChunkingRouterMS.py`

```python
"""
SERVICE_NAME: _ChunkingRouterMS
ENTRY_POINT: _ChunkingRouterMS.py
INTERNAL_DEPENDENCIES: _PythonChunkerMS, base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import re
from typing import Any, Dict, List, Optional
from microservice_std_lib import service_metadata, service_endpoint
from base_service import BaseService
import time
try:
    from _PythonChunkerMS import PythonChunkerMS, CodeChunk
except ImportError:

    class CodeChunk:

        def __init__(self, name, type, content, start_line, end_line):
            self.name = name
            self.type = type
            self.content = content
            self.start_line = start_line
            self.end_line = end_line

        def __repr__(self):
            return f'<CodeChunk {self.name}>'

    class PythonChunkerMS:

        def chunk(self, text):
            return [CodeChunk('mock', 'text', text, 0, 0)]

@service_metadata(name='ChunkingRouterMS', version='1.1.0', description='The Dispatcher: Routes files to specialized chunkers based on extension (AST for Python, Recursive for Prose).', tags=['orchestration', 'chunking', 'nlp'], capabilities=['routing', 'text-processing'], side_effects=[], internal_dependencies=['_PythonChunkerMS', 'base_service', 'microservice_std_lib'], external_dependencies=[])
class ChunkingRouterMS(BaseService):
    """
    The Editor: A 'Recursive' text splitter.
    It respects the natural structure of text (Paragraphs -> Sentences -> Words)
    rather than just hacking it apart by character count.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('ChunkingRouterMS')
        self.config = config or {}
        self.python_specialist = PythonChunkerMS()
        self.separators = ['\n\n', '\n', '(?<=[.?!])\\s+', ' ', '']

    @service_endpoint(inputs={'text': 'str', 'filename': 'str', 'max_size': 'int', 'overlap': 'int'}, outputs={'chunks': 'list'}, description='Routes text to the appropriate specialist. Returns a list of CodeChunk objects or raw strings.', tags=['routing', 'chunking'])
    def chunk_file(self, text: str, filename: str, max_size: int=1000, overlap: int=100) -> List[Any]:
        """
        Extension-aware router.
        """
        if filename.endswith('.py'):
            return self.python_specialist.chunk(text)
        raw_chunks = self._recursive_split(text, self.separators, max_size, overlap)
        return [CodeChunk(name=f'prose_chunk_{i}', type='text', content=c, start_line=0, end_line=0) for i, c in enumerate(raw_chunks)]

    def _recursive_split(self, text: str, separators: List[str], max_size: int, overlap: int) -> List[str]:
        final_chunks = []
        if len(text) <= max_size:
            return [text]
        if not separators:
            return self._hard_split(text, max_size, overlap)
        current_sep = separators[0]
        next_separators = separators[1:]
        if len(current_sep) > 1 and '(' in current_sep:
            splits = re.split(current_sep, text)
        else:
            splits = text.split(current_sep)
        current_doc = []
        current_length = 0
        for split in splits:
            if not split:
                continue
            if len(split) > max_size:
                if current_doc:
                    final_chunks.append(current_sep.join(current_doc))
                    current_doc = []
                    current_length = 0
                sub_chunks = self._recursive_split(split, next_separators, max_size, overlap)
                final_chunks.extend(sub_chunks)
                continue
            if current_length + len(split) + len(current_sep) > max_size:
                doc_text = current_sep.join(current_doc)
                final_chunks.append(doc_text)
                current_doc = [split]
                current_length = len(split)
            else:
                current_doc.append(split)
                current_length += len(split) + len(current_sep)
        if current_doc:
            final_chunks.append(current_sep.join(current_doc))
        return final_chunks

    def _hard_split(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Last resort: naive character sliding window."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    chunker = ChunkingRouterMS()
    print(f'Service ready: {chunker}')
    doc = '\n    # Intro to AI\n    Artificial Intelligence is great.\n    It helps us code.\n    \n    ## How it works\n    1. Ingestion: Reading data.\n    2. Processing: Thinking about data.\n    This is a very long paragraph that effectively serves as a stress test for the sentence splitter.\n    It should hopefully not break in the middle of a thought! We want to keep sentences whole.\n    '
    print('--- Testing Smart Chunking (Max 60 chars) ---')
    chunks = chunker.chunk_file(doc, 'test.md', max_size=60, overlap=0)
    for i, c in enumerate(chunks):
        print(f'[{i}] {repr(c)}')
```

---

## FILE: `.microservice-library/services/_CodeChunkerMS.py`

```python
"""
SERVICE_NAME: _CodeChunkerMS
ENTRY_POINT: _CodeChunkerMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from microservice_std_lib import service_metadata, service_endpoint, BaseService
import time

@service_metadata(name='CodeChunker', version='1.0.0', description='Splits code into semantic blocks (Classes, Functions) using indentation and regex heuristics.', tags=['parsing', 'chunking', 'code'], capabilities=['filesystem:read'], side_effects=['filesystem:read'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=[])
class CodeChunkerMS(BaseService):
    """
    The Surgeon (Pure Python Edition): Splits code into semantic blocks
    (Classes, Functions) using indentation and regex heuristics.
    
    Advantages: Zero dependencies. Works on any machine.
    Disadvantages: Slightly less precise than Tree-Sitter for messy code.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('CodeChunker')
        self.config = config or {}
        self.def_pattern = re.compile('^(\\s*)(?:async\\s+)?(?:class|def|function|func|var|const)\\s+([a-zA-Z0-9_]+)', re.MULTILINE)

    @service_endpoint(inputs={'file_path': 'str', 'max_chars': 'int'}, outputs={'chunks': 'List[Dict]'}, description='Reads a file and breaks it into logical blocks based on indentation.', tags=['parsing', 'chunking'], side_effects=['filesystem:read'])
    def chunk_file(self, file_path: str, max_chars: int=1500) -> List[Dict[str, Any]]:
        """
        Reads a file and breaks it into logical blocks based on indentation.
        """
        path = Path(file_path)
        try:
            code = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f'Error reading {file_path}: {e}')
            return []
        return self._chunk_by_indentation(code, max_chars)

    def _chunk_by_indentation(self, code: str, max_chars: int) -> List[Dict]:
        lines = code.splitlines()
        chunks = []
        current_chunk_lines = []
        current_start_line = 0
        current_indent = 0
        in_block = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped and (not in_block):
                continue
            indent_match = re.match('^(\\s*)', line)
            indent_level = len(indent_match.group(1)) if indent_match else 0
            match = self.def_pattern.match(line)
            is_def = match is not None and indent_level <= 4
            if is_def and current_chunk_lines:
                self._finalize_chunk(chunks, current_chunk_lines, current_start_line, max_chars)
                current_chunk_lines = []
                current_start_line = i + 1
                in_block = True
                current_indent = indent_level
            if in_block and stripped and (indent_level <= current_indent) and (not is_def):
                if not stripped.startswith('}'):
                    self._finalize_chunk(chunks, current_chunk_lines, current_start_line, max_chars)
                    current_chunk_lines = []
                    current_start_line = i + 1
                    in_block = False
            current_chunk_lines.append(line)
        if current_chunk_lines:
            self._finalize_chunk(chunks, current_chunk_lines, current_start_line, max_chars)
        return chunks

    def _finalize_chunk(self, chunks, lines, start_line, max_chars):
        """Recursively splits huge chunks if they exceed max_chars."""
        full_text = '\n'.join(lines)
        if not full_text.strip():
            return
        if len(full_text) > max_chars:
            self._split_large_block(chunks, lines, start_line, max_chars)
        else:
            chunks.append({'type': 'block', 'text': full_text, 'start_line': start_line, 'end_line': start_line + len(lines)})

    def _split_large_block(self, chunks, lines, start_line, max_chars):
        """Force split a large block while keeping line boundaries."""
        current_sub = []
        current_len = 0
        sub_start = start_line
        for i, line in enumerate(lines):
            if current_len + len(line) > max_chars:
                if current_sub:
                    chunks.append({'type': 'fragment', 'text': '\n'.join(current_sub), 'start_line': sub_start, 'end_line': sub_start + len(current_sub)})
                current_sub = []
                current_len = 0
                sub_start = start_line + i
            current_sub.append(line)
            current_len += len(line)
        if current_sub:
            chunks.append({'type': 'fragment', 'text': '\n'.join(current_sub), 'start_line': sub_start, 'end_line': sub_start + len(current_sub)})
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    chunker = CodeChunkerMS()
    print(f'Service ready: {chunker}')
    py_code = '\nimport os\n\ndef small_helper():\n    return True\n\nclass DataProcessor:\n    def __init__(self):\n        self.data = []\n\n    def process(self, raw_input):\n        # This is a comment inside the function\n        if raw_input:\n            self.data.append(raw_input)\n        return True\n    '
    with tempfile.NamedTemporaryFile(suffix='.py', mode='w+', delete=False) as tmp:
        tmp.write(py_code)
        tmp_path = tmp.name
    try:
        print(f'--- Chunking {tmp_path} (Pure Python) ---')
        chunks = chunker.chunk_file(tmp_path)
        for i, c in enumerate(chunks):
            print(f"\n[Chunk {i}] Lines {c['start_line']}-{c['end_line']}")
            print(f"{'-' * 20}\n{c['text'].strip()}\n{'-' * 20}")
    finally:
        os.remove(tmp_path)
```

---

## FILE: `.microservice-library/services/_CodeFormatterMS.py`

```python
"""
SERVICE_NAME: _CodeFormatterMS
ENTRY_POINT: _CodeFormatterMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
logger = logging.getLogger('CodeFormatter')

class WhitespaceEngine:
    """
    Parses code into a granular map of (Indent + Content + Trailing).
    Can Normalize structure and generate 'Hunk' patches.
    """

    def __init__(self):
        self.raw_lines = []
        self.nodes = []
        self.normalized_text = ''
        self.patch_data = {'hunks': []}

    def load_source(self, text):
        self.raw_lines = text.splitlines()
        self.nodes = []
        indent_stack = [0]
        last_line_was_block_starter = False
        for i, line in enumerate(self.raw_lines):
            match = re.match('^([ \\t]*)(.*?)([ \\t]*)$', line)
            if not match:
                self.nodes.append({'id': i, 'indent': '', 'content': line, 'depth': 0, 'is_empty': True})
                continue
            indent, content, trailing = match.groups()
            is_empty = len(content) == 0
            current_width = 0
            for char in indent:
                current_width += 4 if char == '\t' else 1
            if is_empty:
                depth = len(indent_stack) - 1
            else:
                if current_width > indent_stack[-1]:
                    if last_line_was_block_starter:
                        indent_stack.append(current_width)
                    else:
                        pass
                while len(indent_stack) > 1 and current_width < indent_stack[-1]:
                    indent_stack.pop()
                depth = len(indent_stack) - 1
                clean_content = content.split('#')[0].strip()
                last_line_was_block_starter = clean_content.endswith(':')
            self.nodes.append({'id': i, 'raw_indent': indent, 'depth': depth, 'content': content, 'trailing': trailing, 'is_empty': is_empty})

    def normalize(self, use_tabs=False, space_count=4):
        """Reconstructs the code with strict indentation rules."""
        char = '\t' if use_tabs else ' ' * space_count
        clean_lines = []
        for node in self.nodes:
            if node['is_empty']:
                clean_lines.append('')
            else:
                new_indent = char * node['depth']
                clean_lines.append(f"{new_indent}{node['content']}")
        self.normalized_text = '\n'.join(clean_lines)
        return self.normalized_text

    def generate_patch(self):
        """Compares Raw vs Normalized and generates JSON Schema Hunks."""
        clean_lines = self.normalized_text.splitlines()
        if not clean_lines:
            return {'hunks': []}
        hunks = []
        current_hunk = None
        for i, (raw, clean) in enumerate(zip(self.raw_lines, clean_lines)):
            if raw != clean:
                if current_hunk is None:
                    current_hunk = {'start_line': i, 'raw_block': [raw], 'clean_block': [clean]}
                elif i == current_hunk['start_line'] + len(current_hunk['raw_block']):
                    current_hunk['raw_block'].append(raw)
                    current_hunk['clean_block'].append(clean)
                else:
                    self._finalize_hunk(hunks, current_hunk)
                    current_hunk = {'start_line': i, 'raw_block': [raw], 'clean_block': [clean]}
            elif current_hunk:
                self._finalize_hunk(hunks, current_hunk)
                current_hunk = None
        if current_hunk:
            self._finalize_hunk(hunks, current_hunk)
        self.patch_data = {'hunks': hunks}
        return self.patch_data

    def _finalize_hunk(self, hunks_list, hunk_data):
        search_txt = '\n'.join(hunk_data['raw_block'])
        replace_txt = '\n'.join(hunk_data['clean_block'])
        schema_hunk = {'description': f"Normalize indentation (Lines {hunk_data['start_line']}-{hunk_data['start_line'] + len(hunk_data['raw_block'])})", 'search_block': search_txt, 'replace_block': replace_txt}
        hunks_list.append(schema_hunk)


@service_metadata(name='CodeFormatter', version='1.0.0', description='The Architect: Intelligent whitespace normalization and structural repair engine.', tags=['formatting', 'code', 'utility'], capabilities=['compute', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['filesystem:read', 'filesystem:write'])
class CodeFormatterMS:
    """
    The Architect.
    Uses the WhitespaceEngine to enforce strict indentation rules, 
    fixing 'staircase' formatting and mixed tabs/spaces.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'content': 'str', 'use_tabs': 'bool', 'spaces': 'int'}, outputs={'normalized': 'str', 'patch': 'Dict'}, description='Takes raw code and returns the normalized version plus a JSON patch of changes.', tags=['formatting', 'compute'], side_effects=[])
    def normalize_code(self, content: str, use_tabs: bool=False, spaces: int=4) -> Dict[str, Any]:
        """
        Pure logic endpoint: Takes string, returns string + patch.
        Does not touch the filesystem.
        """
        engine = WhitespaceEngine()
        engine.load_source(content)
        normalized = engine.normalize(use_tabs=use_tabs, space_count=spaces)
        patch = engine.generate_patch()
        return {'normalized': normalized, 'patch': patch}

    @service_endpoint(inputs={'file_path': 'str', 'use_tabs': 'bool', 'spaces': 'int'}, outputs={'status': 'str', 'changes': 'int'}, description='Reads a file, normalizes it, and overwrites it if changes are needed.', tags=['formatting', 'filesystem'], side_effects=['filesystem:read', 'filesystem:write'])
    def format_file(self, file_path: str, use_tabs: bool=False, spaces: int=4) -> Dict[str, Any]:
        """
        Filesystem endpoint: In-place repair of a file.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            return {'status': 'error', 'message': 'File not found'}
        try:
            content = path.read_text(encoding='utf-8')
            engine = WhitespaceEngine()
            engine.load_source(content)
            normalized = engine.normalize(use_tabs=use_tabs, space_count=spaces)
            patch = engine.generate_patch()
            changes = len(patch['hunks'])
            if changes > 0:
                path.write_text(normalized, encoding='utf-8')
                logger.info(f'Formatted {path.name}: {changes} hunks applied.')
                return {'status': 'modified', 'changes': changes}
            else:
                return {'status': 'clean', 'changes': 0}
        except Exception as e:
            logger.error(f'Formatting failed for {path}: {e}')
            return {'status': 'error', 'message': str(e)}
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    svc = CodeFormatterMS()
    print('Service ready:', svc)
    broken_code = '\ndef hello():\n  print("Indented with 2 spaces")\n      print("Suddenly 6 spaces!")\n    '
    print('\n--- Processing Broken Code ---')
    result = svc.normalize_code(broken_code, spaces=4)
    print(f"Hunks Detected: {len(result['patch']['hunks'])}")
    print('\n--- Normalized Output ---')
    print(result['normalized'])
```

---

## FILE: `.microservice-library/services/_CodeGrapherMS.py`

```python
"""
SERVICE_NAME: _CodeGrapherMS
ENTRY_POINT: _CodeGrapherMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import ast
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from microservice_std_lib import service_metadata, service_endpoint, BaseService
import time

class SurgicalVisitor(ast.NodeVisitor):
    """
    Extracts function definitions, calls, and class structures from AST.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols = []

    def visit_FunctionDef(self, node):
        self._handle_func(node, 'function')

    def visit_AsyncFunctionDef(self, node):
        self._handle_func(node, 'async_function')

    def visit_ClassDef(self, node):
        class_id = f'{self.file_path}::{node.name}'
        self.symbols.append({'id': class_id, 'file': self.file_path, 'name': node.name, 'type': 'class', 'line': node.lineno, 'calls': []})
        self.generic_visit(node)

    def _handle_func(self, node, type_name):
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        unique_calls = list(set(calls))
        node_id = f'{self.file_path}::{node.name}'
        self.symbols.append({'id': node_id, 'file': self.file_path, 'name': node.name, 'type': type_name, 'line': node.lineno, 'calls': unique_calls})


@service_metadata(name='CodeGrapher', version='1.0.0', description='Parses Python code to extract symbols (nodes) and call relationships (edges).', tags=['parsing', 'graph', 'analysis'], capabilities=['filesystem:read'], side_effects=['filesystem:read'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=[])
class CodeGrapherMS(BaseService):
    """
    The Cartographer of Logic: Parses Python code to extract high-level 
    symbols (classes, functions) and maps their 'Call' relationships.
    
    Output: A graph structure (Nodes + Edges) suitable for visualization 
    or dependency analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('CodeGrapher')
        self.config = config or {}
        self.nodes = []
        self.edges = []

    @service_endpoint(inputs={'root_path': 'str'}, outputs={'graph_data': 'Dict[str, Any]'}, description='Recursively scans a directory for .py files and builds the graph.', tags=['parsing', 'graph'], side_effects=['filesystem:read'])
    def scan_directory(self, root_path: str) -> Dict[str, Any]:
        """
        Recursively scans a directory for .py files and builds the graph.
        """
        root = Path(root_path).resolve()
        self.nodes = []
        self.edges = []
        if not root.exists():
            return {'error': f'Path {root} does not exist'}
        for path in root.rglob('*.py'):
            try:
                if any((p.startswith('.') for p in path.parts)) or 'venv' in path.parts:
                    continue
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    source = f.read()
                rel_path = str(path.relative_to(root)).replace('\\', '/')
                file_symbols = self._parse_source(source, rel_path)
                self.nodes.extend(file_symbols)
            except Exception as e:
                print(f'Failed to parse {path.name}: {e}')
        self._build_edges()
        return {'root': str(root), 'node_count': len(self.nodes), 'edge_count': len(self.edges), 'nodes': self.nodes, 'edges': self.edges}

    def _parse_source(self, source: str, file_path: str) -> List[Dict]:
        """
        Uses Python's AST to extract surgical symbol info.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        visitor = SurgicalVisitor(file_path)
        visitor.visit(tree)
        return visitor.symbols

    def _build_edges(self):
        """
        Resolves 'calls' strings into explicit graph edges.
        """
        name_map = {n['name']: n['id'] for n in self.nodes}
        for node in self.nodes:
            source_id = node['id']
            calls = node.get('calls', [])
            for target_name in calls:
                if target_name in name_map:
                    target_id = name_map[target_name]
                    if source_id != target_id:
                        self.edges.append({'source': source_id, 'target': target_id, 'type': 'calls'})
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    target_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f'Mapping Logic in: {target_dir}')
    grapher = CodeGrapherMS()
    print(f'Service Ready: {grapher}')
    graph_data = grapher.scan_directory(target_dir)
    print(f'\n--- Scan Complete ---')
    print(f"Nodes Found: {graph_data.get('node_count', 0)}")
    print(f"Edges Built: {graph_data.get('edge_count', 0)}")
    out_file = 'code_graph_dump.json'
    with open(out_file, 'w') as f:
        json.dump(graph_data, f, indent=2)
    print(f'Graph saved to {out_file}')
```

---

## FILE: `.microservice-library/services/_CodeJanitorMS.py`

```python
"""
SERVICE_NAME: _CodeJanitorMS
ENTRY_POINT: _CodeJanitorMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
logger = logging.getLogger('CodeJanitor')
RENAME_MAP = {'__AppShellMS': '_TkinterAppShellMS', '_AppShellMS': '_TkinterAppShellMS', '__ThemeManagerMS': '_TkinterThemeManagerMS', '_ThemeManagerMS': '_TkinterThemeManagerMS', '__SmartExplorerMS': '_TkinterSmartExplorerMS', '_SmartExplorerMS': '_TkinterSmartExplorerMS', '__UniButtonMS': '_TkinterUniButtonMS', '_UniButtonMS': '_TkinterUniButtonMS'}

@service_metadata(name='CodeJanitor', version='2.2.0', description='Fast version: Skips backup, high verbosity.', tags=['maintenance'], capabilities=['filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class CodeJanitorMS:

    def __init__(self):
        self.root = Path('.').resolve()

    def enforce_standards(self, dry_run: bool=True):
        print(f"--- 🧹 JANITOR STARTED in {('DRY RUN' if dry_run else 'LIVE')} MODE ---")
        files = list(self.root.glob('*.py'))
        print(f'Found {len(files)} Python files to scan.\n')
        generic_import = re.compile('(from|import)\\s+__([A-Z])')
        generic_string = re.compile('["\\\']__([A-Z]\\w+MS)["\\\']')
        entry_point = re.compile('ENTRY_POINT:\\s*__([A-Z]\\w+MS\\.py)')
        for file_path in files:
            if file_path.name == '_CodeJanitorMS.py':
                continue
            try:
                original = file_path.read_text(encoding='utf-8')
                new = original
                new = entry_point.sub('ENTRY_POINT: _\\1', new)
                for old_name, new_name in RENAME_MAP.items():
                    pattern = re.compile(f'\\b{old_name}\\b')
                    if pattern.search(new):
                        new = pattern.sub(new_name, new)
                new = generic_import.sub('\\1 _\\2', new)
                new = generic_string.sub('"_\\1"', new)
                if new != original:
                    print(f'🛠️  PATCHING: {file_path.name}')
                    if not dry_run:
                        file_path.write_text(new, encoding='utf-8')
                else:
                    pass
            except Exception as e:
                print(f'❌ ERROR {file_path.name}: {e}')
        print('\n--- 🏁 JANITOR FINISHED ---')

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    janitor = CodeJanitorMS()
    janitor.enforce_standards(dry_run=False)
```

---

## FILE: `.microservice-library/services/_CognitiveMemoryMS.py`

```python
"""
SERVICE_NAME: _CognitiveMemoryMS
ENTRY_POINT: _CognitiveMemoryMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: pydantic
"""
import importlib.util
import sys
import time
REQUIRED = ['pydantic']
MISSING = []
for lib in REQUIRED:
    if importlib.util.find_spec(lib) is None:
        MISSING.append(lib)
if MISSING:
    print(f"MISSING DEPENDENCIES: {' '.join(MISSING)}")
    print('Please run: pip install pydantic')
import datetime
import json
import logging
import uuid
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from microservice_std_lib import service_metadata, service_endpoint, BaseService
DEFAULT_MEMORY_FILE = Path('working_memory.jsonl')
FLUSH_THRESHOLD = 5
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('CognitiveMem')

class MemoryEntry(BaseModel):
    """Atomic unit of memory."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


@service_metadata(name='CognitiveMemory', version='1.0.0', description='Manages Short-Term (Working) Memory and orchestrates flushing to Long-Term Memory.', tags=['memory', 'history', 'context'], capabilities=['filesystem:read', 'filesystem:write'], side_effects=['filesystem:write'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=['pydantic'])
class CognitiveMemoryMS(BaseService):
    """
    The Hippocampus: Manages Short-Term (Working) Memory and orchestrates 
    flushing to Long-Term Memory (Vector Store).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('CognitiveMemory')
        self.config = config or {}
        self.file_path = Path(self.config.get('persistence_path', DEFAULT_MEMORY_FILE))
        self.summarizer = self.config.get('summarizer_func')
        self.ingestor = self.config.get('long_term_ingest_func')
        self.working_memory: List[MemoryEntry] = []
        self._load_working_memory()

    @service_endpoint(inputs={'role': 'str', 'content': 'str', 'metadata': 'Dict'}, outputs={'entry': 'MemoryEntry'}, description='Adds an item to working memory and persists it.', tags=['memory', 'write'], side_effects=['filesystem:write'])
    def add_entry(self, role: str, content: str, metadata: Dict=None) -> MemoryEntry:
        """Adds an item to working memory and persists it."""
        entry = MemoryEntry(role=role, content=content, metadata=metadata or {})
        self.working_memory.append(entry)
        self._append_to_file(entry)
        log.info(f'Added memory: [{role}] {content[:30]}...')
        return entry

    @service_endpoint(inputs={'limit': 'int'}, outputs={'context': 'str'}, description='Returns the most recent conversation history formatted for an LLM.', tags=['memory', 'read', 'llm'], side_effects=['filesystem:read'])
    def get_context(self, limit: int=10) -> str:
        """
        Returns the most recent conversation history formatted for an LLM.
        """
        recent = self.working_memory[-limit:]
        return '\n'.join([f'{e.role.upper()}: {e.content}' for e in recent])

    def get_full_history(self) -> List[Dict]:
        """Returns the raw list of memory objects."""
        return [e.dict() for e in self.working_memory]

    @service_endpoint(inputs={}, outputs={}, description='Signals that a turn is complete; checks if memory flush is needed.', tags=['memory', 'maintenance'], side_effects=['filesystem:write'])
    def commit_turn(self):
        """
        Signal that a "Turn" (User + AI response) is complete.
        Checks if memory is full and triggers a flush if needed.
        """
        if len(self.working_memory) >= FLUSH_THRESHOLD:
            self._flush_to_long_term()

    def _flush_to_long_term(self):
        """
        Compresses working memory into a summary and moves it to Long-Term storage.
        """
        if not self.summarizer or not self.ingestor:
            log.warning('Flush triggered but Summarizer/Ingestor not configured. Skipping.')
            return
        log.info('🌀 Flushing Working Memory to Long-Term Storage...')
        full_text = '\n'.join([f'{e.role}: {e.content}' for e in self.working_memory])
        try:
            summary = self.summarizer(full_text)
            log.info(f'Summary generated: {summary[:50]}...')
        except Exception as e:
            log.error(f'Summarization failed: {e}')
            return
        try:
            meta = {'source': 'cognitive_memory_flush', 'date': datetime.datetime.utcnow().isoformat(), 'original_entry_count': len(self.working_memory)}
            self.ingestor(summary, meta)
            log.info('✅ Saved to Long-Term Memory.')
        except Exception as e:
            log.error(f'Ingestion failed: {e}')
            return
        self.working_memory.clear()
        self._rotate_log_file()

    def _load_working_memory(self):
        """Rehydrates memory from the JSONL file."""
        if not self.file_path.exists():
            return
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        self.working_memory.append(MemoryEntry.parse_raw(line))
            log.info(f'Loaded {len(self.working_memory)} items from {self.file_path}')
        except Exception as e:
            log.error(f'Corrupt memory file: {e}')

    def _append_to_file(self, entry: MemoryEntry):
        """Appends a single entry to the JSONL log."""
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(entry.json() + '\n')

    def _rotate_log_file(self):
        """Renames the current log to an archive timestamp."""
        if self.file_path.exists():
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = self.file_path.with_name(f'memory_archive_{timestamp}.jsonl')
            self.file_path.rename(archive_name)
            log.info(f'Rotated memory log to {archive_name}')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':

    def mock_summarizer(text):
        return f'SUMMARY OF {len(text)} CHARS: The user and AI discussed AI architecture.'

    def mock_ingest(text, metadata):
        print(f"\n[VectorDB] Indexing: '{text}'\n[VectorDB] Meta: {metadata}")
    print('--- Initializing Cognitive Memory ---')
    mem = CognitiveMemoryMS({'summarizer_func': mock_summarizer, 'long_term_ingest_func': mock_ingest})
    print(f'Service ready: {mem}')
    print('\n--- Simulating Conversation ---')
    mem.add_entry('user', 'Hello, who are you?')
    mem.add_entry('assistant', 'I am a Cognitive Agent.')
    mem.add_entry('user', 'What is your memory capacity?')
    mem.add_entry('assistant', 'I have a tiered memory system.')
    mem.add_entry('user', 'That sounds complex.')
    print(f'\nCurrent Context:\n{mem.get_context()}')
    print('\n--- Triggering Memory Flush ---')
    mem.commit_turn()
    print(f'\nWorking Memory after flush: {len(mem.working_memory)} items')
    if Path('working_memory.jsonl').exists():
        os.remove('working_memory.jsonl')
    for p in Path('.').glob('memory_archive_*.jsonl'):
        os.remove(p)
```

---

## FILE: `.microservice-library/services/_ContentExtractorMS.py`

```python
"""
SERVICE_NAME: _ContentExtractorMS
ENTRY_POINT: _ContentExtractorMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: beautifulsoup4, bs4, pypdf
"""
import io
import re
import time
from typing import Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint

@service_metadata(name='ContentExtractorMS', version='1.0.0', description='The Decoder: A specialist service for extracting clean text from complex formats like PDF and HTML.', tags=['utility', 'extraction', 'nlp'], capabilities=['pdf-to-text', 'html-cleaning'], side_effects=['filesystem:read'], internal_dependencies=['microservice_std_lib'], external_dependencies=['beautifulsoup4', 'bs4', 'pypdf'])
class ContentExtractorMS:
    """
    The Decoder.
    A standalone utility microservice that separates the concern of 
    document parsing from ingestion logic.
    """

    def __init__(self):
        self.start_time = time.time()
        self._pdf_ready = False
        try:
            from pypdf import PdfReader
            self._pdf_ready = True
        except ImportError:
            pass
        self._html_ready = False
        try:
            from bs4 import BeautifulSoup
            self._html_ready = True
        except ImportError:
            pass

    @service_endpoint(inputs={}, outputs={'status': 'str', 'pdf_support': 'bool', 'html_support': 'bool'}, description='Health check to verify which extraction backends are installed.', tags=['diagnostic', 'health'])
    def get_health(self) -> Dict[str, Any]:
        """Returns the operational status and library availability."""
        return {'status': 'online', 'uptime': time.time() - self.start_time, 'pdf_support': self._pdf_ready, 'html_support': self._html_ready}

    @service_endpoint(inputs={'blob': 'bytes', 'mime_type': 'str'}, outputs={'text': 'str'}, description='Unified entry point for text extraction. Routes to the correct parser based on mime_type.', tags=['processing', 'extraction'])
    def extract_text(self, blob: bytes, mime_type: str) -> str:
        """
        Main routing logic for extraction. 
         logic is internalized here.
        """
        if 'pdf' in mime_type.lower():
            return self._extract_pdf(blob)
        elif 'html' in mime_type.lower():
            try:
                html_content = blob.decode('utf-8', errors='ignore')
                return self._extract_html(html_content)
            except:
                return ''
        return ''

    def _extract_pdf(self, file_bytes: bytes) -> str:
        """Extracts text from a PDF blob using pypdf. [cite: 96-97]"""
        if not self._pdf_ready:
            return ''
        from pypdf import PdfReader
        text_content = []
        try:
            stream = io.BytesIO(file_bytes)
            reader = PdfReader(stream)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content.append(extracted)
            return '\n'.join(text_content)
        except Exception as e:
            return f'PDF Extraction Error: {e}'

    def _extract_html(self, html_content: str) -> str:
        """Cleans HTML to raw text using BeautifulSoup. [cite: 98-99]"""
        if not self._html_ready:
            return self._strip_tags_regex(html_content)
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(['script', 'style', 'meta', 'noscript']):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split('  '))
            return '\n'.join((chunk for chunk in chunks if chunk))
        except Exception:
            return self._strip_tags_regex(html_content)

    def _strip_tags_regex(self, html: str) -> str:
        """Fallback if BS4 is missing. [cite: 100]"""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html)
if __name__ == '__main__':
    svc = ContentExtractorMS()
    print('Service ready:', svc._service_info['name'])
    print('Health:', svc.get_health())
```

---

## FILE: `.microservice-library/services/_ContextAggregatorMS.py`

```python
"""
SERVICE_NAME: _ContextAggregatorMS
ENTRY_POINT: _ContextAggregatorMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import os
import fnmatch
import datetime
import logging
from pathlib import Path
from typing import Set, Optional, Dict, Any
from microservice_std_lib import service_metadata, service_endpoint
import time
DEFAULT_BINARY_EXTENSIONS = {'.tar.gz', '.gz', '.zip', '.rar', '.7z', '.bz2', '.xz', '.tgz', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.tif', '.tiff', '.mp3', '.wav', '.ogg', '.flac', '.mp4', '.mkv', '.avi', '.mov', '.webm', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.exe', '.dll', '.so', '.db', '.sqlite', '.mdb', '.pyc', '.pyo', '.class', '.jar', '.wasm'}
DEFAULT_IGNORE_DIRS = {'node_modules', '.git', '__pycache__', '.venv', '.env', 'dist', 'build', 'coverage', '.idea', '.vscode'}
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('ContextAggregator')

@service_metadata(name='ContextAggregator', version='1.0.0', description='Flattens a project folder into a single readable text file.', tags=['filesystem', 'context', 'compilation'], capabilities=['filesystem:read', 'filesystem:write'], side_effects=['filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[])
class ContextAggregatorMS:
    """
    The Context Builder: Flattens a project folder into a single readable text file.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        max_file_size_mb = self.config.get('max_file_size_mb', 1)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    @service_endpoint(inputs={'root_path': 'str', 'output_file': 'str', 'extra_exclusions': 'Set[str]', 'use_default_exclusions': 'bool'}, outputs={'file_count': 'int'}, description='Aggregates project files into a single text dump.', tags=['filesystem', 'dump'], side_effects=['filesystem:read', 'filesystem:write'])
    def aggregate(self, root_path: str, output_file: str, extra_exclusions: Optional[Set[str]]=None, use_default_exclusions: bool=True) -> int:
        project_root = Path(root_path).resolve()
        out_path = Path(output_file).resolve()
        exclusions = set()
        if use_default_exclusions:
            exclusions.update(DEFAULT_IGNORE_DIRS)
        if extra_exclusions:
            exclusions.update(extra_exclusions)
        binary_exts = DEFAULT_BINARY_EXTENSIONS.copy()
        file_count = 0
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(out_path, 'w', encoding='utf-8') as out_f:
                out_f.write(f"File Dump from Project: {project_root.name}\nGenerated: {timestamp}\n{'=' * 60}\n\n")
                for root, dirs, files in os.walk(project_root):
                    dirs[:] = [d for d in dirs if d not in exclusions]
                    for filename in files:
                        if self._should_exclude(filename, exclusions):
                            continue
                        file_path = Path(root) / filename
                        if file_path.resolve() == out_path:
                            continue
                        if self._is_safe_to_dump(file_path, binary_exts):
                            self._write_file_content(out_f, file_path, project_root)
                            file_count += 1
        except IOError as e:
            log.error(f'Error writing dump: {e}')
        return file_count

    def _should_exclude(self, filename: str, exclusions: Set[str]) -> bool:
        return any((fnmatch.fnmatch(filename, pattern) for pattern in exclusions))

    def _is_safe_to_dump(self, file_path: Path, binary_exts: Set[str]) -> bool:
        if ''.join(file_path.suffixes).lower() in binary_exts:
            return False
        try:
            if file_path.stat().st_size > self.max_file_size_bytes:
                return False
            with open(file_path, 'rb') as f:
                if b'\x00' in f.read(1024):
                    return False
        except (IOError, OSError):
            return False
        return True

    def _write_file_content(self, out_f, file_path: Path, project_root: Path):
        relative_path = file_path.relative_to(project_root)
        header = f"\n{'-' * 20} FILE: {relative_path} {'-' * 20}\n"
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as in_f:
                out_f.write(header + in_f.read() + f"\n{'-' * 60}\n")
        except Exception as e:
            out_f.write(f'\n[Error reading file: {e}]\n')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    svc = ContextAggregatorMS()
    print('Service ready:', svc)
```

---

## FILE: `.microservice-library/services/_ContextPackerMS.py`

```python
"""
SERVICE_NAME: _ContextPackerMS
ENTRY_POINT: _ContextPackerMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from microservice_std_lib import service_metadata, service_endpoint
import time
DEFAULT_EXCLUDES = {'.git', '__pycache__', '.idea', '.vscode', 'node_modules', 'venv', '.venv', 'dist', 'build', '.DS_Store', 'file-dump.txt'}
logger = logging.getLogger('ContextPacker')

@service_metadata(name='ContextPacker', version='1.0.0', description='Flattens a directory of source code into a single text file (useful for LLM context stuffing).', tags=['filesystem', 'export', 'utility'], capabilities=['filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['filesystem:read', 'filesystem:write'])
class ContextPackerMS:
    """
    The Packer: Walks a directory and dumps all text-readable files 
    into a single monolithic text file with delimiters.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'root_path': 'str', 'output_filename': 'str', 'additional_excludes': 'Set[str]'}, outputs={'output_path': 'str', 'file_count': 'int'}, description='Packs directory contents into a single text file.', tags=['export', 'dump'], side_effects=['filesystem:read', 'filesystem:write'])
    def pack_directory(self, root_path: str, output_filename: str='context_dump.txt', additional_excludes: Optional[Set[str]]=None) -> Dict[str, Any]:
        """
        Walks the directory and writes file contents to the output file.
        """
        root = Path(root_path).resolve()
        output_file = root / output_filename
        excludes = DEFAULT_EXCLUDES.copy()
        if additional_excludes:
            excludes.update(additional_excludes)
        excludes.add(output_filename)
        count = 0
        logger.info(f'Packing context from {root} into {output_filename}...')
        try:
            with open(output_file, 'w', encoding='utf-8') as out_f:
                out_f.write(f'CONTEXT PACKER DUMP\n')
                out_f.write(f'SOURCE: {root}\n')
                out_f.write('=' * 60 + '\n\n')
                for current_dir, dirs, files in os.walk(root):
                    dirs[:] = [d for d in dirs if d not in excludes and (not d.startswith('.'))]
                    for file in files:
                        if file in excludes or file.startswith('.'):
                            continue
                        file_path = Path(current_dir) / file
                        self._append_file(file_path, root, out_f)
                        count += 1
            return {'output_path': str(output_file), 'file_count': count}
        except Exception as e:
            logger.error(f'Packing failed: {e}')
            raise

    def _append_file(self, file_path: Path, root: Path, out_f):
        """Helper to append a single file's content to the dump."""
        rel_path = file_path.relative_to(root)
        try:
            content = file_path.read_text(encoding='utf-8')
            out_f.write(f'==================================================\n')
            out_f.write(f'FILE: {rel_path}\n')
            out_f.write(f'==================================================\n')
            out_f.write(content + '\n\n')
        except UnicodeDecodeError:
            out_f.write(f'==================================================\n')
            out_f.write(f'FILE: {rel_path} [SKIPPED - BINARY]\n')
            out_f.write(f'==================================================\n\n')
        except Exception as e:
            logger.warning(f'Could not read {rel_path}: {e}')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    packer = ContextPackerMS()
    print('Service ready:', packer)
    print('\n--- Packing Current Directory ---')
    result = packer.pack_directory('.', 'test_dump.txt')
    print(f"Packed {result['file_count']} files to: {result['output_path']}")
```

---

## FILE: `.microservice-library/services/_DiffEngineMS.py`

```python
"""
SERVICE_NAME: _DiffEngineMS
ENTRY_POINT: _DiffEngineMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import sqlite3
import difflib
import datetime
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from microservice_std_lib import service_metadata, service_endpoint
import time
DB_PATH = Path(__file__).parent / 'diff_engine.db'
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('DiffEngine')

@service_metadata(name='DiffEngineMS', version='1.0.0', description='Implements hybrid versioning (Head + Diff History) for file content.', tags=['version-control', 'diff', 'db'], capabilities=['db:sqlite', 'filesystem:write'], side_effects=['db:read', 'db:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[])
class DiffEngineMS:
    """
    The Timekeeper: Implements a 'Hybrid' versioning architecture.
    1. HEAD: Stores full current content for fast read access (UI/RAG).
    2. HISTORY: Stores diff deltas using difflib for audit trails.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.db_path = Path(self.config.get('db_path', DB_PATH))
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('\n                CREATE TABLE IF NOT EXISTS files (\n                    id TEXT PRIMARY KEY,\n                    path TEXT UNIQUE NOT NULL,\n                    content TEXT,\n                    last_updated TIMESTAMP\n                )\n            ')
            conn.execute("\n                CREATE TABLE IF NOT EXISTS diff_log (\n                    id TEXT PRIMARY KEY,\n                    file_id TEXT NOT NULL,\n                    timestamp TIMESTAMP,\n                    change_type TEXT,  -- 'CREATE', 'EDIT', 'DELETE'\n                    diff_blob TEXT,    -- The text output of difflib\n                    author TEXT,\n                    FOREIGN KEY(file_id) REFERENCES files(id)\n                )\n            ")

    @service_endpoint(inputs={'path': 'str', 'new_content': 'str', 'author': 'str'}, outputs={'status': 'str', 'file_id': 'str'}, description='Updates a file, creating a diff history entry and updating the head state.', tags=['version-control', 'write'], side_effects=['db:write'])
    def update_file(self, path: str, new_content: str, author: str='agent') -> Dict[str, Any]:
        """
        The Atomic Update Operation:
        1. Checks current state.
        2. Calculates Diff.
        3. Writes Diff to History.
        4. Updates Head to New Content.
        """
        path = str(Path(path).as_posix())
        now = datetime.datetime.utcnow()
        with self._get_conn() as conn:
            row = conn.execute('SELECT id, content FROM files WHERE path = ?', (path,)).fetchone()
            if not row:
                file_id = str(uuid.uuid4())
                conn.execute('INSERT INTO files (id, path, content, last_updated) VALUES (?, ?, ?, ?)', (file_id, path, new_content, now))
                self._log_diff(conn, file_id, 'CREATE', '[New File Created]', author, now)
                log.info(f'Created new file: {path}')
                return {'status': 'created', 'file_id': file_id}
            file_id = row['id']
            old_content = row['content'] or ''
            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff_gen = difflib.unified_diff(old_lines, new_lines, fromfile=f'a/{path}', tofile=f'b/{path}', lineterm='')
            diff_text = ''.join(diff_gen)
            if not diff_text:
                return {'status': 'unchanged', 'file_id': file_id}
            self._log_diff(conn, file_id, 'EDIT', diff_text, author, now)
            conn.execute('UPDATE files SET content = ?, last_updated = ? WHERE id = ?', (new_content, now, file_id))
            log.info(f'Updated file: {path}')
            return {'status': 'updated', 'file_id': file_id, 'diff_size': len(diff_text)}

    def _log_diff(self, conn, file_id, change_type, diff_text, author, timestamp):
        diff_id = str(uuid.uuid4())
        conn.execute('INSERT INTO diff_log (id, file_id, timestamp, change_type, diff_blob, author) VALUES (?, ?, ?, ?, ?, ?)', (diff_id, file_id, timestamp, change_type, diff_text, author))

    @service_endpoint(inputs={'path': 'str'}, outputs={'content': 'Optional[str]'}, description='Fast retrieval of current content.', tags=['version-control', 'read'], side_effects=['db:read'])
    def get_head(self, path: str) -> Optional[str]:
        """Fast retrieval of current content."""
        with self._get_conn() as conn:
            row = conn.execute('SELECT content FROM files WHERE path = ?', (path,)).fetchone()
            return row['content'] if row else None

    @service_endpoint(inputs={'path': 'str'}, outputs={'history': 'List[Dict]'}, description='Retrieves the full evolution history of a file.', tags=['version-control', 'read'], side_effects=['db:read'])
    def get_history(self, path: str) -> List[Dict]:
        """Retrieves the full evolution history of a file."""
        with self._get_conn() as conn:
            row = conn.execute('SELECT id FROM files WHERE path = ?', (path,)).fetchone()
            if not row:
                return []
            rows = conn.execute('SELECT timestamp, change_type, diff_blob, author FROM diff_log WHERE file_id = ? ORDER BY timestamp DESC', (row['id'],)).fetchall()
            return [dict(r) for r in rows]
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import os
    if DB_PATH.exists():
        os.remove(DB_PATH)
    engine = DiffEngineMS()
    print('Service ready:', engine)
    print('--- 1. Creating File ---')
    engine.update_file('notes.txt', 'Todo List:\n1. Buy Milk\n')
    print('\n--- 2. Updating File (The Rising Edge) ---')
    new_text = 'Todo List:\n1. Buy Eggs\n2. Code Python\n'
    res = engine.update_file('notes.txt', new_text, author='Jacob')
    print(f"Update Result: {res['status']}")
    print('\n--- 3. Inspecting History ---')
    history = engine.get_history('notes.txt')
    for event in history:
        print(f"\n[{event['timestamp']}] {event['change_type']} by {event['author']}")
        print(f"Diff Preview:\n{event['diff_blob'].strip()}")
    print('\n--- 4. Inspecting Head (Cache) ---')
    print(engine.get_head('notes.txt'))
    if DB_PATH.exists():
        os.remove(DB_PATH)
```

---

## FILE: `.microservice-library/services/_EnvironmentManagerMS.py`

```python
"""
SERVICE_NAME: _EnvironmentManagerMS
ENTRY_POINT: _EnvironmentManagerMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from microservice_std_lib import service_metadata, service_endpoint
import time
logger = logging.getLogger('EnvManager')

@service_metadata(name='EnvironmentManager', version='1.0.0', description='Manages Python runtime resolution and process execution.', tags=['runtime', 'python', 'venv', 'process'], capabilities=['os:shell', 'os:process'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['os:process'])
class EnvironmentManagerMS:
    """
    The Operator.
    Finds the right Python interpreter (System vs Venv) and launches processes.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'project_path': 'str', 'config_override': 'str'}, outputs={'interpreter': 'str', 'source': 'str'}, description='Determines the absolute path to the Python interpreter for a given project.', tags=['runtime', 'resolve'])
    def resolve_python(self, project_path: str, config_override: Optional[str]=None) -> Dict[str, str]:
        """
        Priority:
        1. Explicit config override
        2. Local .venv
        3. System default (py or sys.executable)
        """
        path = Path(project_path).resolve()
        if config_override:
            if os.path.sep in config_override or '/' in config_override:
                return {'interpreter': str((path / config_override).resolve()), 'source': 'explicit'}
            return {'interpreter': config_override, 'source': 'command'}
        win_venv = path / '.venv' / 'Scripts' / 'python.exe'
        if win_venv.exists():
            return {'interpreter': str(win_venv), 'source': 'venv'}
        nix_venv = path / '.venv' / 'bin' / 'python'
        if nix_venv.exists():
            return {'interpreter': str(nix_venv), 'source': 'venv'}
        if os.name == 'nt':
            return {'interpreter': 'py', 'source': 'system_launcher'}
        return {'interpreter': sys.executable, 'source': 'system_default'}

    @service_endpoint(inputs={'project_path': 'str', 'script_rel_path': 'str', 'env_vars': 'Dict'}, outputs={'pid': 'int'}, description='Launches a python script in a subprocess using the resolved environment.', tags=['runtime', 'execute'], side_effects=['os:process'])
    def launch_script(self, project_path: str, script_rel_path: str='src/app.py', env_vars: Dict[str, str]=None) -> int:
        root = Path(project_path).resolve()
        script = root / script_rel_path
        if not script.exists():
            raise FileNotFoundError(f'Script not found: {script}')
        python_info = self.resolve_python(str(root))
        cmd = [python_info['interpreter'], str(script)]
        proc_env = os.environ.copy()
        if env_vars:
            proc_env.update(env_vars)
        logger.info(f"Launching {cmd} in {root} via {python_info['source']}")
        if os.name == 'nt':
            proc = subprocess.Popen(cmd, cwd=str(root), env=proc_env, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            proc = subprocess.Popen(cmd, cwd=str(root), env=proc_env)
        return proc.pid
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    mgr = EnvironmentManagerMS()
    print('Resolved Self:', mgr.resolve_python('.'))
```

---

## FILE: `.microservice-library/services/_ExplorerWidgetMS.py`

```python
"""
SERVICE_NAME: _ExplorerWidgetMS
ENTRY_POINT: _ExplorerWidgetMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: ttk
"""
import importlib.util, sys
import time
REQUIRED = ['microservice-std-lib>=1.0.0']
MISSING = []
for lib in REQUIRED:
    clean_lib = lib.split('>=')[0].split('==')[0].split('>')[0].replace('-', '_')
    if importlib.util.find_spec(clean_lib) is None:
        if clean_lib == 'pywebview':
            clean_lib = 'webview'
        if importlib.util.find_spec(clean_lib) is None:
            MISSING.append(lib)
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _ExplorerWidgetMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
import os
import queue
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
import tkinter as tk
from tkinter import ttk
from microservice_std_lib import service_metadata, service_endpoint
DEFAULT_EXCLUDED_FOLDERS = {'node_modules', '.git', '__pycache__', '.venv', '.mypy_cache', '_logs', 'dist', 'build', '.vscode', '.idea', 'target', 'out', 'bin', 'obj', 'Debug', 'Release', 'logs'}

@service_metadata(name='ExplorerWidgetMS', version='1.0.0', description='A standalone file system tree viewer widget.', tags=['ui', 'filesystem', 'widget'], capabilities=['ui:gui', 'filesystem:read'], side_effects=['ui:update', 'ui:read', 'filesystem:read'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=['ttk'])
class ExplorerWidgetMS(BaseService):
    """
    A standalone file system tree viewer.
    """
    GLYPH_CHECKED = '[X]'
    GLYPH_UNCHECKED = '[ ]'

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('ExplorerWidgetMS')
        self.config_data: Dict[str, Any] = config or {}
        parent = self.config_data.get('parent')
        self.root_path: Path = Path(self.config_data.get('root_path', '.')).resolve()
        self.use_defaults: bool = self.config_data.get('use_default_exclusions', True)
        self.gui_queue: queue.Queue = queue.Queue()
        self.folder_item_states: Dict[str, str] = {}
        self.state_lock = threading.RLock()
        self._setup_styles()
        self._build_ui()
        self.process_gui_queue()
        self.refresh_tree()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('Explorer.Treeview', background='#252526', foreground='lightgray', fieldbackground='#252526', borderwidth=0, font=('Consolas', 10))
        style.map('Explorer.Treeview', background=[('selected', '#007ACC')], foreground=[('selected', 'white')])

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, show='tree', columns=('size',), selectmode='none', style='Explorer.Treeview')
        self.tree.column('size', width=80, anchor='e')
        ysb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        xsb = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        ysb.grid(row=0, column=1, sticky='ns')
        xsb.grid(row=1, column=0, sticky='ew')
        self.tree.bind('<ButtonRelease-1>', self._on_click)

    @service_endpoint(inputs={}, outputs={}, description='Rescans the directory and refreshes the tree view.', tags=['ui', 'refresh'], side_effects=['filesystem:read', 'ui:update'])
    def refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        with self.state_lock:
            self.folder_item_states.clear()
            self.folder_item_states[str(self.root_path)] = 'checked'
        root_id = str(self.root_path)
        tree_data: List[Dict[str, Any]] = [{'parent': '', 'iid': root_id, 'text': f' {self.root_path.name} (Root)', 'open': True}]
        self._scan_recursive(self.root_path, root_id, tree_data)
        for item in tree_data:
            self.tree.insert(item['parent'], 'end', iid=item['iid'], text=item['text'], open=item.get('open', False))
            self.tree.set(item['iid'], 'size', '...')
        self._refresh_visuals(root_id)
        threading.Thread(target=self._calc_sizes_thread, args=(root_id,), daemon=True).start()

    def _scan_recursive(self, current_path: Path, parent_id: str, data_list: List[Dict[str, Any]]) -> None:
        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for item in items:
                if not item.is_dir():
                    continue
                path_str = str(item.resolve())
                state = 'checked'
                if self.use_defaults and item.name in DEFAULT_EXCLUDED_FOLDERS:
                    state = 'unchecked'
                with self.state_lock:
                    self.folder_item_states[path_str] = state
                data_list.append({'parent': parent_id, 'iid': path_str, 'text': f' {item.name}'})
                self._scan_recursive(item, path_str, data_list)
        except (PermissionError, OSError):
            pass

    def _on_click(self, event: tk.Event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        with self.state_lock:
            curr = self.folder_item_states.get(item_id, 'unchecked')
            self.folder_item_states[item_id] = 'checked' if curr == 'unchecked' else 'unchecked'
        self._refresh_visuals(str(self.root_path))

    def _refresh_visuals(self, start_node: str) -> None:

        def _update(node_id: str) -> None:
            if not self.tree.exists(node_id):
                return
            with self.state_lock:
                state = self.folder_item_states.get(node_id, 'unchecked')
            glyph = self.GLYPH_CHECKED if state == 'checked' else self.GLYPH_UNCHECKED
            name = Path(node_id).name
            if node_id == str(self.root_path):
                name += ' (Root)'
            self.tree.item(node_id, text=f'{glyph} {name}')
            for child in self.tree.get_children(node_id):
                _update(child)
        _update(start_node)

    def _calc_sizes_thread(self, root_id: str) -> None:
        """
        Background worker for calculating folder sizes.

        Currently a stub so that the thread exits cleanly without errors.
        You can later extend this to walk the filesystem and push
        size updates via self.gui_queue.
        """
        return

    @service_endpoint(inputs={}, outputs={'selected_paths': 'List[str]'}, description='Returns a list of currently checked folder paths.', tags=['ui', 'read'], side_effects=['ui:read'])
    def get_selected_paths(self) -> List[str]:
        selected: List[str] = []
        with self.state_lock:
            for path, state in self.folder_item_states.items():
                if state == 'checked':
                    selected.append(path)
        return selected

    def process_gui_queue(self) -> None:
        while not self.gui_queue.empty():
            try:
                callback = self.gui_queue.get_nowait()
            except queue.Empty:
                break
            else:
                try:
                    callback()
                except Exception:
                    pass
        self.after(100, self.process_gui_queue)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    root = tk.Tk()
    root.title('ExplorerWidgetMS Test Harness')
    widget = ExplorerWidgetMS({'parent': root, 'root_path': os.getcwd()})
    widget.pack(fill='both', expand=True)
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_FingerprintScannerMS.py`

```python
"""
SERVICE_NAME: _FingerprintScannerMS
ENTRY_POINT: _FingerprintScannerMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import hashlib
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Tuple
from microservice_std_lib import service_metadata, service_endpoint
import time
DEFAULT_IGNORE_DIRS = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env', '.mypy_cache', '.pytest_cache', '.idea', '.vscode', 'dist', 'build', 'coverage', 'target', 'out', 'bin', 'obj', '_project_library', '_sandbox', '_logs'}
DEFAULT_IGNORE_FILES = {'.DS_Store', 'Thumbs.db', '*.log', '*.tmp', '*.lock'}
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('Fingerprint')

@service_metadata(name='FingerprintScannerMS', version='1.0.0', description='Scans a directory tree and generates a deterministic SHA-256 fingerprint.', tags=['scanning', 'integrity', 'hashing'], capabilities=['filesystem:read'], side_effects=['filesystem:read'], internal_dependencies=['microservice_std_lib'], external_dependencies=[])
class FingerprintScannerMS:
    """
    The Detective: Scans a directory tree and generates a deterministic
    'Fingerprint' (SHA-256 Merkle Root) representing its exact state.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'root_path': 'str'}, outputs={'state': 'Dict[str, Any]'}, description='Scans the project and returns a comprehensive state object (hashes + Merkle root).', tags=['scanning', 'read'], side_effects=['filesystem:read'])
    def scan_project(self, root_path: str) -> Dict[str, Any]:
        """
        Scans the project and returns a comprehensive state object.
        """
        root = Path(root_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f'Path not found: {root}')
        file_map = {}
        for path in sorted(root.rglob('*')):
            if path.is_file():
                if self._should_ignore(path, root):
                    continue
                rel_path = str(path.relative_to(root)).replace('\\', '/')
                file_hash = self._hash_file(path)
                if file_hash:
                    file_map[rel_path] = file_hash
        sorted_hashes = [file_map[p] for p in sorted(file_map.keys())]
        combined_data = ''.join(sorted_hashes).encode('utf-8')
        project_fingerprint = hashlib.sha256(combined_data).hexdigest()
        log.info(f'Scanned {len(file_map)} files. Fingerprint: {project_fingerprint[:8]}...')
        return {'root': str(root), 'project_fingerprint': project_fingerprint, 'file_hashes': file_map, 'file_count': len(file_map)}

    def _should_ignore(self, path: Path, root: Path) -> bool:
        """Checks path against exclusion lists."""
        try:
            rel_parts = path.relative_to(root).parts
            for part in rel_parts[:-1]:
                if part in DEFAULT_IGNORE_DIRS:
                    return True
            import fnmatch
            name = path.name
            if name in DEFAULT_IGNORE_FILES:
                return True
            if any((fnmatch.fnmatch(name, pat) for pat in DEFAULT_IGNORE_FILES)):
                return True
            return False
        except ValueError:
            return True

    def _hash_file(self, path: Path) -> Optional[str]:
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except (PermissionError, OSError):
            log.warning(f'Could not read/hash: {path}')
            return None
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import time
    test_dir = Path('test_fingerprint_proj')
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    (test_dir / 'main.py').write_text("print('hello')")
    scanner = FingerprintScannerMS()
    print('Service ready:', scanner)
    print('--- Scan 1 (Initial) ---')
    state_1 = scanner.scan_project(str(test_dir))
    print(f"Fingerprint 1: {state_1['project_fingerprint']}")
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
```

---

## FILE: `.microservice-library/services/_GitPilotMS.py`

```python
"""
SERVICE_NAME: _GitPilotMS
ENTRY_POINT: _GitPilotMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: git
"""
import os
import subprocess
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Any, Callable, Dict
from microservice_std_lib import service_metadata, service_endpoint

def which(cmd: str) -> Optional[str]:
    for p in os.environ.get('PATH', '').split(os.pathsep):
        f = Path(p) / cmd
        if os.name == 'nt':
            for ext in ('.exe', '.cmd', '.bat'):
                if f.with_suffix(ext).exists():
                    return str(f.with_suffix(ext))
        if f.exists() and os.access(f, os.X_OK):
            return str(f)
    return None
USE_GH = which('gh') is not None

@dataclass
class GitStatusEntry:
    path: str
    index: str
    workdir: str


@dataclass
class GitStatus:
    repo_path: str
    branch: Optional[str]
    ahead: int
    behind: int
    entries: List[GitStatusEntry]

class GitCLI:
    """
    A robust wrapper around the git command line executable.
    """

    def __init__(self, repo_path: Path):
        self.root = self._resolve_repo_root(repo_path)

    def _run(self, args: List[str], *, cwd: Optional[Path]=None) -> Tuple[str, str]:
        cmd = ['git', *args]
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.run(cmd, cwd=str(cwd or self.root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', startupinfo=startupinfo)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
        return (proc.stdout, proc.stderr)

    @staticmethod
    def _resolve_repo_root(path: Path) -> Path:
        path = path.resolve()
        if (path / '.git').exists():
            return path
        p = path
        while True:
            if (p / '.git').exists():
                return p
            if p.parent == p:
                break
            p = p.parent
        return path

    def init(self) -> None:
        self._run(['init'])

    def status(self) -> GitStatus:
        try:
            out, _ = self._run(['rev-parse', '--abbrev-ref', 'HEAD'])
            branch = out.strip()
        except Exception:
            branch = None
        ahead = behind = 0
        try:
            out, _ = self._run(['rev-list', '--left-right', '--count', '@{upstream}...HEAD'])
            left, right = out.strip().split()
            behind, ahead = (int(left), int(right))
        except Exception:
            pass
        out, _ = self._run(['status', '--porcelain=v1'])
        entries = []
        for line in out.splitlines():
            if not line.strip():
                continue
            xy = line[:2]
            path = line[3:]
            index, work = (xy[0], xy[1])
            entries.append(GitStatusEntry(path=path, index=index, workdir=work))
        return GitStatus(str(self.root), branch, ahead, behind, entries)

    def stage(self, paths: List[str]) -> None:
        if paths:
            self._run(['add', '--'] + paths)

    def unstage(self, paths: List[str]) -> None:
        if paths:
            self._run(['reset', 'HEAD', '--'] + paths)

    def diff(self, file: Optional[str]=None) -> str:
        args = ['diff']
        if file:
            args += ['--', file]
        out, _ = self._run(args)
        return out

    def commit(self, message: str, author_name: str, author_email: str) -> str:
        env = os.environ.copy()
        if author_name:
            env['GIT_AUTHOR_NAME'] = author_name
            env['GIT_COMMITTER_NAME'] = author_name
        if author_email:
            env['GIT_AUTHOR_EMAIL'] = author_email
            env['GIT_COMMITTER_EMAIL'] = author_email
        proc = subprocess.run(['git', 'commit', '-m', message], cwd=str(self.root), capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
        out, _ = self._run(['rev-parse', 'HEAD'])
        return out.strip()

    def log(self, limit: int=100) -> List[Tuple[str, str, str, int]]:
        fmt = '%H%x1f%s%x1f%an%x1f%at'
        try:
            out, _ = self._run(['log', f'-n{limit}', f'--pretty=format:{fmt}'])
            items = []
            for line in out.splitlines():
                commit, summary, author, at = line.split('\x1f')
                items.append((commit, summary, author, int(at)))
            return items
        except Exception:
            return []

    def branches(self) -> List[Tuple[str, bool]]:
        try:
            out, _ = self._run(['branch'])
            res = []
            for line in out.splitlines():
                is_head = line.strip().startswith('*')
                name = line.replace('*', '', 1).strip()
                res.append((name, is_head))
            return res
        except Exception:
            return []

    def checkout(self, name: str, create: bool=False) -> None:
        if create:
            self._run(['checkout', '-B', name])
        else:
            self._run(['checkout', name])

    def push(self, remote: str='origin', branch: Optional[str]=None) -> str:
        args = ['push', remote]
        if branch:
            args.append(branch)
        out, _ = self._run(args)
        return out

    def pull(self, remote: str='origin', branch: Optional[str]=None) -> str:
        if branch:
            out, _ = self._run(['pull', remote, branch])
        else:
            out, _ = self._run(['pull', remote])
        return out

class Worker:

    def __init__(self, ui_callback):
        self.q = queue.Queue()
        self.ui_callback = ui_callback
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def submit(self, op: str, func, *args, **kwargs):
        self.q.put((op, func, args, kwargs))

    def _loop(self):
        while True:
            op, func, args, kwargs = self.q.get()
            try:
                result = (op, True, func(*args, **kwargs))
            except Exception as e:
                result = (op, False, e)
            finally:
                self.ui_callback(result)

@service_metadata(name='GitPilotMS', version='1.0.0', description='A Tkinter GUI panel for Git operations (Stage, Commit, Push, Pull).', tags=['ui', 'git', 'version-control', 'widget'], capabilities=['ui:gui', 'filesystem:read', 'filesystem:write', 'network:outbound'], side_effects=['filesystem:read', 'filesystem:write', 'network:outbound', 'ui:update'], internal_dependencies=['microservice_std_lib'], external_dependencies=['git'])
class GitPilotMS(ttk.Frame):

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        parent = self.config.get('parent')
        ttk.Frame.__init__(self, parent)
        initial_path = self.config.get('initial_path')
        self.repo_path = None
        self.git = None
        self.worker = Worker(self._on_worker_done)
        self._build_ui()
        if initial_path:
            self.set_repo(initial_path)

    @service_endpoint(inputs={'path': 'Path'}, outputs={}, description='Sets the active repository path and refreshes status.', tags=['git', 'config'], side_effects=['filesystem:read', 'ui:update'])
    def set_repo(self, path: Path):
        try:
            self.git = GitCLI(path)
            self.repo_path = self.git.root
            self.path_var.set(f'Repo: {self.repo_path}')
            self._refresh()
        except Exception as e:
            self.path_var.set(f'Error: {e}')

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky='ew')
        self.path_var = tk.StringVar(value='No Repo Selected')
        self.busy_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.path_var).pack(side='left', padx=5)
        ttk.Label(bar, textvariable=self.busy_var, foreground='blue').pack(side='right', padx=5)
        self.nb = ttk.Notebook(self)
        self.nb.grid(row=1, column=0, sticky='nsew')
        self.tab_changes = self._build_changes_tab(self.nb)
        self.tab_log = self._build_log_tab(self.nb)
        self.nb.add(self.tab_changes, text='Changes')
        self.nb.add(self.tab_log, text='History')

    def _build_changes_tab(self, parent):
        frame = ttk.Frame(parent)
        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(fill='both', expand=True)
        top = ttk.Frame(paned)
        top.rowconfigure(1, weight=1)
        top.columnconfigure(0, weight=1)
        tb = ttk.Frame(top)
        tb.grid(row=0, column=0, sticky='ew')
        ttk.Button(tb, text='Refresh', command=self._refresh).pack(side='left')
        ttk.Button(tb, text='Stage', command=self._stage).pack(side='left')
        ttk.Button(tb, text='Unstage', command=self._unstage).pack(side='left')
        ttk.Button(tb, text='Diff', command=self._show_diff).pack(side='left')
        ttk.Button(tb, text='Push', command=self._push).pack(side='left', padx=10)
        ttk.Button(tb, text='Pull', command=self._pull).pack(side='left')
        self.tree = ttk.Treeview(top, columns=('path', 'idx', 'wd'), show='headings', selectmode='extended')
        self.tree.heading('path', text='Path')
        self.tree.heading('idx', text='Index')
        self.tree.heading('wd', text='Workdir')
        self.tree.column('path', width=400)
        self.tree.column('idx', width=50, anchor='center')
        self.tree.column('wd', width=50, anchor='center')
        self.tree.grid(row=1, column=0, sticky='nsew')
        paned.add(top, weight=3)
        bot = ttk.Frame(paned)
        bot.columnconfigure(1, weight=1)
        ttk.Label(bot, text='Message:').grid(row=0, column=0, sticky='nw')
        self.msg_text = tk.Text(bot, height=4)
        self.msg_text.grid(row=0, column=1, sticky='nsew')
        ttk.Button(bot, text='Commit', command=self._commit).grid(row=1, column=1, sticky='e', pady=5)
        paned.add(bot, weight=1)
        return frame

    def _build_log_tab(self, parent):
        frame = ttk.Frame(parent)
        self.log_tree = ttk.Treeview(frame, columns=('sha', 'msg', 'auth', 'time'), show='headings')
        self.log_tree.heading('sha', text='SHA')
        self.log_tree.heading('msg', text='Message')
        self.log_tree.heading('auth', text='Author')
        self.log_tree.heading('time', text='Time')
        self.log_tree.column('sha', width=80)
        self.log_tree.column('msg', width=400)
        self.log_tree.pack(fill='both', expand=True)
        return frame

    def _submit(self, label, func, *args):
        self.busy_var.set(f'{label}...')
        self.worker.submit(label, func, *args)

    def _on_worker_done(self, result):
        self.after(0, self._handle_result, result)

    def _handle_result(self, result):
        label, ok, data = result
        self.busy_var.set('')
        if not ok:
            messagebox.showerror('Error', str(data))
            return
        if label == 'refresh':
            status, logs = data
            self.tree.delete(*self.tree.get_children())
            for e in status.entries:
                self.tree.insert('', 'end', values=(e.path, e.index, e.workdir))
            self.log_tree.delete(*self.log_tree.get_children())
            for sha, msg, auth, ts in logs:
                t_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))
                self.log_tree.insert('', 'end', values=(sha[:7], msg, auth, t_str))
        if label == 'diff':
            top = tk.Toplevel(self)
            top.title('Diff')
            txt = tk.Text(top, font=('Consolas', 10))
            txt.pack(fill='both', expand=True)
            txt.insert('1.0', data)
        if label in ['stage', 'unstage', 'commit', 'push', 'pull']:
            self._refresh()

    def _refresh(self):
        if not self.git:
            return
        self._submit('refresh', lambda: (self.git.status(), self.git.log()))

    def _get_selection(self):
        return [self.tree.item(i)['values'][0] for i in self.tree.selection()]

    def _stage(self):
        paths = self._get_selection()
        if paths:
            self._submit('stage', self.git.stage, paths)

    def _unstage(self):
        paths = self._get_selection()
        if paths:
            self._submit('unstage', self.git.unstage, paths)

    def _commit(self):
        msg = self.msg_text.get('1.0', 'end').strip()
        if not msg:
            return
        self._submit('commit', self.git.commit, msg, 'GitPilot', 'pilot@local')
        self.msg_text.delete('1.0', 'end')

    def _push(self):
        self._submit('push', self.git.push)

    def _pull(self):
        self._submit('pull', self.git.pull)

    def _show_diff(self):
        sel = self._get_selection()
        file = sel[0] if sel else None
        self._submit('diff', self.git.diff, file)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    root = tk.Tk()
    root.title('Git Pilot Test')
    root.geometry('800x600')
    cwd = Path(os.getcwd())
    panel = GitPilotMS({'parent': root, 'initial_path': cwd})
    print('Service ready:', panel)
    panel.pack(fill='both', expand=True)
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_HeuristicSumMS.py`

```python
"""
SERVICE_NAME: _HeuristicSumMS
ENTRY_POINT: _HeuristicSumMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import os
import re
from typing import Any, Dict, List, Optional
from microservice_std_lib import service_metadata, service_endpoint, BaseService
import time
SIG_RE = re.compile('^\\s*(def|class|function|interface|struct|impl|func)\\s+([A-Za-z_][A-Za-z0-9_]*)')
MD_HDR_RE = re.compile('^\\s{0,3}(#{1,3})\\s+(.+)')
DOC_RE = re.compile('^\\s*("{3}|\\\'{3})(.*)', re.DOTALL)

@service_metadata(name='HeuristicSum', version='1.0.0', description='Generates quick summaries of code/text files using regex heuristics (No AI).', tags=['parsing', 'summary', 'heuristics'], capabilities=['compute'], side_effects=[], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=[])
class HeuristicSumMS(BaseService):
    """
    The Skimmer: Generates quick summaries of code/text files without AI.
    Scans for high-value lines (headers, signatures, docstrings) and concatenates them.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('HeuristicSum')
        self.config = config or {}

    @service_endpoint(inputs={'text': 'str', 'filename': 'str', 'max_chars': 'int'}, outputs={'summary': 'str'}, description='Generates a summary string from the provided text.', tags=['summary', 'parsing'])
    def summarize(self, text: str, filename: str='', max_chars: int=480) -> str:
        """
        Generates a summary string from the provided text.
        """
        lines = text.splitlines()
        picks = []
        for ln in lines[:20]:
            m = MD_HDR_RE.match(ln)
            if m:
                picks.append(f'Heading: {m.group(2).strip()}')
        for ln in lines[:40]:
            m = SIG_RE.match(ln)
            if m:
                picks.append(f'{m.group(1)} {m.group(2)}')
        if lines:
            joined = '\n'.join(lines[:80])
            m = DOC_RE.match(joined)
            if m:
                after = joined.splitlines()[1:3]
                if after:
                    clean_doc = ' '.join((s.strip() for s in after)).strip()
                    picks.append(f'Doc: {clean_doc}')
        if not picks:
            head = ' '.join((l.strip() for l in lines[:2] if l.strip()))
            if head:
                picks.append(head)
        if filename:
            picks.append(f'[{os.path.basename(filename)}]')
        seen = set()
        uniq = []
        for p in picks:
            if p and p not in seen:
                uniq.append(p)
                seen.add(p)
        summary = ' | '.join(uniq)
        if len(summary) > max_chars:
            summary = summary[:max_chars - 3] + '...'
        return summary.strip() if summary else '[No summary available]'
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    skimmer = HeuristicSumMS()
    print(f'Service ready: {skimmer}')
    py_code = "\n    class DataProcessor:\n        '''\n        Handles the transformation of raw input data into structured formats.\n        '''\n        def process(self, data):\n            pass\n    "
    print(f"Python Summary: {skimmer.summarize(py_code, 'processor.py')}")
    md_text = '\n    # Project Roadmap\n    ## Phase 1\n    We begin with ingestion.\n    '
    print(f"Markdown Summary: {skimmer.summarize(md_text, 'README.md')}")
```

---

## FILE: `.microservice-library/services/_IngestEngineMS.py`

```python
"""
SERVICE_NAME: _IngestEngineMS
ENTRY_POINT: _IngestEngineMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: requests
"""
import importlib.util
REQUIRED = ['requests']
MISSING = []
for lib in REQUIRED:
    if importlib.util.find_spec(lib) is None:
        MISSING.append(lib)
if MISSING:
    print(f"MISSING DEPENDENCIES: {' '.join(MISSING)}")
    print('Please run: pip install requests')
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional
import requests
from microservice_std_lib import service_metadata, service_endpoint, BaseService
OLLAMA_API_URL = 'http://localhost:11434/api'

@dataclass
class IngestStatus:
    current_file: str
    progress_percent: float
    processed_files: int
    total_files: int
    log_message: str
    thought_frame: Optional[Dict] = None


class SynapseWeaver:
    """
    Parses source code to extract import dependencies.
    Used to generate the 'DEPENDS_ON' edges in the Knowledge Graph.
    """

    def __init__(self):
        self.py_pattern = re.compile('^\\s*(?:from|import)\\s+([\\w\\.]+)')
        self.js_pattern = re.compile('(?:import\\s+.*?from\\s+[\\\'"]|require\\([\\\'"])([\\.\\/\\w\\-_]+)[\\\'"]')

    def extract_dependencies(self, content: str, file_path: str) -> List[str]:
        dependencies = []
        ext = os.path.splitext(file_path)[1].lower()
        lines = content.split('\n')
        for line in lines:
            match = None
            if ext == '.py':
                match = self.py_pattern.match(line)
            elif ext in ['.js', '.ts', '.tsx', '.jsx']:
                match = self.js_pattern.search(line)
            if match:
                raw_dep = match.group(1)
                clean_dep = raw_dep.split('.')[-1].split('/')[-1]
                if clean_dep not in dependencies:
                    dependencies.append(clean_dep)
        return dependencies

@service_metadata(name='IngestEngine', version='1.0.0', description='Reads files, chunks text, fetches embeddings, and weaves graph edges.', tags=['ingest', 'rag', 'parsing', 'embedding'], capabilities=['filesystem:read', 'network:outbound', 'db:sqlite'], side_effects=['db:write', 'network:outbound'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=['requests'])
class IngestEngineMS(BaseService):
    """
    The Heavy Lifter: Reads files, chunks text, fetches embeddings,
    populates the Graph Nodes, and weaves Graph Edges.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        super().__init__('IngestEngine')
        self.config = config or {}
        self.db_path = self.config.get('db_path', 'knowledge.db')
        self.stop_signal = False
        self.weaver = SynapseWeaver()
        self._init_db()

    def _init_db(self):
        """Ensures the target database has the required schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, path TEXT, last_updated REAL)')
        conn.execute('CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, file_id INT, chunk_index INT, content TEXT, embedding BLOB)')
        conn.execute('CREATE TABLE IF NOT EXISTS graph_nodes (id TEXT PRIMARY KEY, type TEXT, label TEXT, data_json TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS graph_edges (source TEXT, target TEXT, weight REAL)')
        conn.close()

    def abort(self):
        self.stop_signal = True

    def check_ollama_connection(self) -> bool:
        try:
            requests.get(f'{OLLAMA_API_URL}/tags', timeout=2)
            return True
        except:
            return False

    def get_available_models(self) -> List[str]:
        try:
            res = requests.get(f'{OLLAMA_API_URL}/tags')
            if res.status_code == 200:
                data = res.json()
                return [m['name'] for m in data.get('models', [])]
        except:
            pass
        return []

    @service_endpoint(inputs={'file_paths': 'List[str]', 'model_name': 'str'}, outputs={'status': 'IngestStatus'}, description='Processes a list of files, ingesting them into the knowledge graph.', tags=['ingest', 'processing'], mode='generator', side_effects=['db:write', 'network:outbound'])
    def process_files(self, file_paths: List[str], model_name: str='nomic-embed-text:latest') -> Generator[IngestStatus, None, None]:
        total = len(file_paths)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA synchronous = OFF')
        cursor.execute('PRAGMA journal_mode = MEMORY')
        node_registry = {}
        file_contents = {}
        for idx, file_path in enumerate(file_paths):
            if self.stop_signal:
                yield IngestStatus(file_path, 0, idx, total, 'Ingestion Aborted.')
                break
            filename = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                file_contents[filename] = content
            except Exception as e:
                yield IngestStatus(file_path, idx / total * 100, idx, total, f'Error: {e}')
                continue
            try:
                cursor.execute('INSERT OR REPLACE INTO files (path, last_updated) VALUES (?, ?)', (file_path, time.time()))
                file_id = cursor.lastrowid
            except sqlite3.Error:
                continue
            cursor.execute('\n                INSERT OR REPLACE INTO graph_nodes (id, type, label, data_json)\n                VALUES (?, ?, ?, ?)\n            ', (filename, 'file', filename, json.dumps({'path': file_path})))
            node_registry[filename] = filename
            chunks = self._chunk_text(content)
            for i, chunk_text in enumerate(chunks):
                if self.stop_signal:
                    break
                embedding = None
                if model_name != 'none':
                    embedding = self._get_embedding(model_name, chunk_text)
                emb_blob = json.dumps(embedding).encode('utf-8') if embedding else None
                cursor.execute('\n                    INSERT INTO chunks (file_id, chunk_index, content, embedding)\n                    VALUES (?, ?, ?, ?)\n                ', (file_id, i, chunk_text, emb_blob))
                thought_frame = {'id': f'{file_id}_{i}', 'file': filename, 'chunk_index': i, 'content': chunk_text, 'vector_preview': embedding[:20] if embedding else [], 'concept_color': '#007ACC'}
                yield IngestStatus(current_file=filename, progress_percent=(idx + i / len(chunks)) / total * 100, processed_files=idx, total_files=total, log_message=f'Processing {filename}...', thought_frame=thought_frame)
            conn.commit()
        yield IngestStatus('Graph', 100, total, total, 'Weaving Knowledge Graph...')
        edge_count = 0
        for filename, content in file_contents.items():
            if self.stop_signal:
                break
            deps = self.weaver.extract_dependencies(content, filename)
            for dep in deps:
                target_id = None
                for potential_match in node_registry.keys():
                    if potential_match.startswith(dep + '.') or potential_match == dep:
                        target_id = potential_match
                        break
                if target_id and target_id != filename:
                    try:
                        cursor.execute('\n                            INSERT OR IGNORE INTO graph_edges (source, target, weight)\n                            VALUES (?, ?, 1.0)\n                        ', (filename, target_id))
                        edge_count += 1
                    except:
                        pass
        conn.commit()
        conn.close()
        yield IngestStatus(current_file='Complete', progress_percent=100, processed_files=total, total_files=total, log_message=f'Ingestion Complete. Created {edge_count} dependency edges.')

    def _chunk_text(self, text: str, chunk_size: int=1000, overlap: int=100) -> List[str]:
        if len(text) < chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def _get_embedding(self, model: str, text: str) -> Optional[List[float]]:
        try:
            res = requests.post(f'{OLLAMA_API_URL}/embeddings', json={'model': model, 'prompt': text}, timeout=30)
            if res.status_code == 200:
                return res.json().get('embedding')
        except:
            return None
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    TEST_DB = 'test_ingest_v2.db'
    engine = IngestEngineMS({'db_path': TEST_DB})
    print(f'Service Ready: {engine}')
    target_file = '__IngestEngineMS.py'
    if not os.path.exists(target_file):
        with open(target_file, 'w') as f:
            f.write("import os\nimport json\nprint('Hello World')")
    print(f'Running Ingest on {target_file}...')
    files = [target_file]
    for status in engine.process_files(files, 'none'):
        print(f'[{status.progress_percent:.0f}%] {status.log_message}')
    conn = sqlite3.connect(TEST_DB)
    edges = conn.execute('SELECT * FROM graph_edges').fetchall()
    nodes = conn.execute('SELECT * FROM graph_nodes').fetchall()
    print(f'\nResult: {len(nodes)} Nodes, {len(edges)} Edges.')
    conn.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    if os.path.exists(target_file) and 'Hello World' in open(target_file).read():
        os.remove(target_file)
```

---

## FILE: `.microservice-library/services/_IntakeServiceMS.py`

```python
"""
SERVICE_NAME: _IntakeServiceMS
ENTRY_POINT: _IntakeServiceMS.py
INTERNAL_DEPENDENCIES: _CartridgeServiceMS, _ScoutMS, base_service, document_utils, microservice_std_lib
EXTERNAL_DEPENDENCIES: bs4, requests
"""
import os
import mimetypes
import time
import requests
import fnmatch
import json
from pathlib import Path
from typing import Dict, Set, List, Any
from base_service import BaseService
from _CartridgeServiceMS import CartridgeServiceMS
from _ScoutMS import ScoutMS
import document_utils
from microservice_std_lib import service_metadata, service_endpoint
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

@service_metadata(name='IntakeServiceMS', version='1.3.0', description='The Vacuum: Handles two-phase ingestion by scanning sources and processing selected paths into the cartridge.', tags=['ingestion', 'scanner', 'vfs'], capabilities=['filesystem:read', 'web:crawl'], side_effects=['filesystem:read', 'cartridge:write'], internal_dependencies=['_CartridgeServiceMS', '_ScoutMS', 'base_service', 'document_utils', 'microservice_std_lib'], external_dependencies=['bs4', 'requests'])
class IntakeServiceMS(BaseService):
    """
    The Vacuum. 
    Now supports two-phase ingestion:
    1. Scan -> Build Tree (with .gitignore respect)
    2. Ingest -> Process selected paths
    """
    DEFAULT_IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 'env', '.env', '.idea', '.vscode', 'dist', 'build', 'target', 'bin', 'obj', '__cartridge__'}
    DEFAULT_IGNORE_EXTS = {'.pyc', '.pyd', '.exe', '.dll', '.so', '.db', '.sqlite', '.sqlite3', '.bin', '.iso', '.img', '.zip', '.tar', '.gz', '.7z', '.jpg', '.png'}

    def __init__(self, cartridge: CartridgeServiceMS):
        super().__init__('IntakeServiceMS')
        self.cartridge = cartridge
        self.ignore_patterns: Set[str] = set()
        self.start_time = time.time()

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float', 'cartridge_connected': 'bool'}, description='Standardized health check to verify service status and cartridge connectivity.', tags=['diagnostic', 'health'])
    def get_health(self) -> Dict[str, Any]:
        """Returns the operational status of the IntakeServiceMS."""
        return {'status': 'online', 'uptime': time.time() - self.start_time, 'cartridge_connected': self.cartridge is not None}

    def ingest_source(self, source_path: str) -> Dict[str, int]:
        """Headless/CLI Entry point: Scans and Ingests in one go."""
        self.cartridge.initialize_manifest()
        self.cartridge.set_manifest('source_root', source_path)
        is_web = source_path.startswith('http')
        self.cartridge.set_manifest('source_type', 'web_root' if is_web else 'filesystem_dir')
        scanner = ScoutMS()
        tree_node = scanner.scan_directory(source_path, web_depth=1 if is_web else 0)
        if not tree_node:
            return {'error': 'Source not found'}
        files_to_ingest = scanner.flatten_tree(tree_node)
        self.cartridge.set_manifest('ingest_config', {'auto_flattened': True, 'count': len(files_to_ingest)})
        return self.ingest_selected(files_to_ingest, source_path)

    @service_endpoint(inputs={'root_path': 'str', 'web_depth': 'int'}, outputs={'tree': 'dict'}, description='Scans a local directory or URL to build a hierarchical tree structure of available files.', tags=['scan', 'discovery'])
    def scan_path(self, root_path: str, web_depth: int=0) -> Dict[str, Any]:
        """
        Unified Scanner Interface.
        Delegates to ScoutMS for both Web and Local FS to ensure consistent node structure.
        """
        scanner = ScoutMS()
        tree_root = scanner.scan_directory(root_path, web_depth=web_depth)
        if not tree_root:
            return None
        if not root_path.startswith('http'):
            saved_config = self._load_persistence(os.path.abspath(root_path))
            self._apply_persistence(tree_root, saved_config)
        return tree_root

    def _apply_persistence(self, node: Dict, saved_config: Dict):
        """Recursively applies checked state from saved config."""
        if 'rel_path' in node and node['rel_path'] in saved_config:
            node['checked'] = saved_config[node['rel_path']]
        elif 'children' in node:
            pass
        if 'children' in node:
            for child in node['children']:
                self._apply_persistence(child, saved_config)

    def _scan_recursive(self, current_path: str, root_path: str, saved_config: Dict) -> Dict:
        name = os.path.basename(current_path)
        is_dir = os.path.isdir(current_path)
        rel_path = os.path.relpath(current_path, root_path).replace('\\', '/')
        node = {'name': name, 'path': current_path, 'rel_path': rel_path, 'type': 'dir' if is_dir else 'file', 'children': [], 'checked': True}
        if saved_config and rel_path in saved_config:
            node['checked'] = saved_config[rel_path]
        elif self._is_ignored(name) or (not is_dir and self._is_binary_ext(name)):
            node['checked'] = False
        if is_dir:
            try:
                with os.scandir(current_path) as it:
                    entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
                    for entry in entries:
                        child = self._scan_recursive(entry.path, root_path, saved_config)
                        node['children'].append(child)
            except PermissionError:
                pass
        return node

    @service_endpoint(inputs={'file_list': 'list', 'root_path': 'str'}, outputs={'stats': 'dict'}, description='Processes a specific list of files into the cartridge storage, handling text extraction and VFS indexing.', tags=['ingest', 'write'], side_effects=['cartridge:write'])
    def ingest_selected(self, file_list: List[str], root_path: str) -> Dict[str, int]:
        """Ingests only the specific files passed in the list."""
        stats = {'added': 0, 'skipped': 0, 'errors': 0}
        for file_path in file_list:
            try:
                try:
                    vfs_path = os.path.relpath(file_path, root_path).replace('\\', '/')
                except ValueError:
                    vfs_path = os.path.basename(file_path)
                self._read_and_store(Path(file_path), vfs_path, 'filesystem', stats)
            except Exception as e:
                self.log_error(f'Error ingesting {file_path}: {e}')
                stats['errors'] += 1
        self._rebuild_directory_index()
        return stats

    def _rebuild_directory_index(self):
        """
        Scans 'files' table and populates 'directories' table.
        This creates the navigable VFS structure.
        """
        self.log_info('Rebuilding VFS Directory Index...')
        conn = self.cartridge._get_conn()
        try:
            rows = conn.execute('SELECT vfs_path FROM files').fetchall()
            seen_dirs = set()
            for r in rows:
                path = r[0]
                current = os.path.dirname(path).replace('\\', '/')
                while current and current != '.' and (current not in seen_dirs):
                    self.cartridge.ensure_directory(current)
                    seen_dirs.add(current)
                    current = os.path.dirname(current).replace('\\', '/')
        except Exception as e:
            self.log_error(f'Directory Index Error: {e}')
        finally:
            conn.close()

    def _load_persistence(self, root_path: str) -> Dict[str, bool]:
        """Loads config from DB Manifest (Portable) or fallback to local."""
        try:
            conn = self.cartridge._get_conn()
            row = conn.execute("SELECT value FROM manifest WHERE key='ingest_config'").fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except:
            pass
        cfg_path = os.path.join(root_path, '.ragforge.json')
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save_persistence(self, root_path: str, checked_map: Dict[str, bool]):
        """Saves user selections into the Cartridge Manifest (Portable)."""
        try:
            conn = self.cartridge._get_conn()
            conn.execute('INSERT OR REPLACE INTO manifest (key, value) VALUES (?, ?)', ('ingest_config', json.dumps(checked_map)))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_error(f'Failed to save persistence to DB: {e}')
        cfg_path = os.path.join(root_path, '.ragforge.json')
        try:
            with open(cfg_path, 'w') as f:
                json.dump(checked_map, f, indent=2)
        except:
            pass

    def _load_gitignore(self, root_path: str):
        gitignore_path = os.path.join(root_path, '.gitignore')
        self.ignore_patterns = self.DEFAULT_IGNORE_DIRS.copy()
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and (not line.startswith('#')):
                            if line.endswith('/'):
                                line = line[:-1]
                            self.ignore_patterns.add(line)
            except:
                pass

    def _is_ignored(self, name: str) -> bool:
        if name in self.ignore_patterns:
            return True
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _is_binary_ext(self, name: str) -> bool:
        _, ext = os.path.splitext(name)
        return ext.lower() in self.DEFAULT_IGNORE_EXTS

    def _read_and_store(self, real_path: Path, vfs_path: str, origin_type: str, stats: Dict):
        mime_type, _ = mimetypes.guess_type(real_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
        content = None
        blob = None
        try:
            with open(real_path, 'rb') as f:
                blob = f.read()
        except Exception as e:
            self.log_error(f'Read error {real_path}: {e}')
            stats['errors'] += 1
            return
        lower_path = str(real_path).lower()
        if lower_path.endswith('.pdf'):
            content = document_utils.extract_text_from_pdf(blob)
            if not content:
                mime_type = 'application/pdf'
        elif lower_path.endswith('.html') or lower_path.endswith('.htm'):
            try:
                raw_text = blob.decode('utf-8', errors='ignore')
                content = document_utils.extract_text_from_html(raw_text)
            except:
                pass
        else:
            try:
                content = blob.decode('utf-8')
            except UnicodeDecodeError:
                content = None
        success = self.cartridge.store_file(vfs_path, str(real_path), content=content, blob=blob, mime_type=mime_type, origin_type=origin_type)
        if success:
            stats['added'] += 1
        else:
            stats['errors'] += 1
        if __name__ == '__main__':
            from _CartridgeServiceMS import CartridgeService
            mock_cartridge = CartridgeService(':memory:')
            svc = IntakeServiceMS(mock_cartridge)
            print('Service ready:', svc._service_info['name'])
```

---

## FILE: `.microservice-library/services/_IsoProcessMS.py`

```python
import multiprocessing as mp
import logging
import logging.handlers
import time
import queue
from typing import Any, Dict, Optional
from microservice_std_lib import service_metadata, service_endpoint

def _isolated_worker(result_queue: mp.Queue, log_queue: mp.Queue, payload: Any, config: Dict[str, Any]):
    """
    Entry point for the child process.
    Configures a logging handler to send records back to the parent.
    Note: Must remain top-level for multiprocessing pickling compatibility.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in root.handlers[:]:
        root.removeHandler(h)
    qh = logging.handlers.QueueHandler(log_queue)
    root.addHandler(qh)
    log = logging.getLogger('IsoWorker')
    try:
        log.info(f'Worker PID {mp.current_process().pid} started.')
        log.info('Loading heavy libraries (Torch/Transformers)...')
        time.sleep(0.2)
        model_name = config.get('model_name', 'default-model')
        log.info(f"Initializing model '{model_name}'...")
        for i in range(1, 4):
            time.sleep(0.3)
            log.info(f'Processing chunk {i}/3...')
        processed_data = f'Processed({payload}) via {model_name}'
        log.info('Work complete. Returning result.')
        result_queue.put({'success': True, 'data': processed_data})
    except Exception as e:
        log.exception('Critical failure in worker process.')
        result_queue.put({'success': False, 'error': str(e)})

@service_metadata(name='IsoProcess', version='1.0.0', description='Spawns isolated processes with real-time logging feedback.', tags=['process', 'isolation', 'safety'], capabilities=['process:spawn'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['process:spawn'])
class IsoProcessMS:
    """
    The Safety Valve: Spawns isolated processes with real-time logging feedback.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.timeout = self.config.get('timeout_seconds', 60)
        self.log = logging.getLogger('IsoParent')
        if not self.log.handlers:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

    @service_endpoint(inputs={'payload': 'Any', 'config': 'Dict'}, outputs={'result': 'Any'}, description='Executes a payload in an isolated child process.', tags=['process', 'execution'], side_effects=['process:spawn'])
    def execute(self, payload: Any, config: Optional[Dict[str, Any]]=None) -> Any:
        config = config or {}
        ctx = mp.get_context('spawn')
        result_queue = ctx.Queue()
        log_queue = ctx.Queue()
        listener = logging.handlers.QueueListener(log_queue, *logging.getLogger().handlers)
        listener.start()
        process = ctx.Process(target=_isolated_worker, args=(result_queue, log_queue, payload, config))
        self.log.info('🚀 Spawning isolated process...')
        process.start()
        try:
            result_packet = result_queue.get(timeout=self.timeout)
            process.join()
            if result_packet['success']:
                return result_packet['data']
            else:
                raise RuntimeError(f"Worker Error: {result_packet['error']}")
        except queue.Empty:
            self.log.error('⏳ Worker timed out! Terminating...')
            process.terminate()
            process.join()
            raise TimeoutError(f'Task exceeded {self.timeout}s limit.')
        finally:
            listener.stop()
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    print('--- Testing IsoProcessMS with Live Logging ---')
    iso = IsoProcessMS({'timeout_seconds': 5})
    print('Service ready:', iso)
    try:
        result = iso.execute('Sensitive Data', {'model_name': 'DeepSeek-V3'})
        print(f'\n[Parent] Final Result: {result}')
    except Exception as e:
        print(f'\n[Parent] Failed: {e}')
```

---

## FILE: `.microservice-library/services/_LexicalSearchMS.py`

```python
import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time

@service_metadata(name='LexicalSearch', version='1.0.0', description='Lightweight BM25 keyword search using SQLite FTS5 (No AI required).', tags=['search', 'index', 'sqlite'], capabilities=['db:sqlite', 'filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['db:write', 'db:read'])
class LexicalSearchMS:
    """
    The Librarian's Index: A lightweight, AI-free search engine.
    
    Uses SQLite's FTS5 extension to provide fast, ranked keyword search (BM25).
    Ideal for environments where installing PyTorch/Transformers is impossible
    or overkill.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        default_db = str(Path(__file__).parent / 'lexical_index.db')
        self.db_path = self.config.get('db_path', default_db)
        self._init_db()

    def _init_db(self):
        """
        Sets up the schema. 
        Uses Triggers to automatically keep the FTS index in sync with the main table.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('\n            CREATE TABLE IF NOT EXISTS documents (\n                id TEXT PRIMARY KEY,\n                content TEXT,\n                metadata TEXT  -- JSON blob for extra info (path, author, etc)\n            );\n        ')
        cur.execute("\n            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(\n                content,\n                content='documents',\n                content_rowid='rowid'  -- Internal SQLite mapping\n            );\n        ")
        cur.execute('\n            CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON documents BEGIN\n                INSERT INTO documents_fts(rowid, content) VALUES (new.rowid, new.content);\n            END;\n        ')
        cur.execute("\n            CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON documents BEGIN\n                INSERT INTO documents_fts(documents_fts, rowid, content) VALUES('delete', old.rowid, old.content);\n            END;\n        ")
        cur.execute("\n            CREATE TRIGGER IF NOT EXISTS doc_au AFTER UPDATE ON documents BEGIN\n                INSERT INTO documents_fts(documents_fts, rowid, content) VALUES('delete', old.rowid, old.content);\n                INSERT INTO documents_fts(rowid, content) VALUES (new.rowid, new.content);\n            END;\n        ")
        conn.commit()
        conn.close()

    @service_endpoint(inputs={'doc_id': 'str', 'text': 'str', 'metadata': 'Dict'}, outputs={}, description='Adds or updates a document in the FTS index.', tags=['search', 'write'], side_effects=['db:write'])
    def add_document(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]]=None):
        """
        Adds or updates a document in the index.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        meta_json = json.dumps(metadata or {})
        cur.execute('\n            INSERT OR REPLACE INTO documents (id, content, metadata)\n            VALUES (?, ?, ?)\n        ', (doc_id, text, meta_json))
        conn.commit()
        conn.close()

    @service_endpoint(inputs={'query': 'str', 'top_k': 'int'}, outputs={'results': 'List[Dict]'}, description='Performs a BM25 ranked keyword search.', tags=['search', 'read'], side_effects=['db:read'])
    def search(self, query: str, top_k: int=20) -> List[Dict[str, Any]]:
        """
        Performs a BM25 Ranked Search.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            sql = "\n                SELECT \n                    d.id, \n                    d.content, \n                    d.metadata,\n                    snippet(documents_fts, 0, '<b>', '</b>', '...', 15) as preview,\n                    bm25(documents_fts) as score\n                FROM documents_fts \n                JOIN documents d ON d.rowid = documents_fts.rowid\n                WHERE documents_fts MATCH ? \n                ORDER BY score ASC\n                LIMIT ?\n            "
            safe_query = f'"{query}"'
            rows = cur.execute(sql, (safe_query, top_k)).fetchall()
            results = []
            for r in rows:
                results.append({'id': r['id'], 'score': round(r['score'], 4), 'preview': r['preview'], 'metadata': json.loads(r['metadata']), 'full_content': r['content']})
            return results
        except sqlite3.OperationalError as e:
            print(f'Search syntax error: {e}')
            return []
        finally:
            conn.close()
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import os
    db_name = 'test_lexical.db'
    engine = LexicalSearchMS({'db_path': db_name})
    print('Service ready:', engine)
    print('Ingesting test data...')
    engine.add_document('doc1', 'Python is a great language for data science.', {'category': 'coding'})
    engine.add_document('doc2', 'The snake python is a reptile found in jungles.', {'category': 'biology'})
    engine.add_document('doc3', 'Data science involves python, pandas, and SQL.', {'category': 'coding'})
    query = 'python data'
    print(f"\nSearching for: '{query}'")
    hits = engine.search(query)
    for hit in hits:
        print(f"[{hit['score']:.4f}] {hit['id']} ({hit['metadata']['category']})")
        print(f"   Preview: {hit['preview']}")
    if os.path.exists(db_name):
        os.remove(db_name)
```

---

## FILE: `.microservice-library/services/_LibrarianMS.py`

```python
"""
SERVICE_NAME: _LibrarianMS
ENTRY_POINT: _LibrarianMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: requests
"""
import importlib.util
import time
if importlib.util.find_spec('requests') is None:
    print('! MISSING DEPENDENCY: pip install requests')
import ast
import os
import datetime
import logging
import json
import requests
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
ENABLE_AI = True
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL_WORKER = 'qwen2.5-coder:1.5b-cpu'
MODEL_ARCHITECT = 'qwen2.5-coder:3b-cpu'
MAX_WORKERS = 4
MAX_CONTEXT_CHARS = 16000
logger = logging.getLogger('Librarian')

@service_metadata(name='Librarian', version='3.0.0', description="Uses a swarm of local AI models to generate a 'Card Catalogue' of the microservice library.", tags=['documentation', 'ai', 'catalog', 'swarm'], capabilities=['filesystem:read', 'filesystem:write', 'network:outbound', 'compute:parallel'], internal_dependencies=['microservice_std_lib'], external_dependencies=['requests'], side_effects=['filesystem:write'])
class LibrarianMS:
    """
    The Swarm Librarian.
    Spawns concurrent AI workers to scan the codebase and create a system manifest.
    Optimized for Ryzen CPUs and 32GB RAM.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.root = Path(self.config.get('root_path', '.')).resolve()

    @service_endpoint(inputs={'output_file': 'str'}, outputs={'path': 'str', 'service_count': 'int'}, description='Unleashes the AI swarm to generate a catalog.', tags=['catalog', 'generate'], side_effects=['filesystem:write'])
    def generate_catalog(self, output_file: str='LIBRARY_CATALOGUE.md') -> Dict[str, Any]:
        """
        Main entry point. Uses ThreadPoolExecutor for parallel processing.
        """
        services = []
        logger.info(f'🚀 Launching Swarm (Workers: {MAX_WORKERS}, Model: {MODEL_WORKER})...')
        ms_files = list(self.root.glob('*MS.py'))
        targets = [f for f in ms_files if f.name.startswith('_')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_file = {executor.submit(self._inspect_file, f): f for f in targets}
            for future in concurrent.futures.as_completed(future_to_file):
                f_path = future_to_file[future]
                try:
                    info = future.result()
                    if info:
                        services.append(info)
                        print(f'  [Worker Completed] {f_path.name}')
                except Exception as e:
                    logger.error(f'  [Worker Failed] {f_path.name}: {e}')
        services.sort(key=lambda x: x['name'])
        system_summary = self._generate_system_summary(services)
        content = self._format_markdown(services, system_summary)
        out_path = self.root / output_file
        out_path.write_text(content, encoding='utf-8')
        logger.info(f'✅ Catalog generated: {out_path} ({len(services)} services)')
        return {'path': str(out_path), 'service_count': len(services)}

    def _inspect_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Worker Task: AST Parse -> AI Enrichment.
        """
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
            meta = {'filename': file_path.name, 'name': file_path.stem, 'description': '', 'tags': [], 'endpoints': [], 'ai_enriched': False}
            target_node = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and 'MS' in node.name:
                    target_node = node
                    break
            if not target_node:
                return None
            meta['name'] = target_node.name
            meta['description'] = ast.get_docstring(target_node) or ''
            if ENABLE_AI and len(meta['description']) < 10:
                prompt = f'Read this Python class and write a 1-sentence description of its purpose. Be technical and concise.\n\nCode snippet:\n{source[:2000]}'
                ai_desc = self._query_ollama(MODEL_WORKER, prompt)
                if ai_desc:
                    meta['description'] = f'✨ {ai_desc}'
                    meta['ai_enriched'] = True
            for item in target_node.body:
                if isinstance(item, ast.FunctionDef) and (not item.name.startswith('_')):
                    args = [a.arg for a in item.args.args if a.arg != 'self']
                    doc = ast.get_docstring(item) or ''
                    meta['endpoints'].append({'name': item.name, 'args': args, 'doc': doc.split('\n')[0]})
            return meta
        except Exception as e:
            logger.warning(f'Failed to inspect {file_path.name}: {e}')
            return None

    def _generate_system_summary(self, services: List[Dict]) -> str:
        """
        Architect Task: Analyzes the entire system map using the larger model.
        """
        if not ENABLE_AI:
            return 'Auto-generated catalog of available microservices.'
        logger.info(f'🧠 Architect ({MODEL_ARCHITECT}) is analyzing system structure...')
        service_list = '\n'.join([f"- {s['name']}: {s['description']}" for s in services])
        if len(service_list) > MAX_CONTEXT_CHARS:
            service_list = service_list[:MAX_CONTEXT_CHARS] + '\n...(truncated)...'
        prompt = f"You are a System Architect. Analyze this list of microservices. Write a brief 'Executive Summary' (max 150 words) that explains what this system is capable of. Group capabilities logically (e.g., 'UI Layer', 'Data Ingestion', 'Core Logic').\n\nService List:\n{service_list}"
        summary = self._query_ollama(MODEL_ARCHITECT, prompt)
        return summary or 'System analysis failed.'

    def _query_ollama(self, model: str, prompt: str) -> str:
        """Helper to hit local Ollama instance."""
        try:
            payload = {'model': model, 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.2, 'num_ctx': 4096}}
            timeout = 60 if model == MODEL_ARCHITECT else 20
            res = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
            if res.status_code == 200:
                return res.json().get('response', '').strip()
        except Exception:
            pass
        return ''

    def _format_markdown(self, services: List[Dict], summary: str) -> str:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        md = [f'# 📚 Microservice Library Card Catalogue', f'> **Generated**: {timestamp}', f'> **Total Services**: {len(services)}', f'> **Swarm Configuration**: `{MAX_WORKERS}` Workers (`{MODEL_WORKER}`), 1 Architect (`{MODEL_ARCHITECT}`)', '', '## 🧠 System Architecture Overview', summary, '', '## 📇 Index']
        for s in services:
            desc_short = s['description'].split('\n')[0][:80]
            md.append(f"- **[{s['name']}](#{s['name'].lower()})**: {desc_short}")
        md.append('\n---\n')
        for s in services:
            md.append(f"### {s['name']}")
            md.append(f"**File**: `{s['filename']}`")
            md.append(f"**Description**: {s['description']}")
            if s['endpoints']:
                md.append('\n| Endpoint | Inputs | Summary |')
                md.append('| :--- | :--- | :--- |')
                for ep in s['endpoints']:
                    args_str = ', '.join(ep['args']) or 'None'
                    md.append(f"| `{ep['name']}` | `{args_str}` | {ep['doc']} |")
            md.append('\n---\n')
        return '\n'.join(md)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    lib = LibrarianMS()
    print('Service Ready:', lib)
    res = lib.generate_catalog()
    print(f"Catalog created at: {res['path']}")
```

---

## FILE: `.microservice-library/services/_LibrarianServiceMS.py`

```python
"""
SERVICE_NAME: _LibrarianMS
ENTRY_POINT: _LibrarianMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: requests
"""
import importlib.util
import time
if importlib.util.find_spec('requests') is None:
    print('! MISSING DEPENDENCY: pip install requests')
import ast
import os
import datetime
import logging
import requests
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
ENABLE_AI = True
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL_WORKER = 'qwen2.5-coder:1.5b-cpu'
MODEL_ARCHITECT = 'qwen2.5-coder:3b-cpu'
MAX_WORKERS = 4
MAX_CONTEXT_CHARS = 16000
logger = logging.getLogger('Librarian')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

@service_metadata(name='Librarian', version='3.0.0', description="Uses a swarm of local AI models to generate a 'Card Catalogue'.", tags=['documentation', 'ai', 'catalog', 'swarm'], capabilities=['filesystem:read', 'filesystem:write', 'network:outbound', 'compute:parallel'], internal_dependencies=['microservice_std_lib'], external_dependencies=['requests'], side_effects=[])
class LibrarianMS:

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.root = Path(self.config.get('root_path', '.')).resolve()

    @service_endpoint(inputs={'output_file': 'str'}, outputs={'path': 'str', 'service_count': 'int'}, description='Unleashes the AI swarm to generate a catalog.', tags=['catalog', 'generate'])
    def generate_catalog(self, output_file: str='LIBRARY_CATALOGUE.md') -> Dict[str, Any]:
        services = []
        print(f'\n🚀 LAUNCHING SWARM (Workers: {MAX_WORKERS} | Model: {MODEL_WORKER})...')
        ms_files = list(self.root.glob('*MS.py'))
        targets = [f for f in ms_files if f.name.startswith('_')]
        print(f'🎯 Targets acquired: {len(targets)} microservices.\n')
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_file = {executor.submit(self._inspect_file, f): f for f in targets}
            for future in concurrent.futures.as_completed(future_to_file):
                f_path = future_to_file[future]
                try:
                    info = future.result()
                    if info:
                        services.append(info)
                        print(f'  ✨ Indexed: {f_path.name}')
                except Exception as e:
                    print(f'  ❌ Failed: {f_path.name} - {e}')
        services.sort(key=lambda x: x['name'])
        system_summary = self._generate_system_summary(services)
        content = self._format_markdown(services, system_summary)
        out_path = self.root / output_file
        out_path.write_text(content, encoding='utf-8')
        print(f'\n✅ CATALOG GENERATED: {out_path}')
        return {'path': str(out_path), 'service_count': len(services)}

    def _inspect_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
            meta = {'filename': file_path.name, 'name': file_path.stem, 'description': '', 'endpoints': [], 'ai_enriched': False}
            target_node = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and 'MS' in node.name:
                    target_node = node
                    break
            if not target_node:
                return None
            meta['name'] = target_node.name
            meta['description'] = ast.get_docstring(target_node) or ''
            if ENABLE_AI and len(meta['description']) < 10:
                prompt = f'Read this Python class. Write a 1-sentence technical description.\n\nCode:\n{source[:2000]}'
                ai_desc = self._query_ollama(MODEL_WORKER, prompt)
                if ai_desc:
                    meta['description'] = f'✨ {ai_desc}'
                    meta['ai_enriched'] = True
            for item in target_node.body:
                if isinstance(item, ast.FunctionDef) and (not item.name.startswith('_')):
                    args = [a.arg for a in item.args.args if a.arg != 'self']
                    doc = ast.get_docstring(item) or ''
                    meta['endpoints'].append({'name': item.name, 'args': args, 'doc': doc.split('\n')[0]})
            return meta
        except Exception:
            return None

    def _generate_system_summary(self, services: List[Dict]) -> str:
        if not ENABLE_AI:
            return 'Auto-generated catalog.'
        print(f'\n🧠 Architect ({MODEL_ARCHITECT}) is analyzing system structure...')
        service_list = '\n'.join([f"- {s['name']}: {s['description']}" for s in services])
        if len(service_list) > MAX_CONTEXT_CHARS:
            service_list = service_list[:MAX_CONTEXT_CHARS] + '\n...(truncated)...'
        prompt = f"You are a System Architect. Analyze this microservice library. Write a brief 'Executive Summary' (max 150 words) grouping capabilities.\n\nServices:\n{service_list}"
        return self._query_ollama(MODEL_ARCHITECT, prompt) or 'Analysis failed.'

    def _query_ollama(self, model: str, prompt: str) -> str:
        try:
            res = requests.post(OLLAMA_URL, json={'model': model, 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.2, 'num_ctx': 4096}}, timeout=60)
            if res.status_code == 200:
                return res.json().get('response', '').strip()
        except:
            pass
        return ''

    def _format_markdown(self, services: List[Dict], summary: str) -> str:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        md = [f'# 📚 Microservice Library Codex', f'> **Generated**: {timestamp}', f'> **Services**: {len(services)}', '', '## 🧠 System Architecture', summary, '', '## 📇 Index']
        for s in services:
            md.append(f"- **[{s['name']}](#{s['name'].lower()})**: {s['description'].split(chr(10))[0][:80]}")
        md.append('\n---\n')
        for s in services:
            md.append(f"### {s['name']}\n**File**: `{s['filename']}`\n\n{s['description']}\n")
            if s['endpoints']:
                md.append('| Endpoint | Inputs | Summary |\n|---|---|---|')
                for ep in s['endpoints']:
                    md.append(f"| `{ep['name']}` | `{', '.join(ep['args'])}` | {ep['doc']} |")
            md.append('\n---\n')
        return '\n'.join(md)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    lib = LibrarianMS()
    lib.generate_catalog()
```

---

## FILE: `.microservice-library/services/_LogViewMS.py`

```python
import tkinter as tk
from tkinter import scrolledtext, filedialog
import queue
import logging
import datetime
from typing import Any, Dict, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time

class QueueHandler(logging.Handler):
    """
    Sends log records to a thread-safe queue.
    Used to bridge the gap between Python's logging system and the Tkinter UI.
    """

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)


@service_metadata(name='LogView', version='1.0.0', description='A thread-safe log viewer widget for Tkinter.', tags=['ui', 'logs', 'widget'], capabilities=['ui:gui', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['ui:update', 'filesystem:write', 'ui:dialog'])
class LogViewMS(tk.Frame):
    """
    The Console: A professional log viewer widget.
    Features:
    - Thread-safe (consumes from a Queue).
    - Message Consolidation ("Error occurred (x5)").
    - Level Filtering (Toggle INFO/DEBUG/ERROR).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        parent = self.config.get('parent')
        super().__init__(parent)
        self.log_queue: queue.Queue = self.config.get('log_queue')
        if self.log_queue is None:
            self.log_queue = queue.Queue()
        self.last_msg = None
        self.last_count = 0
        self.last_line_index = None
        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        toolbar = tk.Frame(self, bg='#2d2d2d', height=30)
        toolbar.pack(fill='x', side='top')
        self.filters = {'INFO': tk.BooleanVar(value=True), 'DEBUG': tk.BooleanVar(value=True), 'WARNING': tk.BooleanVar(value=True), 'ERROR': tk.BooleanVar(value=True)}
        for level, var in self.filters.items():
            cb = tk.Checkbutton(toolbar, text=level, variable=var, bg='#2d2d2d', fg='white', selectcolor='#444', activebackground='#2d2d2d', activeforeground='white')
            cb.pack(side='left', padx=5)
        tk.Button(toolbar, text='Clear', command=self.clear, bg='#444', fg='white', relief='flat').pack(side='right', padx=5)
        tk.Button(toolbar, text='Save', command=self.save, bg='#444', fg='white', relief='flat').pack(side='right')
        self.text = scrolledtext.ScrolledText(self, state='disabled', bg='#1e1e1e', fg='#d4d4d4', font=('Consolas', 10), insertbackground='white')
        self.text.pack(fill='both', expand=True)
        self.text.tag_config('INFO', foreground='#d4d4d4')
        self.text.tag_config('DEBUG', foreground='#569cd6')
        self.text.tag_config('WARNING', foreground='#ce9178')
        self.text.tag_config('ERROR', foreground='#f44747')
        self.text.tag_config('timestamp', foreground='#608b4e')

    def _poll_queue(self):
        """Pulls logs from the queue and updates UI."""
        try:
            while True:
                record = self.log_queue.get_nowait()
                self._display(record)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    def _display(self, record):
        level = record.levelname
        if not self.filters.get(level, tk.BooleanVar(value=True)).get():
            return
        msg = record.getMessage()
        ts = datetime.datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        self.text.config(state='normal')
        if msg == self.last_msg:
            self.last_count += 1
        else:
            self.last_msg = msg
            self.last_count = 1
        self.text.insert('end', f'[{ts}] ', 'timestamp')
        self.text.insert('end', f'{msg}\n', level)
        self.text.see('end')
        self.text.config(state='disabled')

    @service_endpoint(inputs={}, outputs={}, description='Clears the log console.', tags=['ui', 'logs'], side_effects=['ui:update'])
    def clear(self):
        self.text.config(state='normal')
        self.text.delete('1.0', 'end')
        self.text.config(state='disabled')

    @service_endpoint(inputs={}, outputs={}, description='Opens a dialog to save logs to a file.', tags=['ui', 'filesystem'], side_effects=['filesystem:write', 'ui:dialog'])
    def save(self):
        path = filedialog.asksaveasfilename(defaultextension='.log', filetypes=[('Log Files', '*.log')])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.text.get('1.0', 'end'))
            except Exception as e:
                print(f'Save failed: {e}')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    root = tk.Tk()
    root.title('Log View Test')
    root.geometry('600x400')
    q = queue.Queue()
    logger = logging.getLogger('TestApp')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(QueueHandler(q))
    log_view = LogViewMS({'parent': root, 'log_queue': q})
    print('Service ready:', log_view)
    log_view.pack(fill='both', expand=True)

    def generate_noise():
        logger.info('System initializing...')
        logger.debug('Checking sensors...')
        logger.warning('Sensor 4 response slow.')
        logger.error('Connection failed!')
        root.after(2000, generate_noise)
    generate_noise()
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_MonacoHostMS.py`

```python
import importlib.util
import sys
import threading
import json
import logging
from typing import Any, Dict, Optional, Callable
import time
REQUIRED = ['webview']
MISSING = []
if importlib.util.find_spec('webview') is None:
    MISSING.append('pywebview')
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _MonacoHostMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
import webview
from microservice_std_lib import service_metadata, service_endpoint
logger = logging.getLogger('MonacoHost')
MONACO_HTML = '\n<!DOCTYPE html>\n<html>\n<head>\n    <meta charset="UTF-8">\n    <title>Monaco Host</title>\n    <style>\n        html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: #1e1e1e; font-family: sans-serif; }\n        #container { display: flex; flex-direction: column; height: 100%; }\n        #tabs { background: #252526; display: flex; overflow-x: auto; height: 35px; border-bottom: 1px solid #3e3e3e; }\n        .tab { \n            padding: 8px 15px; color: #969696; background: #2d2d2d; cursor: pointer; border-right: 1px solid #1e1e1e; font-size: 12px;\n            display: flex; align-items: center; white-space: nowrap;\n        }\n        .tab.active { background: #1e1e1e; color: #fff; border-top: 1px solid #007acc; }\n        .tab:hover { background: #323233; color: #fff; }\n        #editor { flex-grow: 1; }\n    </style>\n</head>\n<body>\n    <div id="container">\n        <div id="tabs"></div>\n        <div id="editor"></div>\n    </div>\n    <script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/min/vs/loader.js"></script>\n    <script>\n        require.config({ paths: { \'vs\': \'https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/min/vs\' }});\n        let editor;\n        let models = {}; \n        let currentPath = null;\n\n        require([\'vs/editor/editor.main\'], function() {\n            editor = monaco.editor.create(document.getElementById(\'editor\'), {\n                value: "# Monaco Editor Ready\\n",\n                language: \'python\',\n                theme: \'vs-dark\',\n                automaticLayout: true,\n                fontSize: 14\n            });\n\n            if (window.pywebview) window.pywebview.api.signal_editor_ready();\n\n            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, function() {\n                if (currentPath) {\n                    window.pywebview.api.save_file(currentPath, editor.getValue());\n                }\n            });\n        });\n\n        window.pywebview = window.pywebview || {};\n        window.pywebview.api = window.pywebview.api || {};\n\n        window.pywebview.api.open_in_tab = function(filepath, content) {\n            let ext = filepath.split(\'.\').pop();\n            let langMap = { \'py\': \'python\', \'js\': \'javascript\', \'html\': \'html\', \'json\': \'json\', \'css\': \'css\' };\n            let lang = langMap[ext] || \'plaintext\';\n\n            if (!models[filepath]) {\n                models[filepath] = monaco.editor.createModel(content, lang, monaco.Uri.file(filepath));\n                const tab = document.createElement(\'div\');\n                tab.className = \'tab\';\n                tab.innerText = filepath.split(/[\\\\/]/).pop();\n                tab.title = filepath;\n                tab.onclick = () => switchTo(filepath);\n                tab.dataset.path = filepath;\n                document.getElementById(\'tabs\').appendChild(tab);\n            }\n            switchTo(filepath);\n        };\n\n        window.pywebview.api.reveal_range = function(filepath, startLine, endLine) {\n            if (filepath !== currentPath) switchTo(filepath);\n            editor.revealLineInCenter(startLine);\n            editor.setSelection({ startLineNumber: startLine, startColumn: 1, endLineNumber: endLine, endColumn: 1000 });\n        };\n\n        function switchTo(filepath) {\n            if (!models[filepath]) return;\n            editor.setModel(models[filepath]);\n            currentPath = filepath;\n            document.querySelectorAll(\'.tab\').forEach(t => t.classList.toggle(\'active\', t.dataset.path === filepath));\n        }\n    </script>\n</body>\n</html>\n'

class MonacoApiBridge:
    """
    Acts as the bridge between Python and the JavaScript running inside the webview.
    Methods here are callable from JS via `window.pywebview.api.methodName()`.
    """

    def __init__(self):
        self._window = None
        self._ready_event = threading.Event()
        self.on_save_callback: Optional[Callable[[str, str], None]] = None

    def set_window(self, window):
        self._window = window

    def signal_editor_ready(self):
        """Called by JS when Monaco is fully loaded."""
        self._ready_event.set()
        logger.info('Monaco Editor reported ready.')

    def save_file(self, filepath: str, content: str):
        """Called by JS when Ctrl+S is pressed."""
        if self.on_save_callback:
            self.on_save_callback(filepath, content)
        else:
            logger.warning(f'Saved {filepath} (No callback registered)')

    def open_file_in_js(self, filepath: str, content: str):
        """Python helper to push data to JS."""
        self._ready_event.wait(timeout=10)
        if not self._window:
            return
        js = f'window.pywebview.api.open_in_tab({json.dumps(filepath)}, {json.dumps(content)})'
        self._window.evaluate_js(js)


@service_metadata(name='MonacoHost', version='1.1.0', description='Hosts an embedded Monaco Editor instance using PyWebview.', tags=['ui', 'editor', 'webview'], capabilities=['ui:gui'], internal_dependencies=['microservice_std_lib'], external_dependencies=['webview'], side_effects=['ui:window'])
class MonacoHostMS:
    """
    Hosts the Monaco Editor.
    This service spawns a GUI window and cannot be run in headless environments.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.api = MonacoApiBridge()
        self.window = None

    @service_endpoint(inputs={'title': 'str', 'width': 'int', 'height': 'int'}, outputs={}, description='Launches the editor window. Blocking call.', tags=['ui', 'launch'], side_effects=['ui:window'])
    def launch(self, title='Monaco Editor', width=1000, height=700, func=None):
        """
        Create and launch the window.
        :param func: Optional function to run in a separate thread after launch.
        """
        self.window = webview.create_window(title, html=MONACO_HTML, js_api=self.api, width=width, height=height)
        self.api.set_window(self.window)
        webview.start(func, debug=True) if func else webview.start(debug=True)

    def set_save_callback(self, callback: Callable[[str, str], None]):
        """Sets the function to trigger when Ctrl+S is pressed in the editor."""
        self.api.on_save_callback = callback

    def open_file(self, filepath: str, content: str):
        """Opens a file in the editor (must be called from a background thread or callback)."""
        self.api.open_file_in_js(filepath, content)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    host = MonacoHostMS()

    def background_actions():
        host.api._ready_event.wait()
        print('Opening demo file...')
        host.open_file('demo.py', "print('Hello World')\n# Try Ctrl+S to save!")
        host.set_save_callback(lambda p, c: print(f'File: {p} was saved with {len(c)} chars.'))
    print('Launching Monaco Host...')
    host.launch(func=background_actions)
```

---

## FILE: `.microservice-library/services/_NetworkLayoutMS.py`

```python
import importlib.util
import sys
import logging
from typing import List, Dict, Any, Tuple, Optional
import time
REQUIRED = ['networkx']
MISSING = []
for lib in REQUIRED:
    if importlib.util.find_spec(lib) is None:
        MISSING.append(lib)
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _NetworkLayoutMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
try:
    import networkx as nx
except ImportError:
    nx = None
from microservice_std_lib import service_metadata, service_endpoint
logger = logging.getLogger('NetLayout')

@service_metadata(name='NetworkLayout', version='1.0.0', description='Calculates visual (x,y) coordinates for graph nodes using NetworkX.', tags=['graph', 'layout', 'visualization'], capabilities=['compute'], internal_dependencies=['microservice_std_lib'], external_dependencies=['networkx'], side_effects=[])
class NetworkLayoutMS:
    """
    The Topologist: Calculates visual coordinates for graph nodes using
    server-side algorithms (NetworkX). 
    Useful for generating static map snapshots or pre-calculating positions 
    to offload client-side rendering.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        if nx is None:
            logger.error('NetworkX is not installed. Layout calculations will fail.')

    @service_endpoint(inputs={'nodes': 'List[str]', 'edges': 'List[Tuple]', 'algorithm': 'str'}, outputs={'positions': 'Dict[str, Tuple]'}, description='Computes (x, y) coordinates for the given graph nodes and edges.', tags=['graph', 'compute'], side_effects=[])
    def calculate_layout(self, nodes: List[str], edges: List[Tuple[str, str]], algorithm: str='spring', **kwargs) -> Dict[str, Tuple[float, float]]:
        """
        Computes (x, y) coordinates for the given graph.
        
        :param nodes: List of node IDs.
        :param edges: List of (source, target) tuples.
        :param algorithm: 'spring' (Force-directed) or 'circular'.
        :return: Dictionary {node_id: (x, y)}
        """
        if nx is None:
            return {}
        G = nx.DiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        logger.info(f"Computing layout for {len(nodes)} nodes, {len(edges)} edges using '{algorithm}'...")
        try:
            if algorithm == 'circular':
                pos = nx.circular_layout(G)
            else:
                k_val = kwargs.get('k', 0.15)
                iter_val = kwargs.get('iterations', 50)
                pos = nx.spring_layout(G, k=k_val, iterations=iter_val, seed=42)
            return {n: (float(p[0]), float(p[1])) for n, p in pos.items()}
        except Exception as e:
            logger.error(f'Layout calculation failed: {e}')
            return {}
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    layout = NetworkLayoutMS()
    print('Service ready:', layout)
    if nx:
        test_nodes = ['Main', 'Utils', 'Config', 'DB', 'Auth']
        test_edges = [('Main', 'Utils'), ('Main', 'Config'), ('Main', 'DB'), ('Main', 'Auth'), ('DB', 'Config'), ('Auth', 'DB')]
        positions = layout.calculate_layout(test_nodes, test_edges, k=0.5)
        print('--- Calculated Positions ---')
        for node, (x, y) in positions.items():
            print(f'{node:<10}: ({x: .4f}, {y: .4f})')
    else:
        print('Skipping test: NetworkX not found.')
```

---

## FILE: `.microservice-library/services/_NeuralGraphEngineMS.py`

```python
"""
SERVICE_NAME: _NeuralGraphEngineMS
ENTRY_POINT: _NeuralGraphEngineMS.py
INTERNAL_DEPENDENCIES: base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: pygame
"""
import pygame
import math
import random
import time
from typing import Dict, Any
pygame.font.init()
from microservice_std_lib import service_metadata, service_endpoint
from base_service import BaseService

@service_metadata(name='NeuralGraphEngineMS', version='1.1.0', description='The Cartographer: A physics-driven rendering engine for visualizing complex neural relationships in a 2D force-directed graph.', tags=['visualization', 'graph', 'pygame'], capabilities=['force-directed-layout', 'real-time-rendering'], side_effects=['ui:update', 'render:write'], internal_dependencies=['base_service', 'microservice_std_lib'], external_dependencies=['pygame'])
class NeuralGraphEngineMS(BaseService):

    def __init__(self, width, height, bg_color=(16, 16, 24)):
        super().__init__('NeuralGraphEngineMS')
        self.width = width
        self.start_time = time.time()
        self.height = height
        self.bg_color = bg_color
        self.surface = pygame.Surface((width, height))
        self.cam_x = 0
        self.cam_y = 0
        self.zoom = 1.0
        self.font = pygame.font.SysFont('Consolas', 12)
        self.nodes = []
        self.links = []
        self.dragged_node_idx = None
        self.hovered_node_idx = None
        self.settled = False

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float', 'nodes': 'int', 'settled': 'bool'}, description='Standardized health check to verify the operational state of the graph renderer.', tags=['diagnostic', 'health'])
    def get_health(self) -> Dict[str, Any]:
        """Returns the operational status of the NeuralGraphEngineMS."""
        return {'status': 'online', 'uptime': time.time() - self.start_time, 'nodes': len(self.nodes), 'settled': self.settled}

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height))

    @service_endpoint(inputs={'nodes': 'list', 'links': 'list'}, outputs={}, description='Injects new node and edge data into the engine and wakes up the physics simulation.', tags=['data', 'update'], side_effects=['graph:write'])
    def set_data(self, nodes, links):
        self.nodes = nodes
        self.links = links
        self.settled = False
        node_map = {node['id']: node for node in self.nodes}
        for n in self.nodes:
            if 'gnn_x' in n and 'gnn_y' in n:
                n['x'] = n['gnn_x'] * self.width
                n['y'] = n['gnn_y'] * self.height
            elif 'x' not in n:
                parent_id = n.get('meta', {}).get('parent')
                if parent_id and parent_id in node_map and ('x' in node_map[parent_id]):
                    p = node_map[parent_id]
                    angle = random.random() * 6.28
                    dist = 30
                    n['x'] = p['x'] + math.cos(angle) * dist
                    n['y'] = p['y'] + math.sin(angle) * dist
                else:
                    n['x'] = random.randint(int(self.width * 0.2), int(self.width * 0.8))
                    n['y'] = random.randint(int(self.height * 0.2), int(self.height * 0.8))
            if 'vx' not in n:
                n['vx'] = 0
            if 'vy' not in n:
                n['vy'] = 0
            if n.get('type') == 'file':
                n['_color'] = (0, 122, 204)
                n['_radius'] = 6
            elif n.get('type') == 'web':
                n['_color'] = (204, 0, 122)
                n['_radius'] = 7
            elif n.get('type') == 'chunk':
                n['_color'] = (100, 200, 100)
                n['_radius'] = 3
            else:
                n['_color'] = (160, 32, 240)
                n['_radius'] = 6

    def screen_to_world(self, sx, sy):
        cx, cy = (self.width / 2, self.height / 2)
        wx = (sx - cx) / self.zoom + cx - self.cam_x
        wy = (sy - cy) / self.zoom + cy - self.cam_y
        return (wx, wy)

    def get_node_at(self, sx, sy):
        wx, wy = self.screen_to_world(sx, sy)
        for n in self.nodes:
            dist = math.hypot(n['x'] - wx, n['y'] - wy)
            if dist < n['_radius'] * 2:
                return n
        return None

    def handle_mouse_down(self, x, y):
        wx, wy = self.screen_to_world(x, y)
        for i, n in enumerate(self.nodes):
            dist = math.hypot(n['x'] - wx, n['y'] - wy)
            if dist < n['_radius'] * 2:
                self.dragged_node_idx = i
                self.settled = False
                return True
        return False

    def handle_mouse_move(self, x, y, is_dragging):
        wx, wy = self.screen_to_world(x, y)
        if is_dragging and self.dragged_node_idx is not None:
            node = self.nodes[self.dragged_node_idx]
            node['x'] = wx
            node['y'] = wy
            node['vx'] = 0
            node['vy'] = 0
            self.settled = False
        else:
            prev_hover = self.hovered_node_idx
            self.hovered_node_idx = None
            for i, n in enumerate(self.nodes):
                dist = math.hypot(n['x'] - wx, n['y'] - wy)
                if dist < n['_radius'] * 2:
                    self.hovered_node_idx = i
                    break
            return prev_hover != self.hovered_node_idx

    def handle_mouse_up(self):
        self.dragged_node_idx = None

    def pan(self, dx, dy):
        self.cam_x += dx / self.zoom
        self.cam_y += dy / self.zoom

    def zoom_camera(self, amount, mouse_x, mouse_y):
        self.zoom *= amount
        self.zoom = max(0.1, min(self.zoom, 5.0))

    def highlight_nodes(self, node_ids):
        """Highlights specific nodes by ID."""
        for n in self.nodes:
            if n.get('type') == 'file':
                n['_color'] = (0, 122, 204)
                n['_radius'] = 6
            elif n.get('type') == 'web':
                n['_color'] = (204, 0, 122)
                n['_radius'] = 7
            elif n.get('type') == 'chunk':
                n['_color'] = (100, 200, 100)
                n['_radius'] = 3
            else:
                n['_color'] = (160, 32, 240)
                n['_radius'] = 6
            if n['id'] in node_ids:
                n['_color'] = (255, 255, 0)
                n['_radius'] = 12
        self.settled = False

    @service_endpoint(inputs={}, outputs={'settled': 'bool'}, description='Performs one iteration of the force-directed physics calculation.', tags=['physics', 'lifecycle'], mode='async', side_effects=['graph:update'])
    def step_physics(self):
        if not self.nodes or self.settled:
            return
        REPULSION = 1000
        ATTRACTION = 0.01
        CENTER_GRAVITY = 0.01
        DAMPING = 0.85
        cx, cy = (self.width / 2, self.height / 2)
        total_kinetic_energy = 0
        for i, a in enumerate(self.nodes):
            if i == self.dragged_node_idx:
                continue
            if self.zoom < 1.2 and a.get('type') == 'chunk':
                a['vx'] = 0
                a['vy'] = 0
                continue
            fx, fy = (0, 0)
            fx += (cx - a['x']) * CENTER_GRAVITY
            fy += (cy - a['y']) * CENTER_GRAVITY
            for j, b in enumerate(self.nodes):
                if i == j:
                    continue
                dx = a['x'] - b['x']
                dy = a['y'] - b['y']
                dist_sq = dx * dx + dy * dy
                if dist_sq < 0.1:
                    dist_sq = 0.1
                if dist_sq > 25000:
                    continue
                f = REPULSION / dist_sq
                dist = math.sqrt(dist_sq)
                fx += dx / dist * f
                fy += dy / dist * f
            a['vx'] = (a['vx'] + fx) * DAMPING
            a['vy'] = (a['vy'] + fy) * DAMPING
        for u, v in self.links:
            a = self.nodes[u]
            b = self.nodes[v]
            dx = b['x'] - a['x']
            dy = b['y'] - a['y']
            fx = dx * ATTRACTION
            fy = dy * ATTRACTION
            if u != self.dragged_node_idx:
                a['vx'] += fx
                a['vy'] += fy
            if v != self.dragged_node_idx:
                b['vx'] -= fx
                b['vy'] -= fy
        for i, n in enumerate(self.nodes):
            if i == self.dragged_node_idx:
                continue
            n['x'] += n['vx']
            n['y'] += n['vy']
            total_kinetic_energy += abs(n['vx']) + abs(n['vy'])
        if total_kinetic_energy < 0.5:
            self.settled = True
        return self.settled

    @service_endpoint(inputs={}, outputs={'raw_data': 'bytes'}, description='Renders the current frame to a byte buffer for display in UI components.', tags=['render', 'output'], side_effects=['ui:update', 'render:write'])
    def get_image_bytes(self):
        self.surface.fill(self.bg_color)
        cx, cy = (self.width / 2, self.height / 2)

        def to_screen(x, y):
            sx = (x - cx + self.cam_x) * self.zoom + cx
            sy = (y - cy + self.cam_y) * self.zoom + cy
            return (int(sx), int(sy))
        for u, v in self.links:
            if self.zoom < 1.2:
                if self.nodes[u].get('type') == 'chunk' or self.nodes[v].get('type') == 'chunk':
                    continue
            start = to_screen(self.nodes[u]['x'], self.nodes[u]['y'])
            end = to_screen(self.nodes[v]['x'], self.nodes[v]['y'])
            pygame.draw.line(self.surface, (60, 60, 80), start, end, 1)
        for i, n in enumerate(self.nodes):
            if self.zoom < 1.2 and n.get('type') == 'chunk':
                continue
            sx, sy = to_screen(n['x'], n['y'])
            if sx < -20 or sx > self.width + 20 or sy < -20 or (sy > self.height + 20):
                continue
            rad = int(n['_radius'] * self.zoom)
            col = n['_color']
            if i == self.hovered_node_idx or i == self.dragged_node_idx:
                pygame.draw.circle(self.surface, (255, 255, 255), (sx, sy), rad + 2)
            pygame.draw.circle(self.surface, col, (sx, sy), rad)
            if self.zoom > 0.8 or i == self.hovered_node_idx:
                text = self.font.render(n['label'], True, (200, 200, 200))
                self.surface.blit(text, (sx + rad + 4, sy - 6))
        return pygame.image.tostring(self.surface, 'RGB')
```

---

## FILE: `.microservice-library/services/_NeuralGraphViewerMS.py`

```python
"""
SERVICE_NAME: _NeuralGraphViewerMS
ENTRY_POINT: _NeuralGraphViewerMS.py
INTERNAL_DEPENDENCIES: _NeuralGraphEngineMS, base_service, microservice_std_lib
EXTERNAL_DEPENDENCIES: PIL
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import sqlite3
import json
import os
from _NeuralGraphEngineMS import NeuralGraphEngineMS
from microservice_std_lib import service_metadata, service_endpoint
from base_service import BaseService
import time

@service_metadata(name='NeuralGraphViewerMS', version='1.0.0', description='The Lens: A Tkinter-based UI component that hosts the neural graph engine and provides search/highlighting overlays.', tags=['ui', 'visualization', 'tkinter'], capabilities=['graph-rendering', 'search-highlighting'], side_effects=['ui:update', 'filesystem:read'], internal_dependencies=['_NeuralGraphEngineMS', 'base_service', 'microservice_std_lib'], external_dependencies=['PIL'])
class NeuralGraphViewerMS(BaseService, ttk.Frame):

    def __init__(self, parent):
        BaseService.__init__(self, 'NeuralGraphViewerMS')
        ttk.Frame.__init__(self, parent)
        self.pack(fill='both', expand=True)
        self.controls = tk.Frame(self, bg='#101018')
        self.controls.pack(fill='x', side='top', padx=5, pady=5)
        self.entry_search = tk.Entry(self.controls, bg='#252526', fg='white', insertbackground='white', font=('Consolas', 10))
        self.entry_search.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.entry_search.bind('<Return>', self.run_search)
        btn = tk.Button(self.controls, text='NEURAL TEST', command=self.run_search, bg='#007ACC', fg='white', relief='flat')
        btn.pack(side='right')
        self.canvas_lbl = tk.Label(self, bg='#101018', cursor='crosshair')
        self.canvas_lbl.pack(fill='both', expand=True)
        self.cartridge = None
        self.neural = None
        self.engine = NeuralGraphEngineMS(800, 600)
        self.photo = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_dragging_node = False
        self.is_panning = False
        self.canvas_lbl.bind('<Button-1>', self.on_click)
        self.canvas_lbl.bind('<Double-Button-1>', self.on_double_click)
        self.canvas_lbl.bind('<ButtonRelease-1>', self.on_release)
        self.canvas_lbl.bind('<B1-Motion>', self.on_drag)
        self.canvas_lbl.bind('<Motion>', self.on_hover)
        self.canvas_lbl.bind('<Button-4>', lambda e: self.on_zoom(1.1))
        self.canvas_lbl.bind('<Button-5>', lambda e: self.on_zoom(0.9))
        self.canvas_lbl.bind('<MouseWheel>', self.on_windows_scroll)
        self.canvas_lbl.bind('<Configure>', self.on_resize)
        self.animate()

    def bind_services(self, cartridge, neural):
        self.cartridge = cartridge
        self.neural = neural

    @service_endpoint(inputs={'event': 'any'}, outputs={}, description='Triggers a neural search based on the entry field and highlights resulting nodes in the viewer.', tags=['ui-action', 'search'], side_effects=['ui:update', 'graph:highlight'])
    def run_search(self, event=None):
        if not self.cartridge or not self.neural:
            return
        query = self.entry_search.get().strip()
        if not query:
            return
        vec = self.neural.get_embedding(query)
        if not vec:
            return
        results = self.cartridge.search_embeddings(vec, limit=5)
        ids = set()
        for r in results:
            if 'vfs_path' in r and 'name' in r:
                ids.add(f"{r['vfs_path']}::{r['name']}")
        self.engine.highlight_nodes(ids)

    @service_endpoint(inputs={'db_path': 'str'}, outputs={}, description='Loads graph nodes and edges from a Cartridge database and triggers the physics engine.', tags=['data-load', 'sqlite'], side_effects=['filesystem:read'])
    def load_from_db(self, db_path):
        """
        Loads graph data from SQLite.
        Does NOT block the UI. The physics engine will settle the nodes frame-by-frame.
        """
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            db_nodes = cursor.execute('SELECT id, type, label, data_json FROM graph_nodes').fetchall()
            db_edges = cursor.execute('SELECT source, target FROM graph_edges').fetchall()
            conn.close()
        except Exception as e:
            print(f'Graph Load Error: {e}')
            return
        id_to_index = {}
        formatted_nodes = []
        for idx, row in enumerate(db_nodes):
            node_id, n_type, label, raw_json = row
            meta = {}
            try:
                if raw_json:
                    meta = json.loads(raw_json)
            except:
                pass
            id_to_index[node_id] = idx
            formatted_nodes.append({'id': node_id, 'type': n_type, 'label': label, 'meta': meta})
        formatted_links = []
        for src, tgt in db_edges:
            if src in id_to_index and tgt in id_to_index:
                formatted_links.append((id_to_index[src], id_to_index[tgt]))
        self.engine.set_data(formatted_nodes, formatted_links)

    def on_resize(self, event):
        if event.width > 1 and event.height > 1:
            self.engine.resize(event.width, event.height)

    def on_double_click(self, event):
        hit_node = self.engine.get_node_at(event.x, event.y)
        if hit_node:
            self.engine.cam_x = hit_node['x']
            self.engine.cam_y = hit_node['y']
            self.engine.zoom = 2.0
            self.engine.settled = False

    def on_click(self, event):
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        hit = self.engine.handle_mouse_down(event.x, event.y)
        if hit:
            self.is_dragging_node = True
        else:
            self.is_panning = True

    def on_release(self, event):
        self.engine.handle_mouse_up()
        self.is_dragging_node = False
        self.is_panning = False

    def on_drag(self, event):
        if self.is_dragging_node:
            self.engine.handle_mouse_move(event.x, event.y, True)
        elif self.is_panning:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            self.engine.pan(dx, dy)
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def on_hover(self, event):
        if not self.is_dragging_node:
            self.engine.handle_mouse_move(event.x, event.y, False)

    def on_zoom(self, amount):
        self.engine.zoom_camera(amount, 0, 0)
        self.engine.settled = False

    def on_windows_scroll(self, event):
        if event.delta > 0:
            self.on_zoom(1.1)
        else:
            self.on_zoom(0.9)

    @service_endpoint(inputs={}, outputs={}, description='The primary heartbeat loop that orchestrates frame-by-frame physics steps and UI blitting.', tags=['lifecycle', 'rendering'], mode='async', side_effects=['ui:update', 'render:write'])
    def animate(self):
        """
        The Heartbeat Loop.
        Runs at ~30 FPS. Handles Physics + Rendering.
        """
        self.engine.step_physics()
        raw_data = self.engine.get_image_bytes()
        if raw_data:
            img = Image.frombytes('RGB', (self.engine.width, self.engine.height), raw_data)
            self.photo = ImageTk.PhotoImage(img)
            self.canvas_lbl.configure(image=self.photo)
        self.after(30, self.animate)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    root = tk.Tk()
    root.title('NeuralGraphViewerMS Test')
    view = NeuralGraphViewerMS(root)
    print('Service ready:', view._service_info['name'])
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_NeuralServiceMS.py`

```python
import requests
import json
import concurrent.futures
import logging
from typing import Optional, Dict, Any, List
from microservice_std_lib import service_metadata, service_endpoint
import time
OLLAMA_API_URL = 'http://localhost:11434/api'
logger = logging.getLogger('NeuralService')

@service_metadata(name='NeuralService', version='1.0.0', description='The Brain Interface: Orchestrates local AI operations via Ollama.', tags=['ai', 'neural', 'inference', 'ollama'], capabilities=['text-generation', 'embeddings', 'parallel-processing'], internal_dependencies=['microservice_std_lib'], external_dependencies=['requests'], side_effects=['config:update', 'network:read'])
class NeuralServiceMS:
    """
    The Brain Interface: Orchestrates local AI operations via Ollama for inference and embeddings.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.max_workers = self.config.get('max_workers', 4)
        self.models = {'fast': 'qwen2.5-coder:1.5b-cpu', 'smart': 'qwen2.5:3b-cpu', 'embed': 'mxbai-embed-large:latest-cpu'}
        if 'models' in self.config:
            self.models.update(self.config['models'])

    @service_endpoint(inputs={'fast_model': 'str', 'smart_model': 'str', 'embed_model': 'str'}, outputs={'status': 'str'}, description='Updates the active model configurations on the fly.', tags=['config', 'write'], side_effects=['config:update'])
    def update_models(self, fast_model: str, smart_model: str, embed_model: str) -> Dict[str, str]:
        """Called by the UI Settings Modal to change models on the fly."""
        self.models['fast'] = fast_model
        self.models['smart'] = smart_model
        self.models['embed'] = embed_model
        logger.info(f'Models Updated: Fast={fast_model}, Smart={smart_model}')
        return {'status': 'success', 'config': str(self.models)}

    @service_endpoint(inputs={}, outputs={'models': 'List[str]'}, description='Fetches a list of available models from the local Ollama instance.', tags=['ai', 'read'], side_effects=['network:read'])
    def get_available_models(self) -> List[str]:
        """Fetches list from Ollama for the UI dropdown."""
        try:
            res = requests.get(f'{OLLAMA_API_URL}/tags', timeout=2)
            if res.status_code == 200:
                return [m['name'] for m in res.json().get('models', [])]
        except Exception as e:
            logger.error(f'Failed to fetch models: {e}')
            return []
        return []

    @service_endpoint(inputs={}, outputs={'is_alive': 'bool'}, description='Pings Ollama to verify connectivity.', tags=['health', 'read'], side_effects=['network:read'])
    def check_connection(self) -> bool:
        """Pings Ollama to see if it's alive."""
        try:
            requests.get(f'{OLLAMA_API_URL}/tags', timeout=2)
            return True
        except requests.RequestException:
            logger.error("Ollama connection failed. Is 'ollama serve' running?")
            return False

    @service_endpoint(inputs={'text': 'str'}, outputs={'embedding': 'list'}, description='Generates a vector embedding for the provided text.', tags=['nlp', 'vector', 'ai'], side_effects=['network:read'])
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generates a vector using the configured embedding model."""
        try:
            res = requests.post(f'{OLLAMA_API_URL}/embeddings', json={'model': self.models['embed'], 'prompt': text}, timeout=30)
            if res.status_code == 200:
                return res.json().get('embedding')
        except Exception as e:
            logger.error(f'Embedding failed: {e}')
        return None

    @service_endpoint(inputs={'prompt': 'str', 'tier': 'str', 'format_json': 'bool'}, outputs={'response': 'str'}, description='Requests synchronous text generation from a local LLM.', tags=['llm', 'inference'], side_effects=['network:read'])
    def request_inference(self, prompt: str, tier: str='fast', format_json: bool=False) -> str:
        """
        Synchronous inference request.
        tier: 'fast', 'smart', or other keys in self.models
        """
        model = self.models.get(tier, self.models['fast'])
        payload = {'model': model, 'prompt': prompt, 'stream': False}
        if format_json:
            payload['format'] = 'json'
        try:
            res = requests.post(f'{OLLAMA_API_URL}/generate', json=payload, timeout=60)
            if res.status_code == 200:
                return res.json().get('response', '').strip()
        except Exception as e:
            logger.error(f'Inference ({tier}) failed: {e}')
        return ''

    def process_parallel(self, items: List[Any], worker_func) -> List[Any]:
        """
        Helper to run a function across many items using a ThreadPool.
        Useful for batch ingestion.
        Note: Not exposed as an endpoint as it takes a function as an argument.
        """
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(worker_func, item): item for item in items}
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f'Worker task failed: {e}')
        return results
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    svc = NeuralServiceMS()
    print('Service ready:', svc)
    if svc.check_connection():
        print('Ollama Connection: OK')
        print(f'Models available: {svc.get_available_models()}')
        print('Testing Inference (Fast Tier)...')
        response = svc.request_inference('Why is the sky blue? Answer in 1 sentence.')
        print(f'Response: {response}')
    else:
        print('Ollama Connection: FAILED (Is Ollama running?)')
```

---

## FILE: `.microservice-library/services/_ProjectForgeMS.py`

```python
"""
SERVICE_NAME: _ProjectForgeMS
ENTRY_POINT: _ProjectForgeMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
logger = logging.getLogger('ProjectForge')

@service_metadata(name='ProjectForge', version='1.0.0', description='Scaffolding engine for creating new microservice projects or Python apps.', tags=['scaffolding', 'generator', 'filesystem'], capabilities=['filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['filesystem:write'])
class ProjectForgeMS:
    """
    The Blacksmith.
    Creates directory structures, stamps out boilerplate code, and injects dependencies.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.template_root = self.config.get('template_root')

    @service_endpoint(inputs={'parent_path': 'str', 'project_name': 'str', 'dependencies': 'List[str]', 'type': 'str'}, outputs={'path': 'str', 'status': 'str'}, description='Creates a new standardized Python project with the given specifications.', tags=['create', 'scaffold'], side_effects=['filesystem:write'])
    def forge_project(self, parent_path: str, project_name: str, dependencies: List[str]=None, project_type: str='microservice') -> Dict[str, Any]:
        """
        Stamps out a new project folder.
        """
        root = Path(parent_path).resolve()
        project_dir = root / project_name
        if project_dir.exists():
            raise FileExistsError(f'Directory already exists: {project_dir}')
        logger.info(f"Forging new project '{project_name}' at {project_dir}...")
        try:
            project_dir.mkdir(parents=True)
            (project_dir / 'src').mkdir()
            (project_dir / 'tests').mkdir()
            (project_dir / 'config').mkdir()
            self._create_readme(project_dir, project_name)
            self._create_requirements(project_dir, dependencies or [])
            self._create_gitignore(project_dir)
            if project_type == 'microservice':
                self._create_microservice_boilerplate(project_dir, project_name)
            else:
                self._create_standard_app_boilerplate(project_dir)
            return {'path': str(project_dir), 'status': 'created', 'name': project_name}
        except Exception as e:
            logger.error(f'Forge failed: {e}')
            raise e

    def _create_readme(self, root: Path, name: str):
        content = f'# {name}\n\nGenerated by ProjectForgeMS.\n\n## Overview\nTODO: Add description.\n'
        (root / 'README.md').write_text(content, encoding='utf-8')

    def _create_requirements(self, root: Path, deps: List[str]):
        base_deps = ['requests', 'logging']
        all_deps = sorted(list(set(base_deps + deps)))
        content = '\n'.join(all_deps)
        (root / 'requirements.txt').write_text(content, encoding='utf-8')

    def _create_gitignore(self, root: Path):
        content = '__pycache__/\n*.pyc\n.env\n.venv/\n.vscode/\n'
        (root / '.gitignore').write_text(content, encoding='utf-8')

    def _create_microservice_boilerplate(self, root: Path, name: str):
        content = f'"""\nSERVICE_NAME: _{name}MS\nENTRY_POINT: _{name}MS.py\nDEPENDENCIES: None\n"""\nfrom typing import Dict, Any, Optional\nfrom microservice_std_lib import service_metadata, service_endpoint\n\n@service_metadata(\n    name="{name}",\n    version="1.0.0",\n    description="Auto-generated microservice.",\n    tags=["new"],\n    capabilities=[]\n)\nclass {name}MS:\n    def __init__(self, config: Optional[Dict[str, Any]] = None):\n        self.config = config or {{}}\n\n    @service_endpoint(\n        inputs={{}},\n        outputs={{"message": "str"}},\n        description="Default endpoint.",\n        tags=["hello"]\n    )\n    def hello(self):\n        return {{"message": "Hello from {name}!"}}\n\nif __name__ == "__main__":\n    svc = {name}MS()\n    print("Service ready:", svc)\n'
        (root / 'src' / f'_{name}MS.py').write_text(content, encoding='utf-8')

    def _create_standard_app_boilerplate(self, root: Path):
        content = "def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()"
        (root / 'src' / 'app.py').write_text(content, encoding='utf-8')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    forge = ProjectForgeMS()
    try:
        forge.forge_project('.', 'TestForgedApp', ['pandas', 'numpy'])
        print('Test Project Created.')
        shutil.rmtree('TestForgedApp')
        print('Test Project Cleaned up.')
    except Exception as e:
        print(f'Test failed: {e}')
```

---

## FILE: `.microservice-library/services/_PromptOptimizerMS.py`

```python
import json
import logging
from typing import List, Dict, Any, Callable, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
REFINE_SYSTEM_PROMPT = 'You are a world-class prompt engineer. Given an original prompt and specific feedback, provide an improved, refined version of the prompt that incorporates the feedback. Return ONLY the refined prompt text, no preamble.'
VARIATION_SYSTEM_PROMPT = 'You are a creative AI assistant. Generate {num} innovative and diverse variations of the following prompt. Return the result as a valid JSON array of strings. Example: ["variation 1", "variation 2"]'
logger = logging.getLogger('PromptOpt')

DEFAULT_OLLAMA_URL = 'http://localhost:11434/api'


def _make_ollama_infer(model: str = 'phi3:mini', ollama_url: str = DEFAULT_OLLAMA_URL) -> Callable[[str], str]:
    """Returns a callable that sends a prompt to a local ollama model and returns the response text."""
    try:
        import requests as _requests
    except ImportError:
        return lambda x: 'Error: requests package not installed. pip install requests'

    def _infer(prompt: str) -> str:
        try:
            res = _requests.post(
                f'{ollama_url}/generate',
                json={'model': model, 'prompt': prompt, 'stream': False},
                timeout=60,
            )
            if res.status_code == 200:
                return res.json().get('response', '').strip()
            return f'Error: ollama returned status {res.status_code}'
        except Exception as e:
            return f'Error: {e}'

    return _infer


@service_metadata(name='PromptOptimizer', version='1.1.0', description='Uses a local LLM (ollama) to refine prompts or generate variations.', tags=['llm', 'prompt-engineering', 'optimization'], capabilities=['network:local'], internal_dependencies=['microservice_std_lib'], external_dependencies=['requests'], side_effects=['network:local'])
class PromptOptimizerMS:
    """
    The Tuner: Uses a local LLM to refine prompts or generate variations.

    Defaults to ollama at localhost:11434. Override by passing 'inference_func'
    in config, or set 'model' and 'ollama_url' to point at a different local model.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.start_time = time.time()
        custom_fn = self.config.get('inference_func')
        if custom_fn:
            self.infer: Callable[[str], str] = custom_fn
        else:
            model = self.config.get('model', 'llama3.1:8b')
            url = self.config.get('ollama_url', DEFAULT_OLLAMA_URL)
            self.infer = _make_ollama_infer(model, url)

    @service_endpoint(inputs={'draft_prompt': 'str', 'feedback': 'str'}, outputs={'refined_prompt': 'str'}, description='Rewrites a prompt based on feedback.', tags=['llm', 'refine'], side_effects=['network:outbound'])
    def refine_prompt(self, draft_prompt: str, feedback: str) -> str:
        """
        Rewrites a prompt based on feedback.
        """
        full_prompt = f'{REFINE_SYSTEM_PROMPT}\n\n[Original Prompt]:\n{draft_prompt}\n\n[Feedback]:\n{feedback}\n\n[Refined Prompt]:'
        logger.info('Refining prompt...')
        try:
            result = self.infer(full_prompt)
            return result.strip()
        except Exception as e:
            logger.error(f'Refinement failed: {e}')
            return draft_prompt

    @service_endpoint(inputs={'draft_prompt': 'str', 'num_variations': 'int', 'context_data': 'Dict'}, outputs={'variations': 'List[str]'}, description='Generates multiple versions of a prompt for testing.', tags=['llm', 'variations'], side_effects=['network:outbound'])
    def generate_variations(self, draft_prompt: str, num_variations: int=3, context_data: Optional[Dict[str, Any]]=None) -> List[str]:
        """
        Generates multiple versions of a prompt for testing.
        """
        meta_prompt = VARIATION_SYSTEM_PROMPT.format(num=num_variations)
        prompt_content = draft_prompt
        if context_data:
            prompt_content += f'\n\n--- Context ---\n{json.dumps(context_data, indent=2)}'
        full_prompt = f'{meta_prompt}\n\n[Original Prompt]:\n{prompt_content}\n\n[JSON Array of Variations]:'
        logger.info(f'Generating {num_variations} variations...')
        try:
            raw_response = self.infer(full_prompt)
            start = raw_response.find('[')
            end = raw_response.rfind(']') + 1
            if start == -1 or end == 0:
                logger.warning('No JSON array found in response. Returning raw response.')
                return [raw_response]
            clean_json = raw_response[start:end]
            variations = json.loads(clean_json)
            if isinstance(variations, list):
                return [str(v) for v in variations]
            return []
        except Exception as e:
            logger.error(f'Variation generation failed: {e}')
            return []
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    def mock_llm(prompt: str) -> str:
        if '[Refined Prompt]' in prompt:
            return 'You are a helpful assistant who speaks like a pirate. How may I help ye?'
        if '[JSON Array]' in prompt:
            return '["Variation A: Pirate Mode", "Variation B: Formal Mode", "Variation C: Concise Mode"]'
        return 'Error'
    optimizer = PromptOptimizerMS({'inference_func': mock_llm})
    print('Service ready:', optimizer)
    print('--- Test: Refine ---')
    draft = 'Help me.'
    feedback = 'Make it sound like a pirate.'
    refined = optimizer.refine_prompt(draft, feedback)
    print(f'Original: {draft}')
    print(f'Refined:  {refined}')
    print('\n--- Test: Variations ---')
    vars = optimizer.generate_variations(draft, num_variations=3)
    for i, v in enumerate(vars):
        print(f' {i + 1}. {v}')
```

---

## FILE: `.microservice-library/services/_PromptVaultMS.py`

```python
import importlib.util
import sys
import sqlite3
import json
import uuid
import logging
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import time
REQUIRED = ['pydantic', 'jinja2']
MISSING = []
for lib in REQUIRED:
    if importlib.util.find_spec(lib) is None:
        MISSING.append(lib)
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _PromptVaultMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
from pydantic import BaseModel
from jinja2 import Environment, BaseLoader
from microservice_std_lib import service_metadata, service_endpoint
DB_PATH = Path(__file__).parent / 'prompt_vault.db'
logger = logging.getLogger('PromptVault')

class PromptVersion(BaseModel):
    """A specific historical version of a prompt."""
    version_num: int
    content: str
    author: str
    timestamp: datetime.datetime
    embedding: Optional[List[float]] = None


class PromptTemplate(BaseModel):
    """The master record for a prompt."""
    id: str
    slug: str
    title: str
    description: Optional[str] = ''
    tags: List[str] = []
    latest_version_num: int
    versions: List[PromptVersion] = []

    @property
    def latest(self) -> PromptVersion:
        """Helper to get the most recent content."""
        if not self.versions:
            raise ValueError('No versions found.')
        return sorted(self.versions, key=lambda v: v.version_num)[-1]

@service_metadata(name='PromptVault', version='1.0.0', description='A persistent SQLite store for managing, versioning, and rendering AI prompts.', tags=['prompt', 'database', 'versioning', 'jinja'], capabilities=['db:sqlite', 'filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=['jinja2', 'pydantic'], side_effects=['db:write', 'db:read'])
class PromptVaultMS:
    """
    The Vault: A persistent SQLite store for managing, versioning, 
    and rendering AI prompts.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.db_path = Path(self.config.get('db_path', DB_PATH))
        self._init_db()
        self.jinja_env = Environment(loader=BaseLoader())

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Bootstraps the schema."""
        with self._get_conn() as conn:
            conn.execute('\n                CREATE TABLE IF NOT EXISTS templates (\n                    id TEXT PRIMARY KEY,\n                    slug TEXT UNIQUE NOT NULL,\n                    title TEXT NOT NULL,\n                    description TEXT,\n                    tags_json TEXT,\n                    latest_version INTEGER DEFAULT 1,\n                    created_at TIMESTAMP,\n                    updated_at TIMESTAMP\n                )\n            ')
            conn.execute('\n                CREATE TABLE IF NOT EXISTS versions (\n                    id TEXT PRIMARY KEY,\n                    template_id TEXT,\n                    version_num INTEGER,\n                    content TEXT,\n                    author TEXT,\n                    timestamp TIMESTAMP,\n                    embedding_json TEXT,\n                    FOREIGN KEY(template_id) REFERENCES templates(id)\n                )\n            ')

    @service_endpoint(inputs={'slug': 'str', 'title': 'str', 'content': 'str', 'author': 'str', 'tags': 'List[str]'}, outputs={'template': 'Dict'}, description='Creates a new prompt template with an initial version.', tags=['prompt', 'create'], side_effects=['db:write'])
    def create_template(self, slug: str, title: str, content: str, author: str='system', tags: List[str]=None) -> Dict[str, Any]:
        """Creates a new prompt template with an initial version 1."""
        tags = tags or []
        now = datetime.datetime.utcnow()
        t_id = str(uuid.uuid4())
        v_id = str(uuid.uuid4())
        try:
            with self._get_conn() as conn:
                conn.execute('INSERT INTO templates (id, slug, title, description, tags_json, latest_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (t_id, slug, title, '', json.dumps(tags), 1, now, now))
                conn.execute('INSERT INTO versions (id, template_id, version_num, content, author, timestamp) VALUES (?, ?, ?, ?, ?, ?)', (v_id, t_id, 1, content, author, now))
            logger.info(f'Created template: {slug}')
            tpl = self.get_template(slug)
            return tpl.dict() if tpl else {}
        except sqlite3.IntegrityError:
            raise ValueError(f"Template '{slug}' already exists.")

    @service_endpoint(inputs={'slug': 'str', 'content': 'str', 'author': 'str'}, outputs={'template': 'Dict'}, description='Adds a new version to an existing template.', tags=['prompt', 'update'], side_effects=['db:write'])
    def add_version(self, slug: str, content: str, author: str='user') -> Dict[str, Any]:
        """Adds a new version to an existing template."""
        current = self.get_template(slug)
        if not current:
            raise ValueError(f"Template '{slug}' not found.")
        new_ver = current.latest_version_num + 1
        now = datetime.datetime.utcnow()
        v_id = str(uuid.uuid4())
        with self._get_conn() as conn:
            conn.execute('INSERT INTO versions (id, template_id, version_num, content, author, timestamp) VALUES (?, ?, ?, ?, ?, ?)', (v_id, current.id, new_ver, content, author, now))
            conn.execute('UPDATE templates SET latest_version = ?, updated_at = ? WHERE id = ?', (new_ver, now, current.id))
        logger.info(f'Updated {slug} to v{new_ver}')
        tpl = self.get_template(slug)
        return tpl.dict() if tpl else {}

    @service_endpoint(inputs={'slug': 'str'}, outputs={'template': 'Optional[PromptTemplate]'}, description='Retrieves a full template with all history.', tags=['prompt', 'read'], side_effects=['db:read'])
    def get_template(self, slug: str) -> Optional[PromptTemplate]:
        """Retrieves a full template with all history."""
        with self._get_conn() as conn:
            row = conn.execute('SELECT * FROM templates WHERE slug = ?', (slug,)).fetchone()
            if not row:
                return None
            v_rows = conn.execute('SELECT * FROM versions WHERE template_id = ? ORDER BY version_num ASC', (row['id'],)).fetchall()
            versions = []
            for v in v_rows:
                versions.append(PromptVersion(version_num=v['version_num'], content=v['content'], author=v['author'], timestamp=v['timestamp']))
            return PromptTemplate(id=row['id'], slug=row['slug'], title=row['title'], description=row['description'], tags=json.loads(row['tags_json']), latest_version_num=row['latest_version'], versions=versions)

    @service_endpoint(inputs={'slug': 'str', 'context': 'Dict'}, outputs={'rendered_text': 'str'}, description='Fetches the latest version and renders it with Jinja2.', tags=['prompt', 'render'], side_effects=['db:read'])
    def render(self, slug: str, context: Optional[Dict[str, Any]]=None) -> str:
        """Fetches the latest version and renders it with Jinja2."""
        template = self.get_template(slug)
        if not template:
            raise ValueError(f"Template '{slug}' not found.")
        raw_text = template.latest.content
        jinja_template = self.jinja_env.from_string(raw_text)
        return jinja_template.render(**context or {})

    @service_endpoint(inputs={}, outputs={'slugs': 'List[str]'}, description='Lists all available prompt slugs.', tags=['prompt', 'list'], side_effects=['db:read'])
    def list_slugs(self) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute('SELECT slug FROM templates').fetchall()
            return [r[0] for r in rows]
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import os
    db_file = Path('test_prompt_vault.db')
    if db_file.exists():
        os.remove(db_file)
    vault = PromptVaultMS({'db_path': db_file})
    print('Service ready:', vault)
    print('--- Creating Prompt ---')
    vault.create_template(slug='greet_user', title='Greeting Protocol', content='Hello {{ name }}, welcome to the {{ system_name }}!', tags=['ui', 'onboarding'])
    print('--- Updating Prompt ---')
    vault.add_version('greet_user', 'Greetings, {{ name }}. System {{ system_name }} is online.')
    print('--- Rendering ---')
    final_text = vault.render('greet_user', {'name': 'Alice', 'system_name': 'Nexus'})
    print(f'Rendered Output: {final_text}')
    tpl = vault.get_template('greet_user')
    if tpl:
        print(f'Current Version: v{tpl.latest_version_num}')
        print(f'History: {[v.content for v in tpl.versions]}')
    if db_file.exists():
        os.remove(db_file)
```

---

## FILE: `.microservice-library/services/_PythonChunkerMS.py`

```python
import ast
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from microservice_std_lib import service_metadata, service_endpoint

@dataclass
class CodeChunk:
    name: str
    type: str
    content: str
    start_line: int
    end_line: int
    docstring: str = ''


@service_metadata(name='PythonChunker', version='1.2.0', description='The Python Surgeon: Specialist in Abstract Syntax Tree (AST) parsing for Python source code.', tags=['chunking', 'python', 'ast'], capabilities=['python-ast'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class PythonChunkerMS:
    """
    Specialized Python AST Chunker.
    Focuses exclusively on identifying classes and functions to preserve code logic.
    """

    def __init__(self, config: Dict[str, Any]=None):
        self.config = config or {}
        self.start_time = time.time()

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float', 'specialty': 'str'}, description='Standardized health check for the Python specialist service.', tags=['diagnostic', 'health'])
    def get_health(self) -> Dict[str, Any]:
        """Returns the operational status of the PythonChunkerMS."""
        return {'status': 'online', 'uptime': time.time() - self.start_time, 'specialty': 'python_ast'}

    @service_endpoint(inputs={'content': 'str'}, outputs={'chunks': 'List[Dict]'}, description='Primary entry point for high-fidelity Python-specific AST chunking.', tags=['processing', 'python'])
    def chunk(self, content: str) -> List[Dict[str, Any]]:
        """Parses Python source into semantic CodeChunks."""
        chunks = self._chunk_python(content)
        return [asdict(c) for c in chunks]

    def _chunk_python(self, source: str) -> List[CodeChunk]:
        chunks = []
        try:
            tree = ast.parse(source)
            lines = source.splitlines(keepends=True)

            def get_segment(node):
                start = node.lineno - 1
                end = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start + 1
                return (''.join(lines[start:end]), start + 1, end)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    text, s, e = get_segment(node)
                    doc = ast.get_docstring(node) or ''
                    chunks.append(CodeChunk(name=f'def {node.name}', type='function', content=text, start_line=s, end_line=e, docstring=doc))
                elif isinstance(node, ast.ClassDef):
                    text, s, e = get_segment(node)
                    doc = ast.get_docstring(node) or ''
                    chunks.append(CodeChunk(name=f'class {node.name}', type='class', content=text, start_line=s, end_line=e, docstring=doc))
            if not chunks and source.strip():
                chunks.append(CodeChunk(name='module_level', type='text', content=source, start_line=1, end_line=len(lines)))
        except SyntaxError:
            chunks.append(CodeChunk(name='syntax_error_fallback', type='text', content=source, start_line=1, end_line=source.count('\n') + 1))
        return chunks
if __name__ == '__main__':
    svc = PythonChunkerMS()
    print('Service ready:', svc)
    test_code = 'class Test:\n    def run(self):\n        pass'
    results = svc.chunk(test_code)
    for c in results:
        print(f"[{c['type']}] {c['name']} (Lines {c['start_line']}-{c['end_line']})")
```

---

## FILE: `.microservice-library/services/_RefineryServiceMS.py`

```python
import json
import re
import os
import time
import ast
import concurrent.futures
import logging
from typing import Dict, List, Any, Optional, Tuple
try:
    from _CartridgeServiceMS import CartridgeServiceMS
    from _NeuralServiceMS import NeuralServiceMS
    from _ChunkingRouterMS import ChunkingRouterMS
except ImportError:
    CartridgeServiceMS = Any
    NeuralServiceMS = Any
    ChunkingRouterMS = Any
from microservice_std_lib import service_metadata, service_endpoint
logger = logging.getLogger('RefineryService')

@service_metadata(name='RefineryService', version='1.1.0', description="The Night Shift: Processes 'RAW' files into semantic chunks and weaves them into a knowledge graph.", tags=['processing', 'refinery', 'graph', 'RAG'], capabilities=['smart-chunking', 'graph-weaving', 'parallel-embedding'], internal_dependencies=['_CartridgeServiceMS', '_ChunkingRouterMS', '_NeuralServiceMS', 'microservice_std_lib'], external_dependencies=[], side_effects=['cartridge:write', 'neural:inference'])
class RefineryServiceMS:
    """
    The Night Shift.
    Polls the DB for 'RAW' files and processes them into Chunks and Graph Nodes.

    Graph Enrichment:
    - Code: function/class nodes, resolved import edges when possible.
    - Docs: section/chapter nodes for long-form text (md/txt/rst).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.cartridge = self.config.get('cartridge')
        self.neural = self.config.get('neural')
        self.chunker = ChunkingRouterMS() if ChunkingRouterMS != Any else None
        self.start_time = time.time()
        self.import_pattern = re.compile('(?:from|import)\\s+([\\w\\.]+)|require\\([\'"]([\\w\\.\\-/]+)[\'"]\\)')
        self._module_index: Dict[str, str] = {}
        self._path_index: Dict[str, str] = {}
        self._index_built: bool = False
        self._md_heading = re.compile('^(#{1,6})\\s+(.+?)\\s*$')
        self._chapter_heading = re.compile('^\\s*(chapter|CHAPTER)\\s+([0-9]+|[IVXLC]+)\\b\\s*[:\\-]?\\s*(.*)$')
        if self.cartridge and self.neural:
            self._stamp_specs()

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float', 'cartridge_health': 'str'}, description='Standardized health check to verify the operational state of the Refinery service.', tags=['diagnostic', 'health'])
    def get_health(self) -> Dict[str, Any]:
        """Returns the operational status of the RefineryServiceMS."""
        cart_status = 'UNKNOWN'
        if self.cartridge:
            cart_status = 'CONNECTED'
        return {'status': 'online', 'uptime': time.time() - self.start_time, 'cartridge_health': cart_status}

    def _stamp_specs(self):
        """Writes the active Neural/Chunker configuration to the Manifest."""
        try:
            embed_model = getattr(self.neural, 'models', {}).get('embed', 'default')
            spec = {'provider': 'ollama', 'model': embed_model, 'dim': 1024, 'dtype': 'float32', 'distance': 'cosine'}
            if self.cartridge:
                self.cartridge.set_manifest('embedding_spec', spec)
        except Exception as e:
            logger.error(f'Failed to stamp specs: {e}')

    def _build_import_index(self):
        """Builds caches for resolving imports to VFS targets."""
        if self._index_built or not self.cartridge:
            return
        path_index: Dict[str, str] = {}
        module_index: Dict[str, str] = {}
        conn = self.cartridge._get_conn()
        try:
            rows = conn.execute('SELECT vfs_path FROM files').fetchall()
            for vp, in rows:
                if not vp:
                    continue
                vfs_path = str(vp).replace('\\', '/')
                path_index[vfs_path] = vfs_path
                if vfs_path.endswith('.py'):
                    mod = vfs_path[:-3].strip('/')
                    mod = mod.replace('/', '.')
                    if mod:
                        module_index[mod] = vfs_path
                    if vfs_path.endswith('/__init__.py'):
                        pkg = vfs_path[:-len('/__init__.py')].strip('/').replace('/', '.')
                        if pkg:
                            module_index[pkg] = vfs_path
        finally:
            conn.close()
        self._path_index = path_index
        self._module_index = module_index
        self._index_built = True

    @service_endpoint(inputs={'batch_size': 'int'}, outputs={'processed_count': 'int'}, description="Polls the database for files with 'RAW' status and processes them into chunks and graph nodes.", tags=['pipeline', 'batch'], side_effects=['cartridge:write', 'neural:inference'])
    def process_pending(self, batch_size: int=5) -> int:
        """Main loop. Returns number of files processed."""
        if not self.cartridge or not self.neural:
            logger.error('Refinery missing dependencies (Cartridge or Neural).')
            return 0
        pending = self.cartridge.get_pending_files(limit=batch_size)
        if not pending:
            return 0
        logger.info(f'Refining batch of {len(pending)} files...')
        for file_row in pending:
            self._refine_file(file_row)
        return len(pending)

    def _refine_file(self, row: Dict):
        file_id = row['id']
        vfs_path = row['vfs_path']
        content = row['content']
        if not content:
            self.cartridge.update_status(file_id, 'SKIPPED_BINARY')
            return
        try:
            chunks = self.chunker.chunk_file(content, vfs_path)
            chunk_texts = [c.content for c in chunks]
            pending_nodes: List[Tuple[str, str, str, Dict[str, Any]]] = []
            pending_edges: List[Tuple[str, str, str, float]] = []
            max_workers = getattr(self.neural, 'max_workers', 4)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                vectors = list(executor.map(self.neural.get_embedding, chunk_texts))
            conn = self.cartridge._get_conn()
            try:
                cursor = conn.cursor()
                for i, chunk in enumerate(chunks):
                    vector = vectors[i]
                    vec_blob = json.dumps(vector).encode('utf-8') if vector else None
                    cursor.execute('\n                        INSERT INTO chunks (file_id, chunk_index, content, embedding, name, type, start_line, end_line)\n                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n                        ', (file_id, i, chunk.content, vec_blob, chunk.name, chunk.type, chunk.start_line, chunk.end_line))
                    chunk_row_id = cursor.lastrowid
                    if vector:
                        try:
                            cursor.execute('INSERT INTO vec_items(rowid, embedding) VALUES (?, ?)', (chunk_row_id, json.dumps(vector)))
                        except Exception as ve:
                            logger.error(f'Vector Index Insert Failed: {ve}')
                    if chunk.type in ['class', 'function']:
                        node_id = f'{vfs_path}::{chunk.name}'
                        pending_nodes.append((node_id, 'chunk', chunk.name, {'parent': vfs_path, 'file_id': file_id, 'chunk_row_id': chunk_row_id, 'chunk_type': chunk.type, 'start_line': chunk.start_line, 'end_line': chunk.end_line}))
                        pending_edges.append((node_id, vfs_path, 'defined_in', 1.0))
                conn.commit()
            finally:
                conn.close()
            pending_nodes.append((vfs_path, 'file', vfs_path.split('/')[-1], {'path': vfs_path, 'file_id': file_id}))
            self._weave_sections(vfs_path, content)
            self._weave_imports(vfs_path, content)
            for nid, ntype, label, data in pending_nodes:
                self.cartridge.add_node(nid, ntype, label, data)
            for src, tgt, rel, w in pending_edges:
                self.cartridge.add_edge(src, tgt, rel, w)
            self.cartridge.update_status(file_id, 'REFINED')
        except Exception as e:
            logger.error(f'Refining failed for {vfs_path}: {e}')
            self.cartridge.update_status(file_id, 'ERROR', {'error': str(e)})

    def _extract_imports_python(self, source_path: str, content: str) -> List[Tuple[str, int, int]]:
        """Returns list of (module_or_path, level, lineno)."""
        out: List[Tuple[str, int, int]] = []
        try:
            tree = ast.parse(content)
        except Exception:
            return out
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias and alias.name:
                        out.append((alias.name, 0, getattr(node, 'lineno', 0)))
            elif isinstance(node, ast.ImportFrom):
                level = int(getattr(node, 'level', 0) or 0)
                mod = getattr(node, 'module', None) or ''
                if mod:
                    out.append((mod, level, getattr(node, 'lineno', 0)))
                else:
                    for alias in node.names:
                        if alias and alias.name:
                            out.append((alias.name, level, getattr(node, 'lineno', 0)))
        return out

    def _resolve_python_import(self, source_path: str, module: str, level: int) -> List[str]:
        """Resolve a python import to possible VFS target paths."""
        self._build_import_index()
        if level <= 0:
            if module in self._module_index:
                return [self._module_index[module]]
            return []
        src_dir = os.path.dirname(source_path).replace('\\', '/').strip('/')
        base_parts = src_dir.split('/') if src_dir else []
        pops = max(level - 1, 0)
        if pops > 0 and pops <= len(base_parts):
            base_parts = base_parts[:-pops]
        rel_base = '/'.join([p for p in base_parts if p])
        mod_path = module.replace('.', '/').strip('/')
        candidates: List[str] = []
        if rel_base:
            if mod_path:
                candidates.append(f'{rel_base}/{mod_path}.py')
                candidates.append(f'{rel_base}/{mod_path}/__init__.py')
            else:
                candidates.append(f'{rel_base}/__init__.py')
        elif mod_path:
            candidates.append(f'{mod_path}.py')
            candidates.append(f'{mod_path}/__init__.py')
        return [c for c in candidates if c in self._path_index]

    def _resolve_js_like_import(self, source_path: str, imp: str) -> List[str]:
        """Resolve require('./x') / import ... from './x' to VFS candidates."""
        self._build_import_index()
        sdir = os.path.dirname(source_path).replace('\\', '/').strip('/')
        raw = imp.strip().replace('\\', '/')
        if not (raw.startswith('.') or raw.startswith('/')):
            return []
        if raw.startswith('/'):
            rel = raw.lstrip('/')
        else:
            rel = os.path.normpath(os.path.join(sdir, raw)).replace('\\', '/').lstrip('./')
        ext_candidates = [rel]
        if not os.path.splitext(rel)[1]:
            ext_candidates.extend([rel + '.js', rel + '.ts', rel + '.json'])
            ext_candidates.extend([rel + '/index.js', rel + '/index.ts'])
        return [c for c in ext_candidates if c in self._path_index]

    def _weave_imports(self, source_path: str, content: str):
        """Scans content for imports and links them in the graph."""
        targets_resolved: List[str] = []
        if source_path.endswith('.py'):
            for mod, level, lineno in self._extract_imports_python(source_path, content):
                resolved = self._resolve_python_import(source_path, mod, level)
                if resolved:
                    for tgt in resolved:
                        self.cartridge.add_edge(source_path, tgt, 'imports_file', 1.0)
                        targets_resolved.append(tgt)
                else:
                    self.cartridge.add_edge(source_path, mod, 'imports_unresolved', 0.25)
            return
        for line in content.splitlines():
            match = self.import_pattern.search(line)
            if not match:
                continue
            imp = match.group(1) or match.group(2)
            if not imp:
                continue
            resolved = self._resolve_js_like_import(source_path, imp)
            if resolved:
                for tgt in resolved:
                    self.cartridge.add_edge(source_path, tgt, 'imports_file', 1.0)
                    targets_resolved.append(tgt)
            else:
                self.cartridge.add_edge(source_path, imp, 'imports_unresolved', 0.25)

    def _weave_sections(self, vfs_path: str, content: str):
        """Creates section/chapter nodes for long-form text and links them to the file node."""
        ext = os.path.splitext(vfs_path)[1].lower()
        if ext not in ('.md', '.markdown', '.txt', '.rst'):
            return
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            lineno = idx + 1
            m = self._md_heading.match(line)
            if m:
                hashes = m.group(1)
                title = (m.group(2) or '').strip()
                level = len(hashes)
                if title:
                    node_id = f'{vfs_path}::section::{lineno}:{title}'
                    self.cartridge.add_node(node_id, 'section', title, {'parent': vfs_path, 'level': level, 'line': lineno})
                    self.cartridge.add_edge(node_id, vfs_path, 'in_file', 1.0)
                continue
            c = self._chapter_heading.match(line)
            if c:
                chap_num = (c.group(2) or '').strip()
                chap_title = (c.group(3) or '').strip()
                title = f'Chapter {chap_num}' + (f': {chap_title}' if chap_title else '')
                node_id = f'{vfs_path}::chapter::{lineno}:{chap_num}'
                self.cartridge.add_node(node_id, 'section', title, {'parent': vfs_path, 'level': 1, 'line': lineno})
                self.cartridge.add_edge(node_id, vfs_path, 'in_file', 1.0)
if __name__ == '__main__':
    try:
        from _CartridgeServiceMS import CartridgeServiceMS
        from _NeuralServiceMS import NeuralServiceMS
        print('Initializing Dependencies...')
        c = CartridgeServiceMS({'db_path': ':memory:'})
        n = NeuralServiceMS()
        svc = RefineryServiceMS({'cartridge': c, 'neural': n})
        print('Service ready:', svc)
        print('Health Check:', svc.get_health())
    except ImportError:
        print('Dependencies not found. Run in project context.')
```

---

## FILE: `.microservice-library/services/_RegexWeaverMS.py`

```python
import re
import logging
from typing import Any, Dict, List, Optional, Set
from microservice_std_lib import service_metadata, service_endpoint
import time
PY_IMPORT = re.compile('^\\s*(?:from|import)\\s+([\\w\\.]+)')
JS_IMPORT = re.compile('(?:import\\s+.*?from\\s+[\\\'"]|require\\([\\\'"])([\\.\\/\\w\\-_]+)[\\\'"]')
logger = logging.getLogger('RegexWeaver')

@service_metadata(name='RegexWeaver', version='1.0.0', description='Fault-tolerant dependency extractor using Regex.', tags=['parsing', 'dependencies', 'regex'], capabilities=['compute'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class RegexWeaverMS:
    """
    The Weaver: A fault-tolerant dependency extractor.
    Uses Regex to find imports, making it faster and more permissive
    than AST parsers (works on broken code).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'content': 'str', 'language': 'str'}, outputs={'dependencies': 'List[str]'}, description='Scans code content for import statements.', tags=['parsing', 'dependencies'], side_effects=[])
    def extract_dependencies(self, content: str, language: str) -> List[str]:
        """
        Scans code content for import statements.
        :param language: 'python' or 'javascript' (includes ts/jsx).
        """
        dependencies: Set[str] = set()
        lines = content.splitlines()
        pattern = PY_IMPORT if language == 'python' else JS_IMPORT
        for line in lines:
            if line.strip().startswith(('#', '//')):
                continue
            if language == 'python':
                match = pattern.match(line)
            else:
                match = pattern.search(line)
            if match:
                raw_dep = match.group(1)
                clean_dep = raw_dep.split('.')[-1].split('/')[-1]
                dependencies.add(clean_dep)
        return sorted(list(dependencies))
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    weaver = RegexWeaverMS()
    print('Service ready:', weaver)
    py_code = '\n    import os\n    from backend.utils import helper\n    # from commented.out import ignore_me\n    import pandas as pd\n    '
    print(f"Python Deps: {weaver.extract_dependencies(py_code, 'python')}")
    js_code = "\n    import React from 'react';\n    const utils = require('./lib/utils');\n    // import hidden from 'hidden';\n    "
    print(f"JS Deps:     {weaver.extract_dependencies(js_code, 'javascript')}")
```

---

## FILE: `.microservice-library/services/_RoleManagerMS.py`

```python
import importlib.util
import sys
import sqlite3
import json
import uuid
import logging
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import time
REQUIRED = ['pydantic']
MISSING = []
for lib in REQUIRED:
    if importlib.util.find_spec(lib) is None:
        MISSING.append(lib)
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _RoleManagerMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
from pydantic import BaseModel
from microservice_std_lib import service_metadata, service_endpoint
DB_PATH = Path('roles.db')
logger = logging.getLogger('RoleManager')

class RoleModel(BaseModel):
    """Data model representing an Agent Persona."""
    id: str
    name: str
    description: Optional[str] = ''
    system_prompt: str
    knowledge_bases: List[str] = []
    memory_policy: str = 'scratchpad'
    created_at: datetime.datetime


@service_metadata(name='RoleManager', version='1.0.0', description='Manages Agent Personas (Roles), including System Prompts and Memory Settings.', tags=['roles', 'personas', 'db'], capabilities=['db:sqlite'], internal_dependencies=['microservice_std_lib'], external_dependencies=['pydantic'], side_effects=['db:write', 'db:read'])
class RoleManagerMS:
    """
    The Casting Director: Manages Agent Personas (Roles).
    Persists configuration for System Prompts, Attached KBs, and Memory Settings.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.db_path = Path(self.config.get('db_path', DB_PATH))
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('\n                CREATE TABLE IF NOT EXISTS roles (\n                    id TEXT PRIMARY KEY,\n                    name TEXT UNIQUE NOT NULL,\n                    description TEXT,\n                    system_prompt TEXT NOT NULL,\n                    knowledge_bases_json TEXT,\n                    memory_policy TEXT,\n                    created_at TIMESTAMP\n                )\n            ')

    @service_endpoint(inputs={'name': 'str', 'system_prompt': 'str', 'description': 'str', 'kbs': 'List[str]'}, outputs={'role': 'Dict'}, description='Creates a new Agent Persona.', tags=['roles', 'create'], side_effects=['db:write'])
    def create_role(self, name: str, system_prompt: str, description: str='', kbs: List[str]=None) -> Dict[str, Any]:
        """Creates a new Agent Persona."""
        role_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow()
        kbs_json = json.dumps(kbs or [])
        try:
            with self._get_conn() as conn:
                conn.execute('INSERT INTO roles (id, name, description, system_prompt, knowledge_bases_json, memory_policy, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (role_id, name, description, system_prompt, kbs_json, 'scratchpad', now))
            logger.info(f'Created Role: {name}')
            role = self.get_role(name)
            return role.dict() if role else {}
        except sqlite3.IntegrityError:
            raise ValueError(f"Role '{name}' already exists.")

    @service_endpoint(inputs={'name_or_id': 'str'}, outputs={'role': 'Optional[RoleModel]'}, description='Retrieves a role by Name or ID.', tags=['roles', 'read'], side_effects=['db:read'])
    def get_role(self, name_or_id: str) -> Optional[RoleModel]:
        """Retrieves a role by Name or ID."""
        with self._get_conn() as conn:
            row = conn.execute('SELECT * FROM roles WHERE id = ?', (name_or_id,)).fetchone()
            if not row:
                row = conn.execute('SELECT * FROM roles WHERE name = ?', (name_or_id,)).fetchone()
            if not row:
                return None
            return RoleModel(id=row['id'], name=row['name'], description=row['description'], system_prompt=row['system_prompt'], knowledge_bases=json.loads(row['knowledge_bases_json']), memory_policy=row['memory_policy'], created_at=row['created_at'])

    @service_endpoint(inputs={}, outputs={'roles': 'List[Dict]'}, description='Lists all available roles.', tags=['roles', 'read'], side_effects=['db:read'])
    def list_roles(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute('SELECT id, name, description FROM roles').fetchall()
            return [dict(r) for r in rows]

    @service_endpoint(inputs={'name': 'str'}, outputs={}, description='Deletes a role by name.', tags=['roles', 'delete'], side_effects=['db:write'])
    def delete_role(self, name: str):
        with self._get_conn() as conn:
            conn.execute('DELETE FROM roles WHERE name = ?', (name,))
        logger.info(f'Deleted Role: {name}')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import os
    test_db = Path('test_roles.db')
    if test_db.exists():
        os.remove(test_db)
    logging.basicConfig(level=logging.INFO)
    mgr = RoleManagerMS({'db_path': test_db})
    print('Service ready:', mgr)
    mgr.create_role(name='SeniorDev', system_prompt='You are a senior Python developer. Prefer Clean Code principles.', description='Expert coding assistant', kbs=['python_docs', 'project_repo'])
    role = mgr.get_role('SeniorDev')
    if role:
        print(f'Role: {role.name}')
        print(f'Prompt: {role.system_prompt}')
        print(f'KBs: {role.knowledge_bases}')
    if test_db.exists():
        os.remove(test_db)
```

---

## FILE: `.microservice-library/services/_SandboxManagerMS.py`

```python
import shutil
import hashlib
import os
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from microservice_std_lib import service_metadata, service_endpoint
import time
DEFAULT_EXCLUDES = {'node_modules', '.git', '__pycache__', '.venv', '.mypy_cache', '_logs', 'dist', 'build', '.vscode', '.idea', '_sandbox', '_project_library'}
logger = logging.getLogger('SandboxMgr')

@service_metadata(name='SandboxManager', version='1.0.0', description="The Safety Harness: Manages a 'Sandbox' mirror of a 'Live' project for safe experimentation.", tags=['filesystem', 'safety', 'versioning'], capabilities=['filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['filesystem:write', 'filesystem:read'])
class SandboxManagerMS:
    """
    The Safety Harness: Manages a 'Sandbox' mirror of a 'Live' project.
    Allows for safe experimentation, diffing, and atomic promotion of changes.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.live_root = Path(self.config.get('live_path', './project')).resolve()
        self.sandbox_root = Path(self.config.get('sandbox_path', './_sandbox')).resolve()

    @service_endpoint(inputs={'force': 'bool'}, outputs={}, description='Creates or resets the sandbox by mirroring the live project.', tags=['sandbox', 'reset'], side_effects=['filesystem:write'])
    def init_sandbox(self, force: bool=False):
        """
        Creates or resets the sandbox by mirroring the live project.
        """
        if self.sandbox_root.exists():
            if not force:
                raise FileExistsError(f'Sandbox already exists at {self.sandbox_root}')
            logger.info('Wiping existing sandbox...')
            shutil.rmtree(self.sandbox_root)
        logger.info(f'Cloning {self.live_root} -> {self.sandbox_root}...')
        self._mirror_tree(self.live_root, self.sandbox_root)
        logger.info('Sandbox initialized.')

    @service_endpoint(inputs={}, outputs={}, description='Discards all sandbox changes and re-syncs from live.', tags=['sandbox', 'reset'], side_effects=['filesystem:write'])
    def reset_sandbox(self):
        """
        Discards all sandbox changes and re-syncs from live.
        """
        self.init_sandbox(force=True)

    @service_endpoint(inputs={}, outputs={'diff': 'Dict[str, List[str]]'}, description='Compares Sandbox vs Live. Returns added, modified, and deleted files.', tags=['sandbox', 'diff'], side_effects=['filesystem:read'])
    def get_diff(self) -> Dict[str, List[str]]:
        """
        Compares Sandbox vs Live. Returns added, modified, and deleted files.
        """
        sandbox_files = self._scan_files(self.sandbox_root)
        live_files = self._scan_files(self.live_root)
        sandbox_paths = set(sandbox_files.keys())
        live_paths = set(live_files.keys())
        added = sorted(list(sandbox_paths - live_paths))
        deleted = sorted(list(live_paths - sandbox_paths))
        common = sandbox_paths.intersection(live_paths)
        modified = []
        for rel_path in common:
            if sandbox_files[rel_path] != live_files[rel_path]:
                modified.append(rel_path)
        modified.sort()
        return {'added': added, 'modified': modified, 'deleted': deleted}

    @service_endpoint(inputs={}, outputs={'added': 'int', 'modified': 'int', 'deleted': 'int'}, description='Applies changes from Sandbox to Live.', tags=['sandbox', 'promote'], side_effects=['filesystem:write'])
    def promote_changes(self) -> Tuple[int, int, int]:
        """
        Applies changes from Sandbox to Live.
        Returns (added_count, modified_count, deleted_count).
        """
        diff = self.get_diff()
        for rel_path in diff['added'] + diff['modified']:
            src = self.sandbox_root / rel_path
            dst = self.live_root / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        for rel_path in diff['deleted']:
            target = self.live_root / rel_path
            if target.exists():
                os.remove(target)
        logger.info(f"Promoted: {len(diff['added'])} added, {len(diff['modified'])} modified, {len(diff['deleted'])} deleted.")
        return (len(diff['added']), len(diff['modified']), len(diff['deleted']))

    def _mirror_tree(self, src_root: Path, dst_root: Path):
        """Recursive copy that respects the exclusion list."""
        if not dst_root.exists():
            dst_root.mkdir(parents=True, exist_ok=True)
        if not src_root.exists():
            return
        for item in src_root.iterdir():
            if item.name in DEFAULT_EXCLUDES:
                continue
            dst_path = dst_root / item.name
            if item.is_dir():
                self._mirror_tree(item, dst_path)
            else:
                shutil.copy2(item, dst_path)

    def _scan_files(self, root: Path) -> Dict[str, str]:
        """
        Scans directory and returns {relative_path: sha256_hash}.
        """
        file_map = {}
        if not root.exists():
            return {}
        for path in root.rglob('*'):
            if path.is_file() and (not self._is_excluded(path, root)):
                rel = str(path.relative_to(root)).replace('\\', '/')
                file_map[rel] = self._get_hash(path)
        return file_map

    def _is_excluded(self, path: Path, root: Path) -> bool:
        """Checks if any part of the path is in the exclusion list."""
        try:
            rel_parts = path.relative_to(root).parts
            return any((p in DEFAULT_EXCLUDES for p in rel_parts))
        except ValueError:
            return False

    def _get_hash(self, path: Path) -> str:
        """Fast SHA-256 for file content."""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return 'read_error'
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    base = Path('test_env')
    live = base / 'live_project'
    box = base / 'sandbox'
    if base.exists():
        shutil.rmtree(base)
    live.mkdir(parents=True)
    (live / 'main.py').write_text("print('v1')")
    (live / 'utils.py').write_text('def help(): pass')
    (live / 'node_modules').mkdir()
    (live / 'node_modules' / 'junk.js').write_text('junk')
    print('--- Initializing Sandbox ---')
    mgr = SandboxManagerMS({'live_path': str(live), 'sandbox_path': str(box)})
    mgr.init_sandbox()
    print('\n--- Modifying Sandbox ---')
    (box / 'main.py').write_text("print('v2')")
    (box / 'new_feature.py').write_text("print('new')")
    os.remove(box / 'utils.py')
    diff = mgr.get_diff()
    print(f"Diff Analysis:\n Added: {diff['added']}\n Modified: {diff['modified']}\n Deleted: {diff['deleted']}")
    print('\n--- Promoting Changes ---')
    mgr.promote_changes()
    print(f"Live 'main.py' content: {(live / 'main.py').read_text()}")
    print(f"Live 'utils.py' exists? {(live / 'utils.py').exists()}")
    if base.exists():
        shutil.rmtree(base)
```

---

## FILE: `.microservice-library/services/_ScoutMS.py`

```python
import os
import time
import requests
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

@service_metadata(name='Scout', version='1.0.0', description='The Scout: A depth-aware utility for recursively walking local file systems or crawling websites.', tags=['utility', 'scanner', 'crawler'], capabilities=['filesystem:read', 'web:crawl'], internal_dependencies=['microservice_std_lib'], external_dependencies=['bs4', 'requests'], side_effects=['filesystem:read', 'network:read'])
class ScoutMS:
    """
    The Scanner: Walks file systems OR crawls websites (Depth-Aware).
    """

    def __init__(self):
        self.IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', '.env', '.idea', '.vscode', 'dist', 'build', 'coverage', 'site-packages'}
        self.BINARY_EXTENSIONS = {'.pyc', '.pyd', '.exe', '.dll', '.so', '.dylib', '.class', '.jpg', '.jpeg', '.png', '.gif', '.ico', '.zip', '.tar', '.gz', '.docx', '.xlsx', '.db', '.sqlite', '.sqlite3'}
        self.visited_urls = set()

    def is_binary(self, file_path: str) -> bool:
        _, ext = os.path.splitext(file_path)
        if ext.lower() in self.BINARY_EXTENSIONS:
            return True
        return False

    @service_endpoint(inputs={'root_path': 'str', 'web_depth': 'int'}, outputs={'tree': 'dict'}, description='Main entry point to perform a recursive scan of a directory or a web crawl.', tags=['discovery', 'recursive'], side_effects=['filesystem:read', 'network:read'])
    def scan_directory(self, root_path: str, web_depth: int=0) -> Optional[Dict[str, Any]]:
        """
        Main Entry Point.
        :param root_path: File path or URL.
        :param web_depth: How many links deep to crawl (0 = single page).
        """
        if root_path.startswith('http://') or root_path.startswith('https://'):
            self.visited_urls.clear()
            return self._crawl_web_recursive(root_path, depth=web_depth, origin_domain=urlparse(root_path).netloc)
        target = os.path.abspath(root_path)
        if not os.path.exists(target):
            return None
        if not os.path.isdir(target):
            return self._create_node(target, is_dir=False)
        return self._scan_fs_recursive(target)

    def _crawl_web_recursive(self, url: str, depth: int, origin_domain: str) -> Dict[str, Any]:
        """
        Recursively fetches links.
        """
        parsed = urlparse(url)
        clean_path = parsed.path.strip('/')
        if not clean_path:
            clean_path = 'index.html'
        rel_path = f'web/{parsed.netloc}/{clean_path}'
        node = {'name': url, 'path': url, 'rel_path': rel_path, 'type': 'web', 'children': [], 'checked': True}
        if depth < 0 or url in self.visited_urls:
            return node
        self.visited_urls.add(url)
        if depth > 0 and BeautifulSoup:
            try:
                time.sleep(0.1)
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        full_url = urljoin(url, link['href'])
                        parsed = urlparse(full_url)
                        if parsed.netloc == origin_domain and parsed.scheme in ['http', 'https']:
                            if full_url not in self.visited_urls:
                                child_node = self._crawl_web_recursive(full_url, depth - 1, origin_domain)
                                node['children'].append(child_node)
            except Exception as e:
                node['error'] = str(e)
        return node

    def _scan_fs_recursive(self, current_path: str, root_path: str=None) -> Dict[str, Any]:
        if root_path is None:
            root_path = current_path
        node = self._create_node(current_path, is_dir=True, root_path=root_path)
        node['children'] = []
        try:
            with os.scandir(current_path) as it:
                entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
                for entry in entries:
                    if entry.is_dir() and entry.name in self.IGNORE_DIRS:
                        continue
                    if entry.name.startswith('.'):
                        continue
                    if entry.is_dir():
                        child = self._scan_fs_recursive(entry.path, root_path=root_path)
                        if child:
                            node['children'].append(child)
                    else:
                        node['children'].append(self._create_node(entry.path, is_dir=False, root_path=root_path))
        except PermissionError:
            node['error'] = 'Access Denied'
        return node

    def _create_node(self, path: str, is_dir: bool, root_path: str=None) -> Dict[str, Any]:
        name = os.path.basename(path)
        rel_path = name
        if root_path:
            try:
                rel_path = os.path.relpath(path, root_path).replace('\\', '/')
            except ValueError:
                pass
        node = {'name': name, 'path': path, 'rel_path': rel_path, 'type': 'folder' if is_dir else 'file', 'children': [], 'checked': False}
        return node

    @service_endpoint(inputs={'tree_node': 'dict'}, outputs={'file_list': 'list'}, description='Flattens a hierarchical tree node structure into a simple list of paths.', tags=['utility', 'processing'])
    def flatten_tree(self, tree_node: Dict[str, Any]) -> List[str]:
        files = []
        if tree_node['type'] in ['file', 'web']:
            files.append(tree_node['path'])
        elif 'children' in tree_node:
            for child in tree_node['children']:
                files.extend(self.flatten_tree(child))
        return files
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    svc = ScoutMS()
    print('Service ready:', svc)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tree = svc.scan_directory(current_dir)
    if tree:
        print(f'Scanned {len(svc.flatten_tree(tree))} files in current directory.')
```

---

## FILE: `.microservice-library/services/_SearchEngineMS.py`

```python
import importlib.util
import sqlite3
import struct
import requests
import os
import logging
from typing import List, Dict, Any, Optional
import time
REQUIRED = ['requests', 'sqlite_vec']
MISSING = []
for lib in REQUIRED:
    import_name = lib.replace('-', '_')
    if importlib.util.find_spec(import_name) is None:
        MISSING.append(lib)
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _SearchEngineMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
from microservice_std_lib import service_metadata, service_endpoint
DEFAULT_OLLAMA_URL = 'http://localhost:11434/api'
logger = logging.getLogger('SearchEngine')

@service_metadata(name='SearchEngine', version='1.0.0', description='The Oracle: Performs Hybrid Search (Vector Similarity + Keyword Matching) on SQLite databases.', tags=['search', 'vector', 'hybrid', 'rag'], capabilities=['db:sqlite', 'network:outbound', 'compute'], internal_dependencies=['microservice_std_lib'], external_dependencies=['requests', 'sqlite_vec'], side_effects=['db:read', 'network:outbound'])
class SearchEngineMS:
    """
    The Oracle: Performs Hybrid Search (Vector Similarity + Keyword Matching).
    
    Architecture:
    1. Vector Search: Uses sqlite-vec (vec0) for fast nearest neighbor search.
    2. Keyword Search: Uses SQLite FTS5 for BM25-style text matching.
    3. Reranking: Combines scores using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.model_name = self.config.get('model_name', 'nomic-embed-text:latest')
        self.ollama_url = self.config.get('ollama_url', DEFAULT_OLLAMA_URL)

    @service_endpoint(inputs={'db_path': 'str', 'query': 'str', 'limit': 'int'}, outputs={'results': 'List[Dict]'}, description='Main entry point. Returns a list of results sorted by relevance (RRF).', tags=['search', 'query'], side_effects=['db:read', 'network:outbound'])
    def search(self, db_path: str, query: str, limit: int=10) -> List[Dict[str, Any]]:
        """
        Main entry point. Returns a list of results sorted by relevance.
        """
        if not os.path.exists(db_path):
            logger.warning(f'Database not found at: {db_path}')
            return []
        conn = sqlite3.connect(db_path)
        try:
            conn.enable_load_extension(True)
            import sqlite_vec
            sqlite_vec.load(conn)
        except Exception as e:
            logger.warning(f'Warning: sqlite_vec not loaded. Vector search may fail. Error: {e}')
        cursor = conn.cursor()
        query_vec = self._get_query_embedding(query)
        if not query_vec:
            logger.info('Vectorization failed. Falling back to keyword-only search.')
            conn.close()
            return self._keyword_search_only(db_path, query, limit)
        vec_bytes = struct.pack(f'{len(query_vec)}f', *query_vec)
        sql = '\n        WITH \n        vec_matches AS (\n            SELECT rowid, distance,\n            row_number() OVER (ORDER BY distance) as rank\n            FROM knowledge_vectors\n            WHERE embedding MATCH ? \n            AND k = 50\n        ),\n        fts_matches AS (\n            SELECT rowid, rank as fts_score,\n            row_number() OVER (ORDER BY rank) as rank\n            FROM documents_fts\n            WHERE documents_fts MATCH ?\n            ORDER BY rank\n            LIMIT 50\n        )\n        SELECT \n            kc.file_path,\n            kc.content,\n            (\n                -- RRF Formula: 1 / (k + rank)\n                COALESCE(1.0 / (60 + v.rank), 0.0) +\n                COALESCE(1.0 / (60 + f.rank), 0.0)\n            ) as rrf_score\n        FROM knowledge_chunks kc\n        LEFT JOIN vec_matches v ON kc.id = v.rowid\n        LEFT JOIN fts_matches f ON kc.id = f.rowid\n        WHERE v.rowid IS NOT NULL OR f.rowid IS NOT NULL\n        ORDER BY rrf_score DESC\n        LIMIT ?;\n        '
        try:
            fts_query = f'"{query}"'
            rows = cursor.execute(sql, (vec_bytes, fts_query, limit)).fetchall()
        except sqlite3.OperationalError as e:
            logger.error(f'Search Error (likely missing schema or sqlite-vec): {e}')
            return []
        finally:
            conn.close()
        results = []
        for r in rows:
            path, content, score = r
            snippet = self._extract_snippet(content, query)
            results.append({'path': path, 'score': round(score, 4), 'snippet': snippet})
        return results

    def _keyword_search_only(self, db_path: str, query: str, limit: int) -> List[Dict[str, Any]]:
        """Fallback if embeddings are offline."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        sql = '\n            SELECT file_path, content\n            FROM documents_fts\n            WHERE documents_fts MATCH ?\n            ORDER BY rank\n            LIMIT ?\n        '
        try:
            rows = cursor.execute(sql, (f'"{query}"', limit)).fetchall()
            return [{'path': r[0], 'score': 0.0, 'snippet': self._extract_snippet(r[1], query)} for r in rows]
        except sqlite3.OperationalError as e:
            logger.error(f'Keyword Search Error: {e}')
            return []
        finally:
            conn.close()

    def _get_query_embedding(self, text: str) -> Optional[List[float]]:
        """Call Ollama to get the vector for the search query."""
        try:
            res = requests.post(f'{self.ollama_url}/embeddings', json={'model': self.model_name, 'prompt': text}, timeout=5)
            if res.status_code == 200:
                return res.json().get('embedding')
        except Exception as e:
            logger.error(f'Embedding request failed: {e}')
            return None
        return None

    def _extract_snippet(self, content: str, query: str) -> str:
        """Finds the best window of text around the keyword."""
        if not content:
            return ''
        lower_content = content.lower()
        parts = query.lower().split()
        lower_query = parts[0] if parts else ''
        idx = lower_content.find(lower_query)
        if idx == -1:
            return content[:200].replace('\n', ' ') + '...'
        start = max(0, idx - 60)
        end = min(len(content), idx + 140)
        snippet = content[start:end].replace('\n', ' ')
        return f'...{snippet}...'
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    print('Initializing Search Engine...')
    engine = SearchEngineMS({'model_name': 'phi3:mini-128k'})
    print('Service ready:', engine)
```

---

## FILE: `.microservice-library/services/_SemanticChunkerMS.py`

```python
import ast
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time

@dataclass
class CodeChunk:
    name: str
    type: str
    content: str
    start_line: int
    end_line: int
    docstring: str = ''


@service_metadata(name='SemanticChunker', version='1.0.0', description='The Surgeon: Intelligent Code Splitter that parses source code into logical semantic units (Classes, Functions) using AST.', tags=['utility', 'nlp', 'parser'], capabilities=['python-ast', 'semantic-chunking'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class SemanticChunkerMS:
    """
    Intelligent Code Splitter.
    Parses source code into logical units (Classes, Functions) 
    rather than arbitrary text windows.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'content': 'str', 'filename': 'str'}, outputs={'chunks': 'List[Dict]'}, description='Main entry point to split a file into semantic chunks based on its extension and content.', tags=['processing', 'chunking'], side_effects=[])
    def chunk_file(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """
        Splits file content into chunks.
        Returns a list of dictionaries suitable for JSON response.
        """
        chunks: List[CodeChunk] = []
        if filename.endswith('.py'):
            chunks = self._chunk_python(content)
        elif filename.lower().endswith(('.md', '.txt', '.pdf', '.html', '.htm', '.rst')):
            chunks = self._chunk_generic(content, window_size=800)
        else:
            chunks = self._chunk_generic(content, window_size=1500)
        return [asdict(c) for c in chunks]

    def _chunk_python(self, source: str) -> List[CodeChunk]:
        chunks = []
        try:
            tree = ast.parse(source)
            lines = source.splitlines(keepends=True)

            def get_segment(node):
                start = node.lineno - 1
                end = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start + 1
                return (''.join(lines[start:end]), start + 1, end)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    text, s, e = get_segment(node)
                    doc = ast.get_docstring(node) or ''
                    chunks.append(CodeChunk(name=f'def {node.name}', type='function', content=text, start_line=s, end_line=e, docstring=doc))
                elif isinstance(node, ast.ClassDef):
                    text, s, e = get_segment(node)
                    doc = ast.get_docstring(node) or ''
                    chunks.append(CodeChunk(name=f'class {node.name}', type='class', content=text, start_line=s, end_line=e, docstring=doc))
            if not chunks:
                return self._chunk_generic(source)
        except SyntaxError:
            return self._chunk_generic(source)
        return chunks

    def _chunk_generic(self, text: str, window_size: int=1500) -> List[CodeChunk]:
        """Sliding window for non-code files."""
        chunks = []
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        lines = text.splitlines(keepends=True)
        current_chunk = []
        current_size = 0
        chunk_idx = 1
        start_line = 1
        for i, line in enumerate(lines):
            current_chunk.append(line)
            current_size += len(line)
            if current_size >= window_size:
                chunks.append(CodeChunk(name=f'Chunk {chunk_idx}', type='text_block', content=''.join(current_chunk), start_line=start_line, end_line=i + 1))
                current_chunk = []
                current_size = 0
                chunk_idx += 1
                start_line = i + 2
        if current_chunk:
            chunks.append(CodeChunk(name=f'Chunk {chunk_idx}', type='text_block', content=''.join(current_chunk), start_line=start_line, end_line=len(lines)))
        return chunks
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    svc = SemanticChunkerMS()
    print('Service ready:', svc)
    test_code = "def hello():\n    print('world')\n\nclass Test:\n    pass"
    results = svc.chunk_file(test_code, 'test.py')
    print(f'Extracted {len(results)} semantic chunks.')
    for c in results:
        print(f" - [{c['type']}] {c['name']} ({c['start_line']}-{c['end_line']})")
        print(f" - [{c['type']}] {c['name']} ({c['start_line']}-{c['end_line']})")
```

---

## FILE: `.microservice-library/services/_ServiceRegistryMS.py`

```python
import ast
import json
import uuid
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
OUTPUT_FILE = 'registry.json'
logger = logging.getLogger('ServiceRegistry')

@service_metadata(name='ServiceRegistry', version='1.0.0', description='Scans a library of Python microservices and generates standardized JSON Service Tokens.', tags=['introspection', 'registry', 'parsing'], capabilities=['filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['filesystem:read', 'filesystem:write'])
class ServiceRegistryMS:
    """
    The Tokenizer (v2): Scans a library of Python microservices and generates
    standardized JSON 'Service Tokens'.
    Feature: Hybrid AST/Regex parsing for maximum robustness.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.root = Path(self.config.get('root_path', '.')).resolve()
        self.registry = []

    @service_endpoint(inputs={'save_to': 'str'}, outputs={'registry': 'List[Dict]'}, description='Scans the file system for microservices and builds a registry.', tags=['introspection', 'scan'], side_effects=['filesystem:read', 'filesystem:write'])
    def scan(self, save_to: str=OUTPUT_FILE) -> List[Dict[str, Any]]:
        logger.info(f'Scanning for microservices in: {self.root}')
        self.registry = []
        if self.root.exists():
            for item in self.root.iterdir():
                if item.is_dir() and item.name.startswith('_') and item.name.endswith('MS'):
                    self._process_folder(item)
                elif item.is_file() and item.name.startswith('_') and item.name.endswith('MS.py'):
                    token = self._tokenize_file(item)
                    if token:
                        self.registry.append(token)
        try:
            with open(save_to, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2)
            logger.info(f'✅ Registry built. Found {len(self.registry)} services. Saved to {save_to}')
        except Exception as e:
            logger.error(f'Failed to save registry: {e}')
        return self.registry

    def _process_folder(self, folder: Path):
        candidates = list(folder.glob('*.py'))
        for file in candidates:
            if file.name.startswith('__') or len(candidates) == 1:
                token = self._tokenize_file(file)
                if token:
                    self.registry.append(token)
                    logger.info(f"  + Tokenized: {token['name']}")
                    break

    def _tokenize_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            try:
                return self._ast_parse(source, file_path)
            except Exception:
                return self._regex_parse(source, file_path)
        except Exception as e:
            logger.warning(f'  - Failed to read {file_path.name}: {e}')
            return None

    def _ast_parse(self, source: str, file_path: Path):
        tree = ast.parse(source)
        target_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith('MS'):
                target_class = node
                break
        if not target_class:
            return None
        return self._build_token(name=target_class.name, doc=ast.get_docstring(target_class) or '', methods=[(n.name, [a.arg for a in n.args.args if a.arg != 'self'], ast.get_docstring(n) or '') for n in target_class.body if isinstance(n, ast.FunctionDef) and (not n.name.startswith('_'))], deps=self._extract_ast_imports(tree), file_path=file_path)

    def _regex_parse(self, source: str, file_path: Path):
        class_match = re.search('class\\s+(\\w+MS)', source)
        if not class_match:
            return None
        name = class_match.group(1)
        methods = []
        for match in re.finditer('def\\s+(\\w+)\\s*\\((.*?)\\):', source):
            m_name = match.group(1)
            if not m_name.startswith('_'):
                args = [a.strip().split(':')[0] for a in match.group(2).split(',') if a.strip() != 'self']
                methods.append((m_name, args, 'Regex extracted'))
        return self._build_token(name, 'Parsed via Regex', methods, [], file_path)

    def _build_token(self, name, doc, methods, deps, file_path):
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, 'microservice.library')
        token_id = f'MS_{uuid.uuid5(namespace, name).hex[:8].upper()}'
        method_dict = {m_name: {'args': m_args, 'doc': m_doc.strip()} for m_name, m_args, m_doc in methods}
        try:
            rel_path = str(file_path.relative_to(self.root)).replace('\\', '/')
        except ValueError:
            rel_path = file_path.name
        return {'token_id': token_id, 'name': name, 'path': rel_path, 'description': doc.strip(), 'methods': method_dict, 'dependencies': sorted(deps)}

    def _extract_ast_imports(self, tree):
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    deps.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.add(node.module.split('.')[0])
        return list(deps)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    svc = ServiceRegistryMS()
    print('Service ready:', svc)
    svc.scan()
```

---

## FILE: `.microservice-library/services/_SpinnerThingyMaBobberMS.py`

```python
import tkinter as tk
import math
import colorsys
import time
from typing import Optional, Dict, Any
from microservice_std_lib import service_metadata, service_endpoint

@service_metadata(name='SpinnerTHINGYMABOBBER', version='1.0.0', description='Interactive visual spinner widget for OBS/UI overlays.', tags=['ui', 'widget', 'visuals'], capabilities=['ui:gui'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['ui:block'])
class SpinnerThingyMaBobberMS:
    """
    The Visualizer: An interactive spinner widget.
    Useful for "Processing..." screens or OBS overlays.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.root = tk.Tk()
        self.root.title('OBS Interactive Spinner')
        self.root.configure(bg='black')
        self.root.geometry('600x600')
        self.canvas = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.angle_1 = 0
        self.angle_2 = 0
        self.angle_3 = 0
        self.hue = 0
        self.user_text = 'PROCESSING'
        self.cursor_visible = True
        self.last_cursor_toggle = time.time()
        self.root.bind('<Key>', self.handle_keypress)
        self.animate()

    @service_endpoint(inputs={}, outputs={}, description='Launches the GUI main loop.', tags=['ui', 'execution'], mode='sync', side_effects=['ui:block'])
    def launch(self):
        """Starts the Tkinter main event loop."""
        self.root.mainloop()

    def handle_keypress(self, event):
        if event.keysym == 'BackSpace':
            self.user_text = self.user_text[:-1]
        elif event.keysym == 'Escape':
            self.user_text = 'PROCESSING'
        elif len(event.char) == 1 and ord(event.char) >= 32:
            if len(self.user_text) < 25:
                self.user_text += event.char.upper()

    def get_neon_color(self, offset=0):
        h = (self.hue + offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'

    def draw_arc(self, cx, cy, radius, width, start, extent, color):
        x0 = cx - radius
        y0 = cy - radius
        x1 = cx + radius
        y1 = cy + radius
        self.canvas.create_arc(x0, y0, x1, y1, start=start, extent=extent, outline=color, width=width, style='arc')

    def animate(self):
        self.canvas.delete('all')
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            self.root.after(50, self.animate)
            return
        cx, cy = (w / 2, h / 2)
        base_size = min(w, h) / 2
        self.hue += 0.005
        if self.hue > 1:
            self.hue = 0
        c1 = self.get_neon_color(0.0)
        c2 = self.get_neon_color(0.3)
        c3 = self.get_neon_color(0.6)
        r1 = base_size * 0.85
        self.angle_1 -= 3
        for i in range(3):
            self.draw_arc(cx, cy, r1, base_size * 0.08, self.angle_1 + i * 120, 80, c1)
        r2 = base_size * 0.65
        self.angle_2 += 5
        self.draw_arc(cx, cy, r2, base_size * 0.05, self.angle_2, 160, c2)
        self.draw_arc(cx, cy, r2, base_size * 0.05, self.angle_2 + 180, 160, c2)
        r3 = base_size * 0.45
        self.angle_3 -= 8
        self.draw_arc(cx, cy, r3, base_size * 0.04, self.angle_3, 300, c3)
        if time.time() - self.last_cursor_toggle > 0.5:
            self.cursor_visible = not self.cursor_visible
            self.last_cursor_toggle = time.time()
        display_text = self.user_text + ('_' if self.cursor_visible else ' ')
        text_len = max(len(self.user_text), 1)
        scaling_factor = 1.0
        if text_len > 8:
            scaling_factor = 8 / text_len
        font_size = int(base_size * 0.15 * scaling_factor)
        font_size = max(font_size, 10)
        self.canvas.create_text(cx, cy, text=display_text, fill='white', font=('Courier', font_size, 'bold'))
        self.root.after(30, self.animate)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    print('Launching Spinner ThingyMaBobber...')
    svc = SpinnerThingyMaBobberMS()
    svc.launch()
```

---

## FILE: `.microservice-library/services/_SysInspectorMS.py`

```python
import platform
import subprocess
import sys
import datetime
import logging
from typing import Any, Dict, List, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
logger = logging.getLogger('SysInspector')

@service_metadata(name='SysInspector', version='1.0.0', description='Gathers hardware and environment statistics via shell commands.', tags=['system', 'audit', 'hardware'], capabilities=['os:shell', 'compute'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['os:read'])
class SysInspectorMS:
    """
    The Auditor: Gathers hardware and environment statistics.
    Supports: Windows (WMIC), Linux (lscpu/lspci), and macOS (sysctl/system_profiler).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={}, outputs={'report': 'str'}, description='Runs the full audit and returns a formatted string report.', tags=['system', 'report'], side_effects=['os:read'])
    def generate_report(self) -> str:
        """
        Runs the full audit and returns a formatted string report.
        """
        system_os = platform.system()
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report = [f'System Audit Report', f'Generated: {timestamp}', f'OS: {system_os} {platform.release()} ({platform.machine()})', '-' * 40, '']
        report.append('--- Hardware Information ---')
        if system_os == 'Windows':
            report.extend(self._audit_windows())
        elif system_os == 'Linux':
            report.extend(self._audit_linux())
        elif system_os == 'Darwin':
            report.extend(self._audit_mac())
        else:
            report.append('Unsupported Operating System for detailed hardware audit.')
        report.append('\n--- Software Environment ---')
        report.append(f'Python Version: {platform.python_version()}')
        report.append(f'Python Executable: {sys.executable}')
        return '\n'.join(report)

    def _run_cmd(self, cmd: str) -> str:
        """Helper to run shell commands safely."""
        try:
            result = subprocess.run(cmd, text=True, capture_output=True, check=False, shell=True, timeout=5)
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
            elif result.stderr:
                return f'[Cmd Error]: {result.stderr.strip()}'
            return '[No Output]'
        except Exception as e:
            return f'[Execution Error]: {e}'

    def _audit_windows(self) -> List[str]:
        data = []
        data.append('CPU: ' + self._run_cmd('wmic cpu get name'))
        data.append('GPU: ' + self._run_cmd('wmic path win32_videocontroller get name'))
        try:
            mem_str = self._run_cmd('wmic computersystem get totalphysicalmemory').splitlines()[-1]
            mem_bytes = int(mem_str)
            data.append(f'Memory: {mem_bytes / 1024 ** 3:.2f} GB')
        except:
            data.append('Memory: Could not retrieve total physical memory.')
        data.append('\nDisks:')
        data.append(self._run_cmd('wmic diskdrive get model,size'))
        return data

    def _audit_linux(self) -> List[str]:
        data = []
        data.append('CPU: ' + self._run_cmd("lscpu | grep 'Model name'"))
        data.append('GPU: ' + self._run_cmd('lspci | grep -i vga'))
        data.append('Memory:\n' + self._run_cmd('free -h'))
        data.append('\nDisks:\n' + self._run_cmd('lsblk -o NAME,SIZE,MODEL'))
        return data

    def _audit_mac(self) -> List[str]:
        data = []
        data.append('CPU: ' + self._run_cmd('sysctl -n machdep.cpu.brand_string'))
        data.append('GPU:\n' + self._run_cmd("system_profiler SPDisplaysDataType | grep -E 'Chipset Model|VRAM'"))
        data.append('Memory Details:\n' + self._run_cmd("system_profiler SPMemoryDataType | grep -E 'Size|Type|Speed'"))
        try:
            mem_bytes = int(self._run_cmd('sysctl -n hw.memsize'))
            data.append(f'Total Memory: {mem_bytes / 1024 ** 3:.2f} GB')
        except:
            pass
        data.append('\nDisks:\n' + self._run_cmd('diskutil list physical'))
        return data
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    inspector = SysInspectorMS()
    print('Service ready:', inspector)
    print('Running System Inspector...')
    print('\n' + inspector.generate_report())
```

---

## FILE: `.microservice-library/services/_TasklistVaultMS.py`

```python
import sqlite3
import uuid
import logging
import datetime
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal
from microservice_std_lib import service_metadata, service_endpoint
import time
DB_PATH = Path(__file__).parent / 'task_vault.db'
logger = logging.getLogger('TaskVault')
TaskStatus = Literal['Pending', 'Running', 'Complete', 'Error', 'Awaiting-Approval']

@service_metadata(name='TaskVault', version='1.0.0', description='Persistent SQLite engine for hierarchical task management.', tags=['tasks', 'db', 'project-management'], capabilities=['db:sqlite', 'filesystem:read', 'filesystem:write'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['db:write', 'db:read'])
class TasklistVaultMS:
    """
    The Taskmaster: A persistent SQLite engine for hierarchical task management.
    Supports infinite nesting of sub-tasks and status tracking.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.db_path = self.config.get('db_path', DB_PATH)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('\n                CREATE TABLE IF NOT EXISTS task_lists (\n                    id TEXT PRIMARY KEY,\n                    name TEXT NOT NULL,\n                    created_at TIMESTAMP\n                )\n            ')
            conn.execute("\n                CREATE TABLE IF NOT EXISTS tasks (\n                    id TEXT PRIMARY KEY,\n                    list_id TEXT NOT NULL,\n                    parent_id TEXT,\n                    content TEXT NOT NULL,\n                    status TEXT DEFAULT 'Pending',\n                    result TEXT,\n                    created_at TIMESTAMP,\n                    updated_at TIMESTAMP,\n                    FOREIGN KEY(list_id) REFERENCES task_lists(id) ON DELETE CASCADE,\n                    FOREIGN KEY(parent_id) REFERENCES tasks(id) ON DELETE CASCADE\n                )\n            ")

    @service_endpoint(inputs={'name': 'str'}, outputs={'list_id': 'str'}, description='Creates a new task list and returns its ID.', tags=['tasks', 'create'], side_effects=['db:write'])
    def create_list(self, name: str) -> str:
        """Creates a new task list and returns its ID."""
        list_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow()
        with self._get_conn() as conn:
            conn.execute('INSERT INTO task_lists (id, name, created_at) VALUES (?, ?, ?)', (list_id, name, now))
        logger.info(f"Created Task List: '{name}' ({list_id})")
        return list_id

    @service_endpoint(inputs={}, outputs={'lists': 'List[Dict]'}, description='Returns metadata for all task lists.', tags=['tasks', 'read'], side_effects=['db:read'])
    def get_lists(self) -> List[Dict[str, Any]]:
        """Returns metadata for all task lists."""
        with self._get_conn() as conn:
            rows = conn.execute('SELECT * FROM task_lists ORDER BY created_at DESC').fetchall()
            return [dict(r) for r in rows]

    @service_endpoint(inputs={'list_id': 'str', 'content': 'str', 'parent_id': 'Optional[str]'}, outputs={'task_id': 'str'}, description='Adds a task (or sub-task) to a list.', tags=['tasks', 'write'], side_effects=['db:write'])
    def add_task(self, list_id: str, content: str, parent_id: Optional[str]=None) -> str:
        """Adds a task (or sub-task) to a list."""
        task_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow()
        with self._get_conn() as conn:
            conn.execute('INSERT INTO tasks (id, list_id, parent_id, content, status, created_at, updated_at) \n                   VALUES (?, ?, ?, ?, ?, ?, ?)', (task_id, list_id, parent_id, content, 'Pending', now, now))
        return task_id

    @service_endpoint(inputs={'task_id': 'str', 'content': 'str', 'status': 'str', 'result': 'str'}, outputs={}, description="Updates a task's details.", tags=['tasks', 'update'], side_effects=['db:write'])
    def update_task(self, task_id: str, content: str=None, status: TaskStatus=None, result: str=None):
        """Updates a task's details."""
        updates = []
        params = []
        if content:
            updates.append('content = ?')
            params.append(content)
        if status:
            updates.append('status = ?')
            params.append(status)
        if result:
            updates.append('result = ?')
            params.append(result)
        if not updates:
            return
        updates.append('updated_at = ?')
        params.append(datetime.datetime.utcnow())
        params.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        with self._get_conn() as conn:
            conn.execute(sql, params)
        logger.info(f'Updated task {task_id}')

    @service_endpoint(inputs={'list_id': 'str'}, outputs={'tree': 'Dict[str, Any]'}, description='Fetches a list and reconstructs the full hierarchy of tasks.', tags=['tasks', 'read'], side_effects=['db:read'])
    def get_full_tree(self, list_id: str) -> Dict[str, Any]:
        """
        Fetches a list and reconstructs the full hierarchy of tasks.
        """
        with self._get_conn() as conn:
            list_row = conn.execute('SELECT * FROM task_lists WHERE id = ?', (list_id,)).fetchone()
            if not list_row:
                return {}
            task_rows = conn.execute('SELECT * FROM tasks WHERE list_id = ?', (list_id,)).fetchall()
        tasks_by_id = {}
        for r in task_rows:
            t = dict(r)
            t['sub_tasks'] = []
            tasks_by_id[t['id']] = t
        root_tasks = []
        for t_id, task in tasks_by_id.items():
            parent_id = task['parent_id']
            if parent_id and parent_id in tasks_by_id:
                tasks_by_id[parent_id]['sub_tasks'].append(task)
            else:
                root_tasks.append(task)
        return {'id': list_row['id'], 'name': list_row['name'], 'tasks': root_tasks}

    @service_endpoint(inputs={'list_id': 'str'}, outputs={}, description='Deletes a task list and all its tasks.', tags=['tasks', 'delete'], side_effects=['db:write'])
    def delete_list(self, list_id: str):
        with self._get_conn() as conn:
            conn.execute('DELETE FROM task_lists WHERE id = ?', (list_id,))
        logger.info(f'Deleted list {list_id}')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import os
    test_db = Path('test_task_vault.db')
    if test_db.exists():
        os.remove(test_db)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    vault = TasklistVaultMS({'db_path': test_db})
    print('Service ready:', vault)
    plan_id = vault.create_list('System Upgrade Plan')
    t1 = vault.add_task(plan_id, 'Backup Database')
    t2 = vault.add_task(plan_id, 'Update Server')
    t2_1 = vault.add_task(plan_id, 'Stop Services', parent_id=t2)
    t2_2 = vault.add_task(plan_id, 'Run Installer', parent_id=t2)
    vault.update_task(t1, status='Complete', result='Backup saved to /tmp/bk.tar')
    vault.update_task(t2_1, status='Running')
    tree = vault.get_full_tree(plan_id)
    print(f"\n--- {tree.get('name')} ---")

    def print_node(node, indent=0):
        status_icon = '✓' if node['status'] == 'Complete' else '○'
        print(f"{'  ' * indent}{status_icon} {node['content']} [{node['status']}]")
        for child in node['sub_tasks']:
            print_node(child, indent + 1)
    if 'tasks' in tree:
        for task in tree['tasks']:
            print_node(task)
    if test_db.exists():
        os.remove(test_db)
```

---

## FILE: `.microservice-library/services/_TelemetryServiceMS.py`

```python
import logging
import queue
import time
from typing import Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
logger = logging.getLogger('TelemetryService')

class QueueHandler(logging.Handler):
    """
    Custom logging handler that pushes log records into a thread-safe queue.
    """

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.format(record)
        self.log_queue.put(record)


@service_metadata(name='TelemetryService', version='1.0.0', description='The Nervous System: Watches the thread-safe LogQueue and updates GUI components with real-time status.', tags=['utility', 'logging', 'telemetry'], capabilities=['log-redirection', 'real-time-updates'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['ui:update'])
class TelemetryServiceMS:
    """
    The Nervous System.
    Watches the thread-safe LogQueue and updates the GUI Panels.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.root = self.config.get('root')
        self.panels = self.config.get('panels')
        self.log_queue = queue.Queue()
        self.start_time = time.time()
        self._heartbeat_count = 0
        self._setup_logging_hook()

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float', 'queue_depth': 'int'}, description='Standardized health check to verify the operational state of the telemetry pipeline.', tags=['diagnostic', 'health'], side_effects=[])
    def get_health(self) -> Dict[str, Any]:
        """Returns the operational status of the TelemetryServiceMS."""
        return {'status': 'online', 'uptime': time.time() - self.start_time, 'queue_depth': self.log_queue.qsize()}

    def _setup_logging_hook(self):
        """Redirects Python's standard logging to our Queue."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        q_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        q_handler.setFormatter(formatter)
        root_logger.addHandler(q_handler)

    @service_endpoint(inputs={}, outputs={}, description='Initiates the telemetry service and begins the asynchronous GUI log-polling loop.', tags=['lifecycle', 'event-loop'], mode='async', side_effects=['ui:update'])
    def start(self):
        """Begins the GUI update loop."""
        logger.info('Telemetry Service starting...')
        self._poll_queue()

    @service_endpoint(inputs={}, outputs={'alive': 'bool', 'heartbeat': 'int'}, description='Verifies that the GUI polling loop is actively processing the log queue.', tags=['diagnostic', 'heartbeat'], side_effects=[])
    def ping(self) -> Dict[str, Any]:
        """Allows an agent to verify the pulse of the UI loop."""
        return {'alive': True, 'heartbeat': self._heartbeat_count}

    def _poll_queue(self):
        """The heartbeat that drains the queue into the GUI."""
        if not self.root or not self.panels:
            return
        self._heartbeat_count += 1
        try:
            while True:
                record = self.log_queue.get_nowait()
                msg = f'[{record.levelname}] {record.message}'
                if hasattr(self.panels, 'log'):
                    self.panels.log(msg)
        except queue.Empty:
            pass
        finally:
            if hasattr(self.root, 'after'):
                self.root.after(100, self._poll_queue)
if __name__ == '__main__':

    class MockRoot:

        def after(self, ms, func):
            pass

    class MockPanels:

        def log(self, msg):
            print(f'[UI LOG]: {msg}')
    svc = TelemetryServiceMS({'root': MockRoot(), 'panels': MockPanels()})
    print('Service ready:', svc)
    logger.info('Internal test message')
    svc._poll_queue()
```

---

## FILE: `.microservice-library/services/_TextChunkerMS.py`

```python
import logging
from typing import Any, Dict, List, Optional, Tuple
from microservice_std_lib import service_metadata, service_endpoint
import time
logger = logging.getLogger('TextChunker')

@service_metadata(name='TextChunker', version='1.0.0', description='Splits text into chunks using various strategies (chars, lines).', tags=['chunking', 'nlp', 'rag'], capabilities=['compute'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class TextChunkerMS:
    """
    The Butcher: A unified service for splitting text into digestible chunks
    for RAG (Retrieval Augmented Generation).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'text': 'str', 'chunk_size': 'int', 'chunk_overlap': 'int'}, outputs={'chunks': 'List[str]'}, description='Standard sliding window split by character count.', tags=['chunking', 'chars'], side_effects=[])
    def chunk_by_chars(self, text: str, chunk_size: int=500, chunk_overlap: int=50) -> List[str]:
        """
        Standard Sliding Window. Best for prose/documentation.
        Splits purely by character count.
        """
        if chunk_size <= 0:
            raise ValueError('chunk_size must be positive')
        chunks = []
        start = 0
        text_length = len(text)
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            if end >= text_length:
                break
            start += chunk_size - chunk_overlap
        return chunks

    @service_endpoint(inputs={'text': 'str', 'max_lines': 'int', 'max_chars': 'int'}, outputs={'chunks': 'List[Dict]'}, description='Line-preserving chunker, best for code.', tags=['chunking', 'lines', 'code'], side_effects=[])
    def chunk_by_lines(self, text: str, max_lines: int=200, max_chars: int=4000) -> List[Dict[str, Any]]:
        """
        Line-Preserving Chunker. Best for Code.
        Respects line boundaries and returns metadata about line numbers.
        """
        lines = text.splitlines()
        chunks = []
        start = 0
        while start < len(lines):
            end = min(start + max_lines, len(lines))
            chunk_str = '\n'.join(lines[start:end])
            while len(chunk_str) > max_chars and end > start + 1:
                end -= 1
                chunk_str = '\n'.join(lines[start:end])
            chunks.append({'text': chunk_str, 'start_line': start + 1, 'end_line': end})
            start = end
        return chunks

    @service_endpoint(inputs={'text': 'str', 'target_chars': 'int', 'overlap_paragraphs': 'int'}, outputs={'chunks': 'List[str]'}, description='Prose-aware paragraph chunking with overlap between windows.', tags=['chunking', 'prose', 'paragraphs'], side_effects=[])
    def chunk_by_paragraphs(self, text: str, target_chars: int=1200, overlap_paragraphs: int=1) -> List[str]:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            return []

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current and current_len + para_len + 2 > target_chars:
                chunks.append('\n\n'.join(current))
                overlap = current[-overlap_paragraphs:] if overlap_paragraphs > 0 else []
                current = list(overlap)
                current_len = sum(len(x) for x in current) + (2 * max(0, len(current) - 1))
            current.append(para)
            current_len += para_len + (2 if len(current) > 1 else 0)

        if current:
            chunks.append('\n\n'.join(current))

        return chunks

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    chunker = TextChunkerMS()
    print('Service ready:', chunker)
    print('--- Prose Chunking ---')
    lorem = 'A' * 100
    result = chunker.chunk_by_chars(lorem, chunk_size=40, chunk_overlap=10)
    for i, c in enumerate(result):
        print(f'Chunk {i}: len={len(c)}')
    print('\n--- Code Chunking ---')
    code = '\n'.join([f"print('Line {i}')" for i in range(1, 10)])
    result_code = chunker.chunk_by_lines(code, max_lines=3, max_chars=100)
    for i, c in enumerate(result_code):
        print(f"Chunk {i}: Lines {c['start_line']}-{c['end_line']}")
```

---

## FILE: `.microservice-library/services/_ThoughtStreamMS.py`

```python
import tkinter as tk
from tkinter import ttk
import datetime
from typing import Any, Dict, Optional, List
from microservice_std_lib import service_metadata, service_endpoint
import time

@service_metadata(name='ThoughtStream', version='1.0.0', description='A UI widget for displaying a stream of AI thoughts/logs.', tags=['ui', 'stream', 'logs', 'widget'], capabilities=['ui:gui'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['ui:update'])
class ThoughtStreamMS(ttk.Frame):
    """
    The Neural Inspector: A UI widget for displaying a stream of AI thoughts/logs
    visualized as 'bubbles' with sparklines.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        parent = self.config.get('parent')
        super().__init__(parent)
        self.header = ttk.Label(self, text='NEURAL INSPECTOR', font=('Consolas', 10, 'bold'))
        self.header.pack(fill='x', padx=5, pady=5)
        self.canvas = tk.Canvas(self, bg='#13131f', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#13131f')
        self.scrollable_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw', width=340)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')

    @service_endpoint(inputs={'filename': 'str', 'chunk_id': 'int', 'content': 'str', 'vector_preview': 'List[float]', 'color': 'str'}, outputs={}, description='Adds a new thought bubble to the visual stream.', tags=['ui', 'update'], side_effects=['ui:update'])
    def add_thought_bubble(self, filename: str, chunk_id: int, content: str, vector_preview: List[float], color: str):
        """
        Mimics the 'InspectorFrame' from your React code.
        """
        bubble = tk.Frame(self.scrollable_frame, bg='#1a1a25', highlightbackground='#444', highlightthickness=1)
        bubble.pack(fill='x', padx=5, pady=5)
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        header_lbl = tk.Label(bubble, text=f'{filename} #{chunk_id} [{ts}]', fg='#007ACC', bg='#1a1a25', font=('Consolas', 8))
        header_lbl.pack(anchor='w', padx=5, pady=2)
        snippet = content[:400] + '...' if len(content) > 400 else content
        content_lbl = tk.Label(bubble, text=snippet, fg='#ccc', bg='#10101a', font=('Consolas', 8), justify='left', wraplength=300)
        content_lbl.pack(fill='x', padx=5, pady=2)
        self._draw_sparkline(bubble, vector_preview, color)

    def _draw_sparkline(self, parent, vector: List[float], color: str):
        """
        Recreates the 'vector_preview' visual from React using a micro-canvas.
        """
        h = 30
        w = 300
        cv = tk.Canvas(parent, height=h, width=w, bg='#1a1a25', highlightthickness=0)
        cv.pack(padx=5, pady=2)
        if not vector:
            return
        bar_w = w / len(vector) if len(vector) > 0 else 0
        for i, val in enumerate(vector):
            mag = abs(val)
            bar_h = mag * h
            x0 = i * bar_w
            y0 = h - bar_h
            x1 = x0 + bar_w
            y1 = h
            cv.create_rectangle(x0, y0, x1, y1, fill=color, outline='')
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    import random
    root = tk.Tk()
    root.title('Thought Stream Test')
    root.geometry('400x600')
    stream = ThoughtStreamMS({'parent': root})
    print('Service ready:', stream)
    stream.pack(fill='both', expand=True)
    fake_vector = [random.uniform(-1, 1) for _ in range(20)]
    stream.add_thought_bubble('ExplorerView.tsx', 1, "import React from 'react'...", fake_vector, '#FF00FF')
    fake_vector_2 = [random.uniform(-1, 1) for _ in range(20)]
    stream.add_thought_bubble('Backend.py', 42, 'def process_data(self): pass', fake_vector_2, '#00FF00')
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_TkinterAppShellMS.py`

```python
"""
SERVICE_NAME: _TkinterAppShellMS
ENTRY_POINT: _TkinterAppShellMS.py
INTERNAL_DEPENDENCIES: _TkinterThemeManagerMS, microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
try:
    from _TkinterThemeManagerMS import TkinterThemeManagerMS
except ImportError:
    TkinterThemeManagerMS = None
logger = logging.getLogger('AppShell')

@service_metadata(name='TkinterAppShell', version='2.0.0', description='The Application Container. Manages the root window, main loop, and global layout.', tags=['ui', 'core', 'lifecycle'], capabilities=['ui:root', 'ui:gui'], internal_dependencies=['_TkinterThemeManagerMS', 'microservice_std_lib'], external_dependencies=[], side_effects=['ui:block', 'ui:close'])
class TkinterAppShellMS:
    """
    The Mother Ship.
    Owns the Tkinter Root. All other UI microservices dock into this.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.root = tk.Tk()
        self.root.withdraw()
        self.theme_svc = self.config.get('theme_manager')
        if not self.theme_svc and TkinterThemeManagerMS:
            self.theme_svc = TkinterThemeManagerMS()
        self.colors = self.theme_svc.get_theme() if self.theme_svc else {}
        self._configure_root()

    def _configure_root(self):
        self.root.title(self.config.get('title', 'Microservice OS'))
        self.root.geometry(self.config.get('geometry', '1200x800'))
        bg = self.colors.get('background', '#1e1e1e')
        self.root.configure(bg=bg)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=bg)
        style.configure('TLabel', background=bg, foreground=self.colors.get('foreground', '#ccc'))
        style.configure('TButton', background=self.colors.get('panel_bg', '#333'), foreground='white')
        self.main_container = tk.Frame(self.root, bg=bg)
        self.main_container.pack(fill='both', expand=True, padx=5, pady=5)

    @service_endpoint(inputs={}, outputs={}, description='Starts the GUI Main Loop.', tags=['lifecycle', 'start'], mode='sync', side_effects=['ui:block'])
    def launch(self):
        """Ignition sequence start."""
        self.root.deiconify()
        logger.info('AppShell Launched.')
        self.root.mainloop()

    @service_endpoint(inputs={}, outputs={'container': 'tk.Frame'}, description='Returns the main content area for other services to dock into.', tags=['ui', 'layout'])
    def get_main_container(self):
        """Other services call this to know where to .pack() themselves."""
        return self.main_container

    @service_endpoint(inputs={}, outputs={}, description='Gracefully shuts down the application.', tags=['lifecycle', 'stop'], side_effects=['ui:close'])
    def shutdown(self):
        self.root.quit()
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    shell = TkinterAppShellMS({'title': 'Test Shell'})
    shell.launch()
```

---

## FILE: `.microservice-library/services/_TkinterSmartExplorerMS.py`

```python
"""
SERVICE_NAME: _TkinterSmartExplorerMS
ENTRY_POINT: _TkinterSmartExplorerMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, List
from microservice_std_lib import service_metadata, service_endpoint
import time

@service_metadata(name='TkinterSmartExplorer', version='1.0.0', description='A hierarchical tree viewer capable of displaying file systems or JSON data structures.', tags=['ui', 'widget', 'explorer'], capabilities=['ui:gui'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['ui:update'])
class TkinterSmartExplorerMS(tk.Frame):
    """
    The Navigator.
    A TreeView widget that expects standard 'Node' dictionaries (name, type, children).
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        parent = self.config.get('parent')
        theme = self.config.get('theme', {})
        super().__init__(parent, bg=theme.get('panel_bg', '#252526'))
        self.tree = ttk.Treeview(self, show='tree headings', selectmode='browse')
        self.tree.heading('#0', text='Explorer', anchor='w')
        vsb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        default_icons = {'folder': '📁', 'file': '📄', 'web': '🌐', 'unknown': '❓'}
        self.theme_manager = self.config.get('theme_manager')
        if self.theme_manager and hasattr(self.theme_manager, 'get_node_icons'):
            try:
                icon_map = self.theme_manager.get_node_icons()
                default_icons.update(icon_map)
            except Exception:
                pass
        self.icons = default_icons

    @service_endpoint(inputs={'data': 'Dict'}, outputs={}, description="Populates the tree view with a nested dictionary structure (Standard 'Node' format).", tags=['ui', 'update'], side_effects=['ui:update'])
    def load_data(self, data: Dict[str, Any]):
        """
        Ingests a dictionary tree (like from _ScoutMS or _TreeMapperMS).
        """
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._build_node('', data)

    @service_endpoint(inputs={}, outputs={'schema': 'Dict'}, description='Returns a headless UI schema for this explorer widget.', tags=['ui', 'schema'])
    def get_ui_schema(self) -> Dict[str, Any]:
        return {'widget': 'TreeView', 'columns': ['#0'], 'selectmode': 'browse', 'icons': self.icons}

    def _build_node(self, parent_id, node_data):
        ntype = node_data.get('type', 'unknown')
        icon = self.icons.get(ntype, self.icons['unknown'])
        text = f"{icon} {node_data.get('name', '???')}"
        item_id = self.tree.insert(parent_id, 'end', text=text, open=True)
        for child in node_data.get('children', []):
            self._build_node(item_id, child)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    root = tk.Tk()
    explorer = TkinterSmartExplorerMS({'parent': root})
    explorer.pack(fill='both', expand=True)
    dummy_data = {'name': 'Project Root', 'type': 'folder', 'children': [{'name': 'src', 'type': 'folder', 'children': []}, {'name': 'README.md', 'type': 'file'}]}
    explorer.load_data(dummy_data)
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_TkinterThemeManagerMS.py`

```python
"""
SERVICE_NAME: _TkinterThemeManagerMS
ENTRY_POINT: _TkinterThemeManagerMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""

import time
from typing import Any, Dict, Optional

from microservice_std_lib import service_metadata, service_endpoint

DEFAULT_THEME = {
    'background': '#1e1e1e',
    'panel_bg': '#252526',
    'surface_bg': '#2d2d2d',
    'border': '#3c3c3c',
    'accent': '#007acc',
    'accent2': '#0e639c',
    'accent3': '#1177bb',
    'foreground': '#d4d4d4',
    'foreground_dim': '#858585',
    'foreground_muted': '#6a6a6a',
    'success': '#6a9955',
    'warning': '#dcdcaa',
    'error': '#f44747',
    'info': '#9cdcfe',
    'font_ui': ('Segoe UI', 10),
    'font_sm': ('Segoe UI', 9),
    'font_xs': ('Segoe UI', 8),
    'font_h': ('Segoe UI Semibold', 11),
    'font_mono': ('Consolas', 10),
    'font_mono_sm': ('Consolas', 9),
    'font_mono_xs': ('Consolas', 8),
    'pad': 8,
    'bg': '#1e1e1e',
    'bg2': '#252526',
    'bg3': '#2d2d2d',
    'fg': '#d4d4d4',
    'fg_dim': '#858585',
    'fg_muted': '#6a6a6a',
    }

DEFAULT_NODE_ICONS = {
    'root': '🗄',
    'directory': '📁',
    'file': '📄',
    'virtual_file': '📎',
    'compound_summary': '📋',
    'module': '📦',
    'class_def': '🔷',
    'function_def': '⚡',
    'method_def': '⚡',
    'async_function': '⚡',
    'decorator': '🏷',
    'import': '📎',
    'document': '📄',
    'document_summary': '📋',
    'section': '§',
    'subsection': '§',
    'heading': '§',
    'paragraph': '¶',
    'list_item': '•',
    'object': '{ }',
    'array': '[ ]',
    'key_value': '→',
    'table': '▦',
    'html_element': '◇',
    'html_section': '◈',
    'css_rule': '🎨',
    'xml_element': '◇',
    'chunk': '▪',
}


@service_metadata(
    name='TkinterThemeManager',
    version='1.2.0',
    description='Centralized modern Tkinter theme tokens and icon maps used by UI microservices.',
    tags=['ui', 'config', 'theme'],
    capabilities=['ui:style'],
    side_effects=['ui:refresh'],
    internal_dependencies=['microservice_std_lib'],
    external_dependencies=[]
)
class TkinterThemeManagerMS:
    """Holds theme tokens and icon maps for modernized Tkinter components."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.start_time = time.time()
        self.config = config or {}
        self.theme = dict(DEFAULT_THEME)
        self.node_icons = dict(DEFAULT_NODE_ICONS)

        overrides = self.config.get('overrides')
        if isinstance(overrides, dict):
            self.theme.update(overrides)

        icon_overrides = self.config.get('icon_overrides')
        if isinstance(icon_overrides, dict):
            self.node_icons.update(icon_overrides)

    @service_endpoint(inputs={}, outputs={'theme': 'dict'}, description='Return active theme token dictionary.', tags=['ui', 'read'])
    def get_theme(self) -> Dict[str, Any]:
        return dict(self.theme)

    @service_endpoint(inputs={}, outputs={'icons': 'dict'}, description='Return active node icon map.', tags=['ui', 'read'])
    def get_node_icons(self) -> Dict[str, str]:
        return dict(self.node_icons)

    @service_endpoint(inputs={}, outputs={'aliases': 'dict'}, description='Return legacy theme alias map for compatibility with older Tkinter components.', tags=['ui', 'read', 'compat'])
    def get_legacy_aliases(self) -> Dict[str, Any]:
        return {
            'BG': self.theme.get('bg', self.theme.get('background')),
            'BG2': self.theme.get('bg2', self.theme.get('panel_bg')),
            'BG3': self.theme.get('bg3', self.theme.get('surface_bg')),
            'FG': self.theme.get('fg', self.theme.get('foreground')),
            'FG_DIM': self.theme.get('fg_dim', self.theme.get('foreground_dim')),
            'FG_MUTED': self.theme.get('fg_muted', self.theme.get('foreground_muted')),
            'ACCENT': self.theme.get('accent'),
            'ACCENT2': self.theme.get('accent2'),
            'ACCENT3': self.theme.get('accent3'),
            'BORDER': self.theme.get('border'),
            'PAD': self.theme.get('pad', 8),
        }

    @service_endpoint(inputs={'key': 'str', 'value': 'Any'}, outputs={'ok': 'bool'}, description='Update a single theme token at runtime.', tags=['ui', 'write'], side_effects=['ui:refresh'])
    def update_key(self, key: str, value: Any) -> bool:
        self.theme[key] = value
        return True

    @service_endpoint(inputs={'node_type': 'str', 'icon': 'str'}, outputs={'ok': 'bool'}, description='Update or add icon mapping for a node type.', tags=['ui', 'write'], side_effects=['ui:refresh'])
    def update_icon(self, node_type: str, icon: str) -> bool:
        self.node_icons[node_type] = icon
        return True

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float', 'token_count': 'int', 'icon_count': 'int'}, description='Standardized health check for theme manager state.', tags=['diagnostic', 'health'])
    def get_health(self):
        return {
            'status': 'online',
            'uptime': time.time() - self.start_time,
            'token_count': len(self.theme),
            'icon_count': len(self.node_icons),
        }


if __name__ == '__main__':
    svc = TkinterThemeManagerMS()
    print('Theme Ready:', svc.get_theme()['accent'])
```

---

## FILE: `.microservice-library/services/_TkinterUniButtonMS.py`

```python
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable
from microservice_std_lib import service_metadata, service_endpoint
import time

@dataclass
class ButtonConfig:
    text: str
    command: Callable[[], None]
    bg_color: str
    active_bg_color: str
    fg_color: str = '#FFFFFF'


@dataclass
class LinkConfig:
    """Configuration for the 'Linked' state (The Trap)"""
    trap_bg: str = '#7C3AED'
    btn_bg: str = '#8B5CF6'
    text_color: str = '#FFFFFF'

@service_metadata(name='LockingDualBtn', version='1.0.0', description='A unified button group (Left/Right/Link) where linking merges the actions.', tags=['ui', 'widget', 'button'], capabilities=['ui:gui'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class TkinterUniButtonMS(tk.Frame):
    """
    A generic button group that can merge ANY two actions.
    Pass the visual/functional definitions in via the config objects.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        parent = self.config.get('parent')
        super().__init__(parent)
        self.left_cfg: Optional[ButtonConfig] = self.config.get('left_btn')
        self.right_cfg: Optional[ButtonConfig] = self.config.get('right_btn')
        self.link_cfg: LinkConfig = self.config.get('link_config') or LinkConfig()
        self.is_linked = False
        try:
            self.default_bg = parent.cget('bg')
        except AttributeError:
            self.default_bg = '#f0f0f0'
        if not self.left_cfg or not self.right_cfg:
            print('Warning: TkinterUniButtonMS initialized without button configs.')
            return
        self._setup_ui()
        self._update_state()

    def _setup_ui(self):
        self.configure(padx=4, pady=4)
        common_style = {'relief': 'flat', 'font': ('Segoe UI', 10, 'bold'), 'bd': 0, 'cursor': 'hand2'}
        self.btn_left = tk.Button(self, command=lambda: self._execute('left'), **common_style)
        self.btn_left.pack(side='left', fill='y', padx=(0, 2))
        self.btn_link = tk.Button(self, text='&', width=3, command=self._toggle_link, **common_style)
        self.btn_link.pack(side='left', fill='y', padx=(0, 2))
        self.btn_right = tk.Button(self, command=lambda: self._execute('right'), **common_style)
        self.btn_right.pack(side='left', fill='y')

    def _toggle_link(self):
        self.is_linked = not self.is_linked
        self._update_state()

    def _update_state(self):
        if self.is_linked:
            self.configure(bg=self.link_cfg.trap_bg)
            for btn in (self.btn_left, self.btn_right, self.btn_link):
                btn.configure(bg=self.link_cfg.btn_bg, fg=self.link_cfg.text_color, activebackground=self.link_cfg.trap_bg)
            self.btn_left.configure(text=self.left_cfg.text)
            self.btn_right.configure(text=self.right_cfg.text)
        else:
            try:
                self.configure(bg=self.default_bg)
            except:
                self.configure(bg='#f0f0f0')
            self.btn_left.configure(text=self.left_cfg.text, bg=self.left_cfg.bg_color, fg=self.left_cfg.fg_color, activebackground=self.left_cfg.active_bg_color)
            self.btn_right.configure(text=self.right_cfg.text, bg=self.right_cfg.bg_color, fg=self.right_cfg.fg_color, activebackground=self.right_cfg.active_bg_color)
            self.btn_link.configure(bg='#E5E7EB', fg='#374151', activebackground='#D1D5DB')

    def _execute(self, source):
        if self.is_linked:
            self.left_cfg.command()
            self.right_cfg.command()
        elif source == 'left':
            self.left_cfg.command()
        elif source == 'right':
            self.right_cfg.command()
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    root = tk.Tk()
    root.title('UniButton Test')
    root.geometry('300x100')

    def on_validate():
        print('Validating Data...')

    def on_apply():
        print('Applying Changes...')
    btn1 = ButtonConfig('Validate', on_validate, '#3b82f6', '#2563eb')
    btn2 = ButtonConfig('Apply', on_apply, '#10b981', '#059669')
    svc = TkinterUniButtonMS({'parent': root, 'left_btn': btn1, 'right_btn': btn2})
    print('Service ready:', svc)
    svc.pack(pady=20)
    root.mainloop()
```

---

## FILE: `.microservice-library/services/_TreeMapperMS.py`

```python
import os
import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Optional
from microservice_std_lib import service_metadata, service_endpoint
import time
DEFAULT_EXCLUDES = {'.git', '__pycache__', '.idea', '.vscode', 'node_modules', '.venv', 'env', 'venv', 'dist', 'build', '.DS_Store'}
logger = logging.getLogger('TreeMapper')

@service_metadata(name='TreeMapper', version='1.0.0', description='Generates ASCII-art style directory maps of the file system.', tags=['filesystem', 'map', 'visualization'], capabilities=['filesystem:read'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=['filesystem:read'])
class TreeMapperMS:
    """
    The Cartographer: Generates ASCII-art style directory maps.
    Useful for creating context snapshots for LLMs.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}

    @service_endpoint(inputs={'root_path': 'str', 'additional_exclusions': 'Set[str]', 'use_default_exclusions': 'bool'}, outputs={'tree_map': 'str'}, description='Generates an ASCII tree map of the directory.', tags=['filesystem', 'visualization'], side_effects=['filesystem:read'])
    def generate_tree(self, root_path: str, additional_exclusions: Optional[Set[str]]=None, use_default_exclusions: bool=True) -> str:
        start_path = Path(root_path).resolve()
        if not start_path.exists():
            return f"Error: Path '{root_path}' does not exist."
        exclusions = set()
        if use_default_exclusions:
            exclusions.update(DEFAULT_EXCLUDES)
        if additional_exclusions:
            exclusions.update(additional_exclusions)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines = [f'Project Map: {start_path.name}', f'Generated: {timestamp}', '-' * 40, f'📁 {start_path.name}/']
        logger.info(f'Mapping directory: {start_path}')
        self._walk(start_path, '', lines, exclusions)
        return '\n'.join(lines)

    def _walk(self, directory: Path, prefix: str, lines: List[str], exclusions: Set[str]):
        try:
            children = sorted([p for p in directory.iterdir() if p.name not in exclusions], key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            lines.append(f'{prefix}└── 🚫 [Permission Denied]')
            return
        count = len(children)
        for index, path in enumerate(children):
            is_last = index == count - 1
            connector = '└── ' if is_last else '├── '
            if path.is_dir():
                lines.append(f'{prefix}{connector}📁 {path.name}/')
                extension = '    ' if is_last else '│   '
                self._walk(path, prefix + extension, lines, exclusions)
            else:
                lines.append(f'{prefix}{connector}📄 {path.name}')

    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    svc = TreeMapperMS()
    print('Service ready:', svc)
    print('\n--- Map of Current Dir ---')
    tree = svc.generate_tree('.', additional_exclusions={'__pycache__'})
    print(tree)
```

---

## FILE: `.microservice-library/services/_WebScraperMS.py`

```python
import importlib.util
import sys
import httpx
import logging
import asyncio
import re
from typing import Optional, Dict, Any
import time
REQUIRED = ['httpx', 'readability-lxml']
MISSING = []
for lib in REQUIRED:
    clean_lib = lib.split('>=')[0].replace('-', '_')
    if clean_lib == 'readability_lxml':
        clean_lib = 'readability'
    if importlib.util.find_spec(clean_lib) is None:
        MISSING.append(lib)
if MISSING:
    print('\n' + '!' * 60)
    print(f'MISSING DEPENDENCIES for _WebScraperMS:')
    print(f"Run:  pip install {' '.join(MISSING)}")
    print('!' * 60 + '\n')
try:
    from readability import Document
except ImportError:
    Document = None
from microservice_std_lib import service_metadata, service_endpoint
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
TIMEOUT_SECONDS = 15.0
logger = logging.getLogger('WebScraper')

@service_metadata(name='WebScraper', version='1.0.0', description='Fetches URLs and extracts main content using Readability (stripping ads/nav).', tags=['scraper', 'web', 'readability'], capabilities=['network:outbound', 'compute'], internal_dependencies=['microservice_std_lib'], external_dependencies=['httpx', 'readability'], side_effects=['network:outbound'])
class WebScraperMS:
    """
    The Reader: Fetches URLs and extracts the main content using Readability.
    Strips ads, navbars, and boilerplate to return clean text for LLMs.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        self.config = config or {}
        self.headers = {'User-Agent': USER_AGENT}

    @service_endpoint(inputs={'url': 'str'}, outputs={'data': 'Dict[str, Any]'}, description='Fetches and cleans a URL.', tags=['scraper', 'read'], side_effects=['network:outbound'])
    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for fetching and cleaning a URL.
        Returns: {
            "url": str,
            "title": str,
            "content": str (The main body text),
            "html": str (The raw HTML of the main content area)
        }
        """
        return asyncio.run(self._scrape_async(url))

    async def _scrape_async(self, url: str) -> Dict[str, Any]:
        if Document is None:
            raise ImportError('readability-lxml is missing.')
        logger.info(f'Fetching: {url}')
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=TIMEOUT_SECONDS) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f'HTTP Error {e.response.status_code}: {e}')
                raise
            except httpx.RequestError as e:
                logger.error(f'Request failed: {e}')
                raise
        try:
            doc = Document(response.text)
            title = doc.title()
            clean_html = doc.summary()
            clean_text = self._strip_tags(clean_html)
            logger.info(f"Successfully scraped '{title}' ({len(clean_text)} chars)")
            return {'url': url, 'title': title, 'content': clean_text, 'html': clean_html}
        except Exception as e:
            logger.error(f'Parsing failed: {e}')
            raise

    def _strip_tags(self, html: str) -> str:
        """
        Removes HTML tags to leave only the readable text.
        """
        html = re.sub('<(script|style).*?>.*?</\\1>', '', html, flags=re.DOTALL)
        text = re.sub('<[^>]+>', ' ', html)
        text = re.sub('\\s+', ' ', text).strip()
        return text
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    scraper = WebScraperMS()
    print('Service ready:', scraper)
    target_url = 'https://peps.python.org/pep-0008/'
    print(f'--- Scraping {target_url} ---')
    try:
        data = scraper.scrape(target_url)
        print(f"\nTitle: {data['title']}")
        print(f"Content Preview:\n{data['content'][:500]}...")
        print(f"\nTotal Length: {len(data['content'])} characters")
    except Exception as e:
        print(f'Scrape failed: {e}')
```

---

## FILE: `.microservice-library/services/_WorkbenchLayoutMS.py`

```python
"""
SERVICE_NAME: _WorkbenchLayoutMS
ENTRY_POINT: _WorkbenchLayoutMS.py
INTERNAL_DEPENDENCIES: microservice_std_lib
EXTERNAL_DEPENDENCIES: None
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, Callable
from microservice_std_lib import service_metadata, service_endpoint
import time

@service_metadata(name='WorkbenchLayout', version='1.0.0', description='A declarative layout engine that builds resizable, nested Workbenches (Rows/Cols) from a config dictionary.', tags=['ui', 'layout', 'framework'], capabilities=['ui:construct'], internal_dependencies=['microservice_std_lib'], external_dependencies=[], side_effects=[])
class WorkbenchLayoutMS(tk.Frame):
    """
    The Architect.
    Recursively builds a UI based on a 'Layout Manifest'.
    Uses ttk.PanedWindow to allow user resizing of areas.
    """

    def __init__(self, config: Optional[Dict[str, Any]]=None):
        parent = config.get('parent')
        super().__init__(parent)
        self.config = config or {}
        self.panel_registry: Dict[str, tk.Widget] = {}

    @service_endpoint(inputs={'manifest': 'Dict'}, outputs={}, description='Builds the UI structure based on the provided dictionary layout.', tags=['ui', 'build'])
    def build_from_manifest(self, manifest: Dict[str, Any]):
        """
        Manifest Schema:
        {
            "type": "row" | "col",
            "weight": int,  # 1 = expands, 0 = fixed
            "children": [
                { "type": "panel", "id": "my_panel_id", "weight": 1 },
                { "type": "row", "weight": 2, "children": [...] }
            ]
        }
        """
        for widget in self.winfo_children():
            widget.destroy()
        self._build_recursive(self, manifest)

    def get_panel(self, panel_id: str) -> Optional[tk.Widget]:
        """Retrieve a specific container by ID to pack widgets into."""
        return self.panel_registry.get(panel_id)

    def _build_recursive(self, parent_widget, node: Dict[str, Any]):
        node_type = node.get('type', 'panel')
        weight = node.get('weight', 1)
        if node_type in ['row', 'col']:
            orient = tk.HORIZONTAL if node_type == 'col' else tk.VERTICAL
            container = ttk.PanedWindow(parent_widget, orient=orient)
            if isinstance(parent_widget, ttk.PanedWindow):
                parent_widget.add(container, weight=weight)
            else:
                container.pack(fill='both', expand=True)
            for child in node.get('children', []):
                self._build_recursive(container, child)
        elif node_type == 'panel':
            p_id = node.get('id', 'unknown')
            frame = ttk.Frame(parent_widget, padding=2)
            self.panel_registry[p_id] = frame
            if isinstance(parent_widget, ttk.PanedWindow):
                parent_widget.add(frame, weight=weight)
            else:
                frame.pack(fill='both', expand=True)
    @service_endpoint(inputs={}, outputs={'status': 'str', 'uptime': 'float'}, description='Standardized health check for service status.', tags=['diagnostic', 'health'])
    def get_health(self):
        """Returns the operational status of the service."""
        start = getattr(self, 'start_time', None)
        if start is None:
            start = time.time()
            self.start_time = start
        return {'status': 'online', 'uptime': time.time() - start}
```

---

## FILE: `.microservice-library/services/base_service.py`

```python
"""
Compatibility base service used by legacy microservices.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


class BaseService:
    """
    Minimal compatibility base class for legacy microservices.
    """

    def __init__(self, service_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        self.service_name = service_name or self.__class__.__name__
        self.config = config or {}
        self.start_time = time.time()

    def configure(self, **kwargs: Any) -> Dict[str, Any]:
        self.config.update(kwargs)
        return dict(self.config)

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": "online",
            "service": self.service_name,
            "uptime": time.time() - self.start_time,
        }
```

---

## FILE: `.microservice-library/services/microservice_std_lib.py`

```python
"""
LIBRARY: Microservice Standard Lib
VERSION: 2.1.0
ROLE: Provides decorators for tagging Python classes as AI-discoverable services.

Change (2.1.0):
- Split dependencies into:
    internal_dependencies: local modules / microservices to vendor with the app
    external_dependencies: pip-installable packages (requirements.txt)
- Keep legacy "dependencies" as an alias for external_dependencies for backward compatibility.
- Accept unknown keyword args in @service_metadata(...) to prevent older/newer services from crashing
  (e.g. when a runner passes additional fields).
"""

import functools
import inspect
from typing import Dict, List, Any, Optional, Type

try:
    from .base_service import BaseService
except ImportError:
    from base_service import BaseService

# ==============================================================================
# DECORATORS (The "Writer" Tools)
# ==============================================================================

def service_metadata(
    name: str,
    version: str,
    description: str,
    tags: List[str],
    capabilities: Optional[List[str]] = None,

    # Legacy field (kept for backward compatibility):
    # Historically this mixed stdlib + pip deps. Going forward, treat this as *external* deps.
    dependencies: Optional[List[str]] = None,

    # New fields (preferred):
    internal_dependencies: Optional[List[str]] = None,
    external_dependencies: Optional[List[str]] = None,

    # Side effects / operational hints
    side_effects: Optional[List[str]] = None,

    # Forward-compat: ignore unknown keyword args instead of crashing older/newer services
    **_ignored_kwargs: Any,
):
    """
    Class Decorator.
    Labels a Microservice class with high-level metadata for the Catalog.

    Dependency semantics:
      - internal_dependencies: local modules and/or other microservice modules that must be shipped with an app
      - external_dependencies: third-party pip packages (requirements.txt)
      - dependencies (legacy): treated as external_dependencies when external_dependencies is not provided
    """
    # Prefer explicit new key, otherwise fall back to legacy dependencies
    ext = external_dependencies if external_dependencies is not None else (dependencies or [])
    intl = internal_dependencies or []

    def decorator(cls):
        cls._is_microservice = True
        info = {
            "name": name,
            "version": version,
            "description": description,
            "tags": tags,
            "capabilities": capabilities or [],

            # New keys
            "internal_dependencies": intl,
            "external_dependencies": ext,

            # Legacy alias (keep existing tooling working)
            "dependencies": ext,

            "side_effects": side_effects or []
        }
        cls._service_info = info
        # Backward compatibility for older grouped services and injected register() hooks.
        cls._meta = dict(info)
        return cls
    return decorator


def service_endpoint(
    inputs: Dict[str, str],
    outputs: Dict[str, str],
    description: str,
    tags: Optional[List[str]] = None,
    side_effects: Optional[List[str]] = None,
    mode: str = "sync",
):
    """
    Method Decorator.
    Defines the 'Socket' that the AI Architect can plug into.

    :param inputs: Dict of {arg_name: type_string} (e.g. {"query": "str"})
    :param outputs: Dict of {return_name: type_string}
    :param description: What the endpoint does
    :param tags: List of categories (e.g. ["read", "write"])
    :param side_effects: List of side effects (e.g. ["filesystem:write", "db:write"])
    :param mode: "sync" or "async" (informational unless your runtime uses it)
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Attach metadata to the function object itself
        wrapper._is_endpoint = True
        wrapper._endpoint_info = {
            "name": func.__name__,
            "inputs": inputs,
            "outputs": outputs,
            "description": description,
            "tags": tags or [],
            "side_effects": side_effects or [],
            "mode": mode
        }
        return wrapper
    return decorator


# ==============================================================================
# INTROSPECTION (The "Reader" Tools)
# ==============================================================================

def extract_service_schema(service_cls: Type) -> Dict[str, Any]:
    """
    Scans a decorated Service Class and returns a JSON-serializable schema
    of its metadata and all its exposed endpoints.

    This is what the AI Agent uses to 'read' the manual.
    """
    if not getattr(service_cls, "_is_microservice", False):
        raise ValueError(f"Class {service_cls.__name__} is not decorated with @service_metadata")

    schema = {
        "meta": getattr(service_cls, "_service_info", {}),
        "endpoints": []
    }

    # Inspect all methods of the class
    for _, method in inspect.getmembers(service_cls, predicate=inspect.isfunction):
        endpoint_info = getattr(method, "_endpoint_info", None)
        if endpoint_info:
            schema["endpoints"].append(endpoint_info)

    return schema


__all__ = [
    "BaseService",
    "extract_service_schema",
    "service_endpoint",
    "service_metadata",
]
```

---

## FILE: `.microservice-library/.sidecar.json`

```json
{
  "name": ".microservice-library",
  "version": "1.0.0",
  "role": "microservice toolbox",
  "description": "56 Python microservices covering file scanning, RAG ingestion, vector search, SQLite storage, Git ops, and Tkinter UI — discoverable by agents via CLI or MCP.",
  "author": "Jacob Lambert",
  "cli": "python .microservice-library/cli.py",
  "mcp": "python .microservice-library/mcp_server.py",
  "index": ".microservice-library/codex.md",
  "requires": {
    "python": ">=3.11",
    "ollama": "running at localhost:11434"
  },
  "tags": ["microservices", "rag", "agent-tooling", "local-inference"]
}
```

---

## FILE: `.microservice-library/cli.py`

```python
"""
ms-toolbox CLI  —  list / describe / call microservices.

Usage:
  python cli.py list
  python cli.py describe ScoutMS
  python cli.py call ScoutMS scan_path root_path=/some/path depth=3
"""
import sys
import json
import argparse
import importlib.util
import inspect
from pathlib import Path

SERVICES_DIR = Path(__file__).parent / "services"
sys.path.insert(0, str(SERVICES_DIR))

from microservice_std_lib import extract_service_schema  # noqa: E402


# ── discovery ─────────────────────────────────────────────────────────────────

def discover() -> dict:
    registry = {}
    for f in sorted(SERVICES_DIR.glob("_*MS.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if getattr(cls, "_is_microservice", False):
                try:
                    schema = extract_service_schema(cls)
                    registry[schema["meta"]["name"]] = {"cls": cls, "schema": schema}
                except Exception:
                    pass
    return registry


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_list(registry: dict, _args) -> None:
    print(f"  {'SERVICE':<35} {'DESCRIPTION':<60}  TAGS")
    print("  " + "-" * 105)
    for svc_name, info in sorted(registry.items()):
        meta = info["schema"]["meta"]
        tags = ", ".join(meta.get("tags", []))
        desc = meta.get("description", "")[:58]
        print(f"  {svc_name:<35} {desc:<60}  {tags}")


def cmd_describe(registry: dict, args) -> None:
    info = registry.get(args.service)
    if not info:
        print(f"Unknown service: {args.service}")
        sys.exit(1)
    print(json.dumps(info["schema"], indent=2))


def cmd_call(registry: dict, args) -> None:
    info = registry.get(args.service)
    if not info:
        print(f"Unknown service: {args.service}")
        sys.exit(1)
    try:
        instance = info["cls"]()
    except TypeError as e:
        print(f"Cannot instantiate {args.service} with no args: {e}")
        sys.exit(1)
    method = getattr(instance, args.method, None)
    if method is None:
        print(f"No method '{args.method}' on {args.service}")
        sys.exit(1)
    kwargs: dict = {}
    for token in args.kwargs or []:
        k, _, v = token.partition("=")
        kwargs[k.lstrip("-")] = v
    try:
        result = method(**kwargs)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="ms-toolbox",
                                     description="Microservice toolbox CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all available services")

    p_desc = sub.add_parser("describe", help="Show full schema for a service")
    p_desc.add_argument("service", help="Service name (e.g. ScoutMS)")

    p_call = sub.add_parser("call", help="Call a service endpoint")
    p_call.add_argument("service", help="Service name")
    p_call.add_argument("method",  help="Method name")
    p_call.add_argument("kwargs",  nargs="*",
                        help="keyword=value pairs (e.g. root_path=/tmp depth=3)")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    registry = discover()
    {"list": cmd_list, "describe": cmd_describe, "call": cmd_call}[args.cmd](registry, args)


if __name__ == "__main__":
    main()
```

---

## FILE: `.microservice-library/codex.md`

```markdown
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
```

---

## FILE: `.microservice-library/LICENSE.md`

```markdown
MIT License

Copyright (c) 2024 Jacob Lambert

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## FILE: `.microservice-library/mcp_server.py`

```python
"""
ms-toolbox MCP server — exposes every @service_endpoint as an MCP tool.

Each tool name is:  ServiceName__method_name
  e.g.  ScoutMS__scan_path

Run as an MCP stdio server:
  python mcp_server.py

Wire into your MCP client config:
  {
    "mcpServers": {
      "ms-toolbox": {
        "command": "python",
        "args": ["/path/to/ms_toolbox/mcp_server.py"]
      }
    }
  }

Requires:  pip install mcp
"""
import sys
import json
import importlib.util
import inspect
import asyncio
from pathlib import Path

SERVICES_DIR = Path(__file__).parent / "services"
sys.path.insert(0, str(SERVICES_DIR))

from microservice_std_lib import extract_service_schema  # noqa: E402

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types as mcp_types
except ImportError:
    print("ERROR: `mcp` package not found.  pip install mcp", file=sys.stderr)
    sys.exit(1)


# ── type coercion helper ───────────────────────────────────────────────────────

_TYPE_MAP = {
    "str": str, "string": str,
    "int": int, "integer": int,
    "float": float, "number": float,
    "bool": bool, "boolean": bool,
}

def _coerce(value: str, type_hint: str):
    fn = _TYPE_MAP.get(type_hint.lower().strip())
    if fn is bool:
        return value.lower() not in ("false", "0", "no", "")
    return fn(value) if fn else value


# ── discovery ─────────────────────────────────────────────────────────────────

def _discover() -> dict:
    """Returns {tool_name: {instance, method_name, schema_ep}}."""
    tools: dict = {}
    for f in sorted(SERVICES_DIR.glob("_*MS.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        for _name, cls in inspect.getmembers(mod, inspect.isclass):
            if not getattr(cls, "_is_microservice", False):
                continue
            try:
                schema = extract_service_schema(cls)
                instance = cls()
            except Exception:
                continue
            svc_name = schema["meta"]["name"]
            for ep in schema["endpoints"]:
                tool_name = f"{svc_name}__{ep['name']}"
                tools[tool_name] = {
                    "instance": instance,
                    "method": ep["name"],
                    "ep": ep,
                    "svc": svc_name,
                }
    return tools


_TOOLS = _discover()

server = Server("ms-toolbox")


# ── MCP handlers ──────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[mcp_types.Tool]:
    result = []
    for tool_name, info in sorted(_TOOLS.items()):
        ep = info["ep"]
        props = {
            k: {"type": "string", "description": v}
            for k, v in ep["inputs"].items()
        }
        result.append(mcp_types.Tool(
            name=tool_name,
            description=f"[{info['svc']}] {ep['description']}",
            inputSchema={
                "type": "object",
                "properties": props,
                "required": list(ep["inputs"].keys()),
            },
        ))
    return result


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    if name not in _TOOLS:
        return [mcp_types.TextContent(type="text", text=f"Unknown tool: {name}")]
    info = _TOOLS[name]
    ep   = info["ep"]
    method = getattr(info["instance"], info["method"])
    # coerce string args from MCP into declared types
    kwargs = {
        k: _coerce(str(v), ep["inputs"].get(k, "str"))
        for k, v in arguments.items()
    }
    try:
        result = method(**kwargs)
        return [mcp_types.TextContent(type="text",
                                      text=json.dumps(result, indent=2, default=str))]
    except Exception as exc:
        return [mcp_types.TextContent(type="text", text=f"Error calling {name}: {exc}")]


# ── entry point ───────────────────────────────────────────────────────────────

async def _main() -> None:
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
```

---

## FILE: `.microservice-library/pyproject.toml`

```toml
[project]
name = "ms-toolbox"
version = "1.0.0"
description = "Lean microservice toolbox — CLI and MCP surface"
requires-python = ">=3.11"

[project.optional-dependencies]
mcp = ["mcp>=1.0"]

[project.scripts]
ms-toolbox = "cli:main"

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "B"]
ignore = ["E501"]
```

---

## FILE: `.microservice-library/README.md`

```markdown
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
```

---

## FILE: `_spine/inference-runs.jsonl`

```text
{"kind": "schema", "id": "inference-run", "version": 1, "definition": {"id": "inference-run", "version": 1, "title": "Inference run", "required": ["step", "model", "status", "prompt"], "properties": {"step": {"type": "integer", "label": "Step"}, "model": {"type": "string", "label": "Model"}, "status": {"type": "string", "label": "Status", "enum": ["success", "stopped", "error"]}, "prompt": {"type": "string", "format": "textarea", "label": "Submitted prompt"}, "options": {"type": "object", "label": "Options"}, "response": {"type": "string", "format": "textarea", "label": "Response"}, "error": {"type": "string", "label": "Error"}, "elapsed_s": {"type": "number", "label": "Elapsed (s)"}, "context": {"type": "string", "label": "Spine context"}}}, "ts": "2026-11-04T15:27:41.612486+00:00"}
{"kind": "entry", "schema": "inference-run@1", "ts": "2026-11-04T15:27:41.617750+00:00", "data": {"step": 2, "model": "deepseek-r1:14b", "status": "success", "prompt": "Hello Deepseek!", "options": {"temperature": 0.8, "top_p": 0.9, "num_ctx": 4096}, "response": "Hello! How can I assist you today? 😊", "error": "", "elapsed_s": 37.48}}
```

---

## FILE: `_spine/klein-bottle-spine.jsonl`

```text
{"kind": "schema", "id": "my-schema", "version": 1, "definition": {"id": "my-schema", "version": 1, "properties": {"field_name": {"type": "string", "label": "Field Label", "description": "What this field holds"}, "context_refs": {"type": "array", "label": "Context Refs", "description": "Pointers to related entries. Bare timestamp = same spine. 'spine-name::timestamp' = cross-spine. Example value: [\"2026-11-02T00:00:05.000000+00:00\", \"other-spine::2026-11-01T12:00:00.000000+00:00\"]"}, "context_summary": {"type": "string", "format": "textarea", "label": "Context Summary", "description": "Prewritten narrative explaining what the context_refs contribute to understanding this entry — so an agent doesn't have to synthesize them cold. Example: \"See decision-log entry for why this approach was chosen and the review entry for its known limitations.\""}}}, "ts": "2026-11-04T15:36:08.738013+00:00"}
{"kind": "schema", "id": "default-schema", "version": 1, "definition": {"id": "default-schema", "version": 1, "properties": {"field_name": {"type": "string", "label": "Field Label", "description": "What this field holds"}, "context_refs": {"type": "array", "label": "Context Refs", "description": "Pointers to related entries. Bare timestamp = same spine. 'spine-name::timestamp' = cross-spine. Example value: [\"2026-11-02T00:00:05.000000+00:00\", \"other-spine::2026-11-01T12:00:00.000000+00:00\"]"}, "context_summary": {"type": "string", "format": "textarea", "label": "Context Summary", "description": "Prewritten narrative explaining what the context_refs contribute to understanding this entry — so an agent doesn't have to synthesize them cold. Example: \"See decision-log entry for why this approach was chosen and the review entry for its known limitations.\""}}}, "ts": "2026-11-04T15:36:26.775983+00:00"}
{"kind": "entry", "schema": "default-schema@1", "ts": "2026-11-04T15:39:25.201902+00:00", "data": {"field_name": "test", "context_refs": [], "context_summary": "asldfksadl;kfjasl;kdjf"}}
{"kind": "schema", "id": "klein-bottle-schema", "version": 1, "definition": {"id": "klein-bottle-schema", "version": 1, "properties": {"field_name": {"type": "string", "label": "Field Label", "description": "What this field holds"}, "context_refs": {"type": "array", "label": "Context Refs", "description": "Pointers to related entries. Bare timestamp = same spine. 'spine-name::timestamp' = cross-spine. Example value: [\"2026-11-02T00:00:05.000000+00:00\", \"other-spine::2026-11-01T12:00:00.000000+00:00\"]"}, "context_summary": {"type": "string", "format": "textarea", "label": "Context Summary", "description": "Prewritten narrative explaining what the context_refs contribute to understanding this entry — so an agent doesn't have to synthesize them cold. Example: \"See decision-log entry for why this approach was chosen and the review entry for its known limitations.\""}, "notes_area": {"type": "string", "format": "textarea", "label": "Notes", "description": "Jot some notes here."}}}, "ts": "2026-11-04T15:46:24.559704+00:00"}
```

---

## FILE: `_spine/things-to-fix.jsonl`

```text
{"kind": "schema", "id": "things-to-fix-schema", "version": 1, "definition": {"id": "things-to-fix-schema", "version": 1, "properties": {"field_name": {"type": "string", "label": "Field Label", "description": "What this field holds"}, "context_refs": {"type": "array", "label": "Context Refs", "description": "Pointers to related entries. Bare timestamp = same spine. 'spine-name::timestamp' = cross-spine. Example value: [\"2026-11-02T00:00:05.000000+00:00\", \"other-spine::2026-11-01T12:00:00.000000+00:00\"]"}, "context_summary": {"type": "string", "format": "textarea", "label": "Context Summary", "description": "Prewritten narrative explaining what the context_refs contribute to understanding this entry — so an agent doesn't have to synthesize them cold. Example: \"See decision-log entry for why this approach was chosen and the review entry for its known limitations.\""}}}, "ts": "2026-11-04T15:48:06.720501+00:00"}
{"kind": "schema", "id": "fix-it-list-schema", "version": 1, "definition": {"id": "fix-it-list-schema", "version": 1, "properties": {"Item to fix": {"type": "string", "label": "Item:", "description": "What thing needs fixing?"}, "context_refs": {"type": "array", "label": "Context Refs", "description": "Pointers to related entries. Bare timestamp = same spine. 'spine-name::timestamp' = cross-spine. Example value: [\"2026-11-02T00:00:05.000000+00:00\", \"other-spine::2026-11-01T12:00:00.000000+00:00\"]"}, "context_summary": {"type": "string", "format": "textarea", "label": "Context Summary", "description": "Prewritten narrative explaining what the context_refs contribute to understanding this entry — so an agent doesn't have to synthesize them cold. Example: \"See decision-log entry for why this approach was chosen and the review entry for its known limitations.\""}}}, "ts": "2026-11-04T15:49:39.941323+00:00"}
{"kind": "entry", "schema": "fix-it-list-schema@1", "ts": "2026-11-04T15:50:46.532874+00:00", "data": {"Item to fix": "Schema Line Numbers", "context_refs": [], "context_summary": "The schema edit window ( and indeed any text edit box may need this) needs line numbers. So when an error hits I know which line to move to since errors show line numbers."}}
{"kind": "entry", "schema": "fix-it-list-schema@1", "ts": "2026-11-04T15:51:52.196061+00:00", "data": {"Item to fix": "Schema logged error highlighting", "context_refs": [], "context_summary": "The schema edit window should highlight the error or let the user click on the error and then it highlights that particular error in the schema they typed so they can fix it."}}
{"kind": "entry", "schema": "fix-it-list-schema@1", "ts": "2026-11-04T15:56:36.761056+00:00", "data": {"Item to fix": "inference chains", "context_refs": [], "context_summary": "closing a step does not remove that steps count from the set of steps. We need to handle how steps collapse. Closing a single step should collapse the chain by a single link. This would mean all previous responses can remain and all responses after the removed link are cleared until the chain re-runs."}}
{"kind": "entry", "schema": "fix-it-list-schema@1", "ts": "2026-11-04T15:58:04.226389+00:00", "data": {"Item to fix": "schema editor tab bug", "context_refs": [], "context_summary": "the schema editor 'Entry Form' should allow the user to tab between fields which does work BUT the context refs box hams this up and you get stuck tabbing around inside the context refs...figure it out."}}
```

---

## FILE: `data/raithetopia.json`

```json
{
  "version": 1,
  "name": "Untitled World",
  "start_room": "hall",
  "rooms": [
    {
      "id": "hall",
      "name": "Entrance Hall",
      "area": "Old House",
      "description": "A cold draft moves beneath the front door.",
      "exits": {
        "north": "study"
      },
      "objects": [
        {
          "id": "table",
          "name": "Oak Table",
          "kind": "furniture",
          "description": "A scarred oak table."
        }
      ],
      "actors": [],
      "secrets": [],
      "environment": {
        "weather": "rain",
        "light": "dim",
        "sound": "Rain on the roof"
      }
    },
    {
      "id": "study",
      "name": "Study",
      "area": "Old House",
      "description": "A wardrobe stands against the northern wall.",
      "exits": {
        "south": "hall",
        "inside": "wardrobe"
      },
      "objects": [
        {
          "id": "wardrobe_object",
          "name": "Wardrobe",
          "kind": "furniture",
          "description": "An old wardrobe."
        }
      ],
      "actors": [],
      "secrets": [],
      "environment": {
        "weather": "rain",
        "light": "dim",
        "sound": "Clock ticking"
      }
    },
    {
      "id": "wardrobe",
      "name": "Inside Wardrobe",
      "area": "Old House",
      "description": "Dark coats hang over a hidden compartment.",
      "exits": {
        "outside": "study"
      },
      "objects": [
        {
          "id": "key",
          "name": "Iron Key",
          "kind": "item",
          "description": "A small iron key."
        }
      ],
      "actors": [],
      "secrets": [
        {
          "id": "false_back",
          "description": "A loose wooden panel."
        }
      ],
      "environment": {
        "light": "dark"
      },
      "interior_of": "study"
    }
  ]
}
```

---

## FILE: `data/world.json`

```json
{
  "version": 1,
  "name": "Raithetopia",
  "start_room": "hall",
  "rooms": [
    {
      "id": "hall",
      "name": "Entrance Hall",
      "area": "Old House",
      "description": "A cold draft moves beneath the front door.",
      "exits": {
        "north": "study"
      },
      "objects": [
        {
          "id": "table",
          "name": "Oak Table",
          "kind": "furniture",
          "description": "A scarred oak table."
        }
      ],
      "actors": [],
      "secrets": [],
      "environment": {
        "weather": "rain",
        "light": "dim",
        "sound": "Rain on the roof"
      }
    },
    {
      "id": "study",
      "name": "Study",
      "area": "Old House",
      "description": "A wardrobe stands against the northern wall.",
      "exits": {
        "south": "hall",
        "inside": "wardrobe"
      },
      "objects": [
        {
          "id": "wardrobe_object",
          "name": "Wardrobe",
          "kind": "furniture",
          "description": "An old wardrobe."
        }
      ],
      "actors": [],
      "secrets": [],
      "environment": {
        "weather": "rain",
        "light": "dim",
        "sound": "Clock ticking"
      }
    },
    {
      "id": "wardrobe",
      "name": "Inside Wardrobe",
      "area": "Old House",
      "description": "Dark coats hang over a hidden compartment.",
      "exits": {
        "outside": "study"
      },
      "objects": [
        {
          "id": "key",
          "name": "Iron Key",
          "kind": "item",
          "description": "A small iron key."
        }
      ],
      "actors": [],
      "secrets": [
        {
          "id": "false_back",
          "description": "A loose wooden panel."
        }
      ],
      "environment": {
        "light": "dark"
      },
      "interior_of": "study"
    }
  ]
}
```

---

## FILE: `examples/rooms.json`

```json
{
  "rooms": [
    {
      "id": "hall",
      "name": "Entrance Hall",
      "area": "Old House",
      "description": "A cold draft moves beneath the front door.",
      "exits": {"north": "study"},
      "objects": [
        {"id": "table", "name": "Oak Table", "kind": "furniture", "description": "A scarred oak table."}
      ],
      "actors": [],
      "secrets": [],
      "environment": {"weather": "rain", "light": "dim", "sound": "Rain on the roof"}
    },
    {
      "id": "study",
      "name": "Study",
      "area": "Old House",
      "description": "A wardrobe stands against the northern wall.",
      "exits": {"south": "hall", "inside": "wardrobe"},
      "objects": [{"id": "wardrobe_object", "name": "Wardrobe", "kind": "furniture", "description": "An old wardrobe."}],
      "actors": [],
      "secrets": [],
      "environment": {"weather": "rain", "light": "dim", "sound": "Clock ticking"}
    },
    {
      "id": "wardrobe",
      "name": "Inside Wardrobe",
      "area": "Old House",
      "description": "Dark coats hang over a hidden compartment.",
      "exits": {"outside": "study"},
      "objects": [{"id": "key", "name": "Iron Key", "kind": "item", "description": "A small iron key."}],
      "actors": [],
      "secrets": [{"id": "false_back", "description": "A loose wooden panel."}],
      "environment": {"light": "dark"},
      "interior_of": "study"
    }
  ]
}
```

---

## FILE: `src/surfaces/__init__.py`

```python
"""UI surfaces for the standalone adventure project."""
```

---

## FILE: `src/surfaces/builder.py`

```python
"""Tkinter world-builder surface. It depends on the builder use cases, not a game engine."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..world_builder import WorldBuilder
from ..world_model import ID_PATTERN, WorldValidationError, pretty


class BuilderSurface(ttk.Frame):
    def __init__(self, master: tk.Tk, builder: WorldBuilder):
        super().__init__(master, padding=12)
        self.builder = builder
        self.selected_id: str | None = None
        self._base: dict = {}
        self._saved_signature: tuple = ()
        self._refreshing = False
        self.vars = {key: tk.StringVar() for key in
                     ("id", "name", "area", "weather", "light", "sound")}
        self.world_name = tk.StringVar(value=builder.world["name"])
        self.start_room = tk.StringVar(value=builder.world["start_room"] or "")
        # A surface is hosted by the application shell (Notebook); do not pack it here.
        self._build()
        self.refresh_tree()
        self.new_room(ask=False)

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="World:").pack(side="left")
        ttk.Entry(header, textvariable=self.world_name, width=30).pack(side="left", padx=6)
        ttk.Label(header, text="Start room:").pack(side="left", padx=(14, 3))
        self.start_combo = ttk.Combobox(header, textvariable=self.start_room, width=20, state="readonly")
        self.start_combo.pack(side="left", padx=4)
        ttk.Button(header, text="Save World Settings", command=self.save_settings).pack(side="left", padx=8)
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)
        nav = ttk.Frame(body, padding=4)
        content = ttk.Frame(body, padding=6)
        body.add(nav, weight=1)
        body.add(content, weight=3)

        ttk.Label(nav, text="Areas / Rooms", font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.tree = ttk.Treeview(nav, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_room)
        controls = ttk.Frame(nav)
        controls.pack(fill="x", pady=7)
        ttk.Button(controls, text="New Room", command=self.new_room).pack(side="left", padx=2)
        ttk.Button(controls, text="Delete", command=self.delete_room).pack(side="left", padx=2)
        ttk.Button(nav, text="Import / Paste JSON...", command=self.import_dialog).pack(fill="x", pady=3)
        ttk.Button(nav, text="Export World JSON...", command=self.export_world).pack(fill="x", pady=3)

        ttk.Label(content, text="Room Editor", font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(0, 9))
        top = ttk.Frame(content)
        top.pack(fill="x", pady=2)
        for index, (key, label, size) in enumerate((("id", "Room ID", 19), ("name", "Name", 32), ("area", "Area", 24))):
            part = ttk.Frame(top)
            part.pack(side="left", padx=(0, 12))
            ttk.Label(part, text=label).pack(anchor="w")
            entry = ttk.Entry(part, textvariable=self.vars[key], width=size)
            entry.pack(anchor="w")
            if key == "id":
                self.id_entry = entry
        ttk.Label(content, text="Description").pack(anchor="w", pady=(7, 2))
        self.description = tk.Text(content, height=4, wrap="word", undo=True)
        self.description.pack(fill="x")
        ttk.Label(content, text="Exits — one per line: direction:room_id").pack(anchor="w", pady=(9, 2))
        self.exits = tk.Text(content, height=4, wrap="none", undo=True)
        self.exits.pack(fill="x")

        environment = ttk.LabelFrame(content, text="Environment — optional text values")
        environment.pack(fill="x", pady=(9, 2))
        for key, title in (("weather", "Weather"), ("light", "Light"), ("sound", "Sound")):
            part = ttk.Frame(environment)
            part.pack(side="left", padx=6, pady=5)
            ttk.Label(part, text=title).pack(anchor="w")
            ttk.Entry(part, textvariable=self.vars[key], width=22).pack()

        ttk.Label(content, text="Objects — JSON array (or use Add Object)").pack(anchor="w", pady=(8, 2))
        self.objects = tk.Text(content, height=7, wrap="none", undo=True)
        self.objects.pack(fill="both", expand=True)
        row = ttk.Frame(content)
        row.pack(fill="x", pady=(8, 3))
        ttk.Button(row, text="Add Object...", command=self.add_object).pack(side="left")
        ttk.Button(row, text="Full Room JSON...", command=self.edit_room_json).pack(side="left", padx=8)
        ttk.Button(row, text="Save Room", command=self.save_room).pack(side="right")
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", pady=(8, 0))

    def _form_signature(self) -> tuple:
        return (tuple(self.vars[k].get() for k in ("id", "name", "area", "weather", "light", "sound")),
                self.description.get("1.0", "end-1c"), self.exits.get("1.0", "end-1c"),
                self.objects.get("1.0", "end-1c"))

    def _guard_unsaved(self) -> bool:
        if self._form_signature() == self._saved_signature:
            return True
        return messagebox.askyesno("Unsaved room edits", "Discard unsaved edits to this room?", parent=self)

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.edit_modified(False)

    def _populate(self, room: dict, existing: bool) -> None:
        self._base = deepcopy(room)
        for key in ("id", "name", "area"):
            self.vars[key].set(room.get(key, ""))
        self.id_entry.configure(state="readonly" if existing else "normal")
        self._set_text(self.description, room.get("description", ""))
        self._set_text(self.exits, "\n".join(f"{key}:{value}" for key, value in room.get("exits", {}).items()))
        env = room.get("environment", {})
        for key in ("weather", "light", "sound"):
            self.vars[key].set(str(env.get(key, "")))
        self._set_text(self.objects, pretty(room.get("objects", [])).rstrip("\n"))
        self._saved_signature = self._form_signature()

    def refresh_tree(self, focus: str | None = None) -> None:
        self._refreshing = True
        self.tree.delete(*self.tree.get_children())
        rooms = sorted(self.builder.rooms(), key=lambda r: (r["area"].lower(), r["name"].lower()))
        areas = {}
        for room in rooms:
            area = room["area"]
            if area not in areas:
                areas[area] = self.tree.insert("", "end", text=area, open=True)
            node = self.tree.insert(areas[area], "end", iid=f"room:{room['id']}", text=room["name"])
            if room["id"] == focus:
                self.tree.selection_set(node)
                self.tree.see(node)
        self.start_combo["values"] = [""] + [room["id"] for room in rooms]
        self.start_room.set(self.builder.world["start_room"] or "")
        self.world_name.set(self.builder.world["name"])
        warnings = self.builder.warnings()
        self.status.set(f"{len(rooms)} rooms. {len(warnings)} unresolved exit reference(s).")
        self._refreshing = False

    def _select_room(self, _event=None) -> None:
        if self._refreshing:
            return
        selection = self.tree.selection()
        if not selection or not selection[0].startswith("room:"):
            return
        new_id = selection[0].removeprefix("room:")
        if new_id == self.selected_id:
            return
        if not self._guard_unsaved():
            self._refreshing = True
            if self.selected_id is not None and self.tree.exists(f"room:{self.selected_id}"):
                self.tree.selection_set(f"room:{self.selected_id}")
            else:
                self.tree.selection_remove(*self.tree.selection())
            self._refreshing = False
            return
        self.selected_id = new_id
        self._populate(self.builder.room(new_id), existing=True)

    def new_room(self, ask: bool = True) -> None:
        if ask and not self._guard_unsaved():
            return
        self.selected_id = None
        self._refreshing = True
        self.tree.selection_remove(*self.tree.selection())
        self._refreshing = False
        self._populate({"id": "", "name": "", "area": "Ungrouped", "description": "",
                        "exits": {}, "environment": {}, "objects": []}, existing=False)
        self.vars["name"].set("")
        self._saved_signature = self._form_signature()
        self.id_entry.focus_set()

    def _read_form(self) -> dict:
        room = deepcopy(self._base)
        for key in ("id", "name", "area"):
            room[key] = self.vars[key].get().strip()
        room["description"] = self.description.get("1.0", "end-1c")
        exits = {}
        for number, line in enumerate(self.exits.get("1.0", "end-1c").splitlines(), 1):
            if not line.strip():
                continue
            if ":" not in line:
                raise WorldValidationError(f"Exit line {number} needs direction:room_id")
            direction, target = (part.strip() for part in line.split(":", 1))
            if not direction or not target or direction in exits:
                raise WorldValidationError(f"Invalid or duplicate direction on exit line {number}")
            exits[direction] = target
        room["exits"] = exits
        env = deepcopy(room.get("environment", {}))
        for key in ("weather", "light", "sound"):
            value = self.vars[key].get().strip()
            if value:
                env[key] = value
            else:
                env.pop(key, None)
        room["environment"] = env
        try:
            room["objects"] = json.loads(self.objects.get("1.0", "end-1c") or "[]")
        except json.JSONDecodeError as exc:
            raise WorldValidationError(f"Objects JSON: {exc}") from exc
        return room

    def save_room(self) -> None:
        try:
            room = self._read_form()
            self.builder.save_room(room, original_id=self.selected_id)
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot save room", str(exc), parent=self)
            return
        self.selected_id = room["id"]
        self.refresh_tree(focus=self.selected_id)
        self._populate(self.builder.room(self.selected_id), existing=True)
        self.status.set(f"Saved room '{self.selected_id}' to world.json")

    def delete_room(self) -> None:
        if self.selected_id is None or not self._guard_unsaved():
            return
        if not messagebox.askyesno("Delete room", f"Delete '{self.selected_id}'?", parent=self):
            return
        try:
            self.builder.delete_room(self.selected_id)
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot delete room", str(exc), parent=self)
            return
        self.selected_id = None
        self.refresh_tree()
        self.new_room(ask=False)

    def save_settings(self) -> None:
        try:
            self.builder.settings(self.world_name.get().strip(), self.start_room.get() or None)
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot save settings", str(exc), parent=self)
            return
        self.status.set("World settings saved")

    def add_object(self) -> None:
        window = tk.Toplevel(self)
        window.title("Add Object")
        window.transient(self.winfo_toplevel())
        window.grab_set()
        window.resizable(False, False)
        fields = {}
        for index, (key, label) in enumerate((("id", "Object ID"), ("name", "Name"), ("kind", "Kind (item/furniture/etc)"), ("description", "Description"))):
            ttk.Label(window, text=label).grid(row=index, column=0, padx=12, pady=7, sticky="e")
            fields[key] = tk.StringVar()
            ttk.Entry(window, textvariable=fields[key], width=44).grid(row=index, column=1, padx=12, pady=7)
        fields["kind"].set("item")

        def save() -> None:
            try:
                objs = json.loads(self.objects.get("1.0", "end-1c") or "[]")
                if not isinstance(objs, list):
                    raise WorldValidationError("Objects must be a JSON array")
                obj = {key: var.get().strip() for key, var in fields.items()}
                if not ID_PATTERN.fullmatch(obj["id"]) or not obj["name"]:
                    raise WorldValidationError("Object ID and name are required; IDs cannot contain spaces")
                if any(isinstance(existing, dict) and existing.get("id") == obj["id"] for existing in objs):
                    raise WorldValidationError("Object ID already exists in this room")
                objs.append(obj)
                self._set_text(self.objects, pretty(objs).rstrip("\n"))
            except (ValueError, WorldValidationError) as exc:
                messagebox.showerror("Cannot add object", str(exc), parent=window)
                return
            window.destroy()
        ttk.Button(window, text="Add", command=save).grid(row=len(fields), column=1, sticky="e", padx=12, pady=10)
        window.bind("<Escape>", lambda _event: window.destroy())

    def edit_room_json(self) -> None:
        if self.selected_id is None:
            messagebox.showinfo("Select a room", "Save the new room before editing its full JSON.", parent=self)
            return
        if not self._guard_unsaved():
            return
        window = tk.Toplevel(self)
        window.title(f"Room JSON — {self.selected_id}")
        window.geometry("750x610")
        window.transient(self.winfo_toplevel())
        editor = tk.Text(window, wrap="none", undo=True)
        editor.pack(fill="both", expand=True, padx=10, pady=10)
        self._set_text(editor, pretty(self.builder.room(self.selected_id)))

        def apply() -> None:
            try:
                raw = json.loads(editor.get("1.0", "end-1c"))
                self.builder.save_room(raw, original_id=self.selected_id)
            except (ValueError, WorldValidationError, OSError) as exc:
                messagebox.showerror("Cannot apply JSON", str(exc), parent=window)
                return
            room_id = self.selected_id
            self.refresh_tree(focus=room_id)
            self._populate(self.builder.room(room_id), existing=True)
            window.destroy()
        ttk.Button(window, text="Apply JSON", command=apply).pack(anchor="e", padx=10, pady=(0, 10))

    def import_dialog(self) -> None:
        if not self._guard_unsaved():
            return
        window = tk.Toplevel(self)
        window.title("Import / Paste Rooms or World JSON")
        window.geometry("830x610")
        window.transient(self.winfo_toplevel())
        ttk.Label(window, text="Paste a room object, list of rooms, or a {rooms: [...]} world document.").pack(anchor="w", padx=10, pady=5)
        editor = tk.Text(window, wrap="none", undo=True)
        editor.pack(fill="both", expand=True, padx=10, pady=5)
        mode = tk.StringVar(value="add")
        options = ttk.Frame(window)
        options.pack(fill="x", padx=10, pady=5)
        for value, label in (("add", "Add new (skip existing IDs)"),
                             ("update", "Update matching IDs"), ("replace", "Replace whole world")):
            ttk.Radiobutton(options, text=label, variable=mode, value=value).pack(side="left", padx=6)

        def load_file() -> None:
            path = filedialog.askopenfilename(parent=window, filetypes=[("JSON", "*.json"), ("All files", "*.*")])
            if path:
                try:
                    self._set_text(editor, Path(path).read_text(encoding="utf-8"))
                except OSError as exc:
                    messagebox.showerror("Cannot load file", str(exc), parent=window)

        def apply() -> None:
            if mode.get() == "replace" and not messagebox.askyesno(
                "Replace whole world", "All existing rooms will be replaced. Continue?", parent=window
            ):
                return
            try:
                changed, skipped = self.builder.import_json(editor.get("1.0", "end-1c"), mode=mode.get())
            except (ValueError, WorldValidationError, OSError) as exc:
                messagebox.showerror("Import failed", str(exc), parent=window)
                return
            self.selected_id = None
            self.refresh_tree()
            self.new_room(ask=False)
            messagebox.showinfo("Import complete", f"Imported or updated: {changed}\nSkipped: {skipped}\n"
                                f"Unresolved exits: {len(self.builder.warnings())}", parent=self)
            window.destroy()
        actions = ttk.Frame(window)
        actions.pack(fill="x", padx=10, pady=10)
        ttk.Button(actions, text="Load JSON File...", command=load_file).pack(side="left")
        ttk.Button(actions, text="Import", command=apply).pack(side="right")

    def export_world(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("JSON", "*.json")],
                                            initialfile="world-export.json")
        if path:
            try:
                Path(path).write_text(self.builder.export_json(), encoding="utf-8")
                self.status.set(f"Exported {path}")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc), parent=self)
```

---

## FILE: `src/surfaces/game.py`

```python
"""Tkinter play surface: transcript + commands over the standalone game session."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..game import GameSession
from ..world_model import WorldValidationError


class GameSurface(ttk.Frame):
    def __init__(self, master: tk.Misc, session: GameSession):
        super().__init__(master, padding=12)
        self.session = session
        self.command = tk.StringVar()
        self.location = tk.StringVar()
        self.inventory = tk.StringVar()
        self._build()
        self._render_initial()

    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Play", font=("TkDefaultFont", 14, "bold")).pack(side="left")
        ttk.Button(top, text="Reload World / Restart", command=self.reload_world).pack(side="right")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)
        main = ttk.Frame(body)
        sidebar = ttk.Frame(body, padding=(10, 0, 0, 0))
        body.add(main, weight=4)
        body.add(sidebar, weight=1)

        story = ttk.Frame(main)
        story.pack(fill="both", expand=True)
        self.transcript = tk.Text(story, wrap="word", state="disabled", font=("TkDefaultFont", 11),
                                  padx=10, pady=10, spacing3=6)
        self.transcript.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(story, orient="vertical", command=self.transcript.yview)
        scrollbar.pack(side="right", fill="y")
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.tag_configure("command", foreground="#4067A4", spacing1=10)
        self.transcript.tag_configure("title", font=("TkDefaultFont", 11, "bold"))
        cmd_row = ttk.Frame(main)
        cmd_row.pack(fill="x", pady=(10, 0))
        ttk.Label(cmd_row, text="Command:").pack(side="left", padx=(0, 5))
        self.entry = ttk.Entry(cmd_row, textvariable=self.command)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._submit)
        ttk.Button(cmd_row, text="Run", command=self._submit).pack(side="left", padx=(5, 0))
        quick = ttk.Frame(main)
        quick.pack(fill="x", pady=(8, 0))
        for caption, command in (("Look", "look"), ("Inventory", "inventory"), ("Help", "help")):
            ttk.Button(quick, text=caption, command=lambda c=command: self.run(c)).pack(side="left", padx=(0, 6))

        ttk.Label(sidebar, text="Location", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(sidebar, textvariable=self.location, wraplength=195, justify="left").pack(anchor="w", pady=(4, 16))
        ttk.Label(sidebar, text="Exits", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.exit_frame = ttk.Frame(sidebar)
        self.exit_frame.pack(fill="x", pady=(4, 16))
        ttk.Label(sidebar, text="Inventory", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(sidebar, textvariable=self.inventory, wraplength=195, justify="left").pack(anchor="w", pady=(4, 0))

    def _append(self, message: str, tag: str | None = None) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", message.rstrip() + "\n\n", tag)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _sync(self) -> None:
        view = self.session.view()
        self.location.set(f"{view.room_name}\n{view.area}" if view.area else view.room_name)
        self.inventory.set("\n".join(view.inventory) if view.inventory else "(empty)")
        for child in self.exit_frame.winfo_children():
            child.destroy()
        if not view.exits:
            ttk.Label(self.exit_frame, text="(none)").pack(anchor="w")
        for direction in view.exits:
            ttk.Button(self.exit_frame, text=direction,
                       command=lambda d=direction: self.run(f"go {d}")).pack(fill="x", pady=2)

    def _render_initial(self) -> None:
        self._append(self.session.world["name"], "title")
        self._append(self.session.look())
        self._sync()

    def _submit(self, _event=None) -> None:
        command = self.command.get().strip()
        if not command:
            return
        self.command.set("")
        self.run(command)

    def run(self, command: str) -> None:
        self._append("> " + command, "command")
        self._append(self.session.execute(command))
        self._sync()
        self.entry.focus_set()

    def reload_world(self) -> None:
        try:
            first_description = self.session.restart()
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot reload world", str(exc), parent=self)
            return
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        self._append(self.session.world["name"], "title")
        self._append(first_description)
        self._sync()
        self.entry.focus_set()
```

---

## FILE: `src/__init__.py`

```python
"""Standalone adventure project."""
```

---

## FILE: `src/app.py`

```python
"""Thin application shell. The editor and game are separate surfaces."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .game import GameSession
from .world_builder import WorldBuilder
from .world_store import WorldStore
from .surfaces.builder import BuilderSurface
from .surfaces.game import GameSurface


def main() -> None:
    root = tk.Tk()
    root.title("Adventure — World Builder & Play")
    root.geometry("1160x760")
    world_file = Path(__file__).resolve().parents[1] / "data" / "world.json"
    store = WorldStore(world_file)
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    builder = BuilderSurface(notebook, WorldBuilder(store))
    game = GameSurface(notebook, GameSession(store))
    notebook.add(builder, text="World Builder")
    notebook.add(game, text="Play")
    # Re-entering Play reloads saved editor data, not unsaved form changes.
    # Runtime state is intentionally temporary in this proof of concept.
    def on_switch(_event=None) -> None:
        if notebook.select() == str(game):
            game.reload_world()
    notebook.bind("<<NotebookTabChanged>>", on_switch)
    root.mainloop()


if __name__ == "__main__":
    main()
```

---

## FILE: `src/game.py`

```python
"""Tiny stateful text-adventure engine. No UI, filesystem writes, or sidecars.

A GameSession loads a snapshot of a world definition. Movement and items alter
only this in-memory play session, never the builder's source JSON.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .world_store import WorldStore


@dataclass(frozen=True)
class GameView:
    world_name: str
    room_id: str | None
    room_name: str
    area: str
    exits: tuple[str, ...]
    inventory: tuple[str, ...]


def _name(value: dict) -> str:
    return str(value.get("name") or value.get("id") or "Unnamed").strip()


def _matches(value: dict, query: str) -> bool:
    query = query.casefold().strip()
    if query.startswith("the "):
        query = query[4:]
    names = (str(value.get("id", "")), _name(value))
    return any(item.casefold() == query for item in names)


def _find(values: list[dict], query: str) -> tuple[dict | None, str | None]:
    """Resolve exact ID/name first, then a unique name fragment."""
    exact = [value for value in values if _matches(value, query)]
    matches = exact or [value for value in values if query.casefold().strip() in _name(value).casefold()]
    if len(matches) > 1:
        return None, "Which one? " + ", ".join(_name(value) for value in matches)
    return (matches[0], None) if matches else (None, None)


class GameSession:
    def __init__(self, store: WorldStore):
        self.store = store
        self.world: dict = {}
        self.room_id: str | None = None
        self.inventory: list[dict] = []
        self.restart()

    def restart(self) -> str:
        """Reload the editor's saved world and begin a fresh play session."""
        self.world = deepcopy(self.store.load())
        self.inventory = []
        rooms = self.world["rooms"]
        self.room_id = self.world["start_room"] or (rooms[0]["id"] if rooms else None)
        return self.look()

    def _room(self) -> dict | None:
        return next((r for r in self.world["rooms"] if r["id"] == self.room_id), None)

    def view(self) -> GameView:
        room = self._room()
        return GameView(
            world_name=self.world["name"], room_id=self.room_id,
            room_name=room["name"] if room else "No room",
            area=room["area"] if room else "",
            exits=tuple(room["exits"]) if room else (),
            inventory=tuple(_name(obj) for obj in self.inventory),
        )

    def look(self) -> str:
        room = self._room()
        if room is None:
            return "This world has no starting room. Create a room in Builder, then click Reload World."
        lines = [room["name"] + (f" — {room['area']}" if room.get("area") else "")]
        if room.get("description"):
            lines.append(str(room["description"]))
        env = room.get("environment", {})
        for key in ("weather", "light", "sound"):
            if env.get(key):
                lines.append(f"{key.capitalize()}: {env[key]}")
        objects = [obj for obj in room.get("objects", []) if not obj.get("hidden", False)]
        if objects:
            lines.append("You see: " + ", ".join(_name(obj) for obj in objects) + ".")
        actors = [actor for actor in room.get("actors", []) if not actor.get("hidden", False)]
        if actors:
            lines.append("Present: " + ", ".join(_name(actor) for actor in actors) + ".")
        exits = room.get("exits", {})
        lines.append("Exits: " + (", ".join(exits) if exits else "none") + ".")
        return "\n".join(lines)

    def move(self, direction: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        exits = room["exits"]
        direction = direction.strip().casefold()
        # Accept a direction, destination ID, or destination name (when unique).
        found = [key for key, target in exits.items() if key.casefold() == direction]
        if not found:
            destinations = {r["id"]: r for r in self.world["rooms"]}
            found = [key for key, target in exits.items() if target.casefold() == direction or
                     (target in destinations and destinations[target]["name"].casefold() == direction)]
        if not found:
            return f"No exit '{direction}' from here. Available exits: {', '.join(exits) or 'none'}."
        if len(found) > 1:
            return "Ambiguous destination. Choose an exit: " + ", ".join(found)
        target = exits[found[0]]
        if not any(r["id"] == target for r in self.world["rooms"]):
            return f"Exit '{found[0]}' points to a missing room ('{target}')."
        self.room_id = target
        return self.look()

    def inspect(self, query: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        if query.casefold().strip() in {"room", "here", "around"}:
            return self.look()
        candidates = ([obj for obj in room.get("objects", []) if not obj.get("hidden", False)]
                      + [actor for actor in room.get("actors", []) if not actor.get("hidden", False)]
                      + self.inventory)
        obj, ambiguity = _find(candidates, query)
        if ambiguity:
            return ambiguity
        if obj is None:
            return f"You don't see '{query}' here."
        return f"{_name(obj)}\n{obj.get('description') or 'Nothing unusual stands out.'}"

    @staticmethod
    def _portable(obj: dict) -> bool:
        # An explicit portable/takeable flag overrides the item kind.
        if "portable" in obj:
            return obj["portable"] is True
        if "takeable" in obj:
            return obj["takeable"] is True
        return str(obj.get("kind", "")).casefold() == "item"

    def take(self, query: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        objects = [obj for obj in room.get("objects", []) if not obj.get("hidden", False)]
        obj, ambiguity = _find(objects, query)
        if ambiguity:
            return ambiguity
        if obj is None:
            return f"You don't see '{query}' here."
        if not self._portable(obj):
            return f"You can't take {_name(obj)}. (Make it an item or set portable: true.)"
        room["objects"].remove(obj)
        self.inventory.append(obj)
        return f"Taken: {_name(obj)}."

    def drop(self, query: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        obj, ambiguity = _find(self.inventory, query)
        if ambiguity:
            return ambiguity
        if obj is None:
            return f"You aren't carrying '{query}'."
        self.inventory.remove(obj)
        room["objects"].append(obj)
        return f"Dropped: {_name(obj)}."

    def inventory_text(self) -> str:
        return "You're carrying: " + ", ".join(_name(obj) for obj in self.inventory) + "." if self.inventory else "Your inventory is empty."

    def execute(self, raw: str) -> str:
        command = raw.strip()
        if not command:
            return "Enter a command, or type 'help'."
        verb, _, arg = command.partition(" ")
        verb, arg = verb.casefold(), arg.strip()
        room = self._room()
        if verb in {"help", "?"}:
            return ("Commands:\n"
                    "  look (l) — describe current room\n"
                    "  inspect <object> (x, examine, look at)\n"
                    "  go <exit> — travel; exit names also work alone\n"
                    "  enter <exit/room>, leave — travel through named exits\n"
                    "  take <item> (get, pick up)\n"
                    "  drop <item>\n"
                    "  inventory (i, inv)\n"
                    "  help (?)\n"
                    "  Reload World — restart from the builder's saved JSON")
        if verb in {"l", "look"} and not arg:
            return self.look()
        if verb in {"i", "inv", "inventory"}:
            return self.inventory_text()
        if command.casefold().startswith("look at "):
            return self.inspect(command[8:].strip())
        if command.casefold().startswith("pick up "):
            return self.take(command[8:].strip())
        if verb in {"inspect", "examine", "x"} or (verb == "look" and arg):
            return self.inspect(arg) if arg else "Inspect what?"
        if verb in {"take", "get"}:
            return self.take(arg) if arg else "Take what?"
        if verb == "drop":
            return self.drop(arg) if arg else "Drop what?"
        if verb in {"go", "move", "walk", "enter"}:
            return self.move(arg) if arg else "Go where?"
        if verb == "leave":
            if room and "outside" in room["exits"]:
                return self.move("outside")
            if room and "out" in room["exits"]:
                return self.move("out")
            return "There's no obvious way to leave by that command. Try 'go <exit>'."
        if room and any(key.casefold() == command.casefold() for key in room["exits"]):
            return self.move(command)
        return f"Unknown command: {command}. Type 'help' for commands."
```

---

## FILE: `src/world_builder.py`

```python
"""World-builder use cases, independent from the editor widgets."""
from __future__ import annotations

from copy import deepcopy
import json

from .world_model import (
    WorldValidationError, exit_warnings, normalize_room, normalize_world, parse_rooms, pretty
)
from .world_store import WorldStore


class WorldBuilder:
    def __init__(self, store: WorldStore):
        self.store = store
        self.world = store.load()

    def rooms(self) -> list[dict]:
        return deepcopy(self.world["rooms"])

    def room(self, room_id: str) -> dict:
        for room in self.world["rooms"]:
            if room["id"] == room_id:
                return deepcopy(room)
        raise WorldValidationError(f"Room not found: {room_id}")

    def save_room(self, raw: dict, original_id: str | None = None) -> None:
        room = normalize_room(raw)
        room_id = room["id"]
        if original_id is not None and room_id != original_id:
            raise WorldValidationError("Room IDs cannot be renamed in this version")
        existing = {item["id"]: i for i, item in enumerate(self.world["rooms"])}
        if original_id is None and room_id in existing:
            raise WorldValidationError(f"Room ID already exists: {room_id}")
        draft = deepcopy(self.world)
        if room_id in existing:
            draft["rooms"][existing[room_id]] = room
        else:
            draft["rooms"].append(room)
        if draft["start_room"] is None:
            draft["start_room"] = room_id
        self._commit(draft)

    def delete_room(self, room_id: str) -> None:
        self.room(room_id)
        refs = [(r["id"], direction) for r in self.world["rooms"] if r["id"] != room_id
                for direction, target in r["exits"].items() if target == room_id]
        if refs:
            raise WorldValidationError(f"Remove exits pointing to '{room_id}' first: {refs}")
        draft = deepcopy(self.world)
        draft["rooms"] = [r for r in draft["rooms"] if r["id"] != room_id]
        if draft["start_room"] == room_id:
            draft["start_room"] = draft["rooms"][0]["id"] if draft["rooms"] else None
        self._commit(draft)

    def settings(self, name: str, start_room: str | None) -> None:
        draft = deepcopy(self.world)
        draft["name"] = name
        draft["start_room"] = start_room or None
        self._commit(draft)

    def import_json(self, source_text: str, mode: str = "add") -> tuple[int, int]:
        if mode not in ("add", "update", "replace"):
            raise ValueError("mode must be add, update or replace")
        try:
            payload = json.loads(source_text)
        except json.JSONDecodeError as exc:
            raise WorldValidationError(f"Invalid JSON: {exc}") from exc
        incoming, metadata = parse_rooms(payload)
        draft = deepcopy(self.world)
        if mode == "replace":
            draft["rooms"] = incoming
            if metadata is not None:
                draft.update(metadata)
            draft["start_room"] = (
                draft["start_room"] if draft.get("start_room") in {r["id"] for r in incoming}
                else (incoming[0]["id"] if incoming else None)
            )
            added, skipped = len(incoming), 0
        else:
            existing = {r["id"]: i for i, r in enumerate(draft["rooms"])}
            added, skipped = 0, 0
            for room in incoming:
                idx = existing.get(room["id"])
                if idx is not None and mode == "add":
                    skipped += 1
                    continue
                if idx is not None:
                    draft["rooms"][idx] = room
                else:
                    existing[room["id"]] = len(draft["rooms"])
                    draft["rooms"].append(room)
                added += 1
            if draft["start_room"] is None and draft["rooms"]:
                draft["start_room"] = draft["rooms"][0]["id"]
        if added > 0 or mode == "replace":
            self._commit(draft)
        return added, skipped

    def warnings(self) -> list[str]:
        return exit_warnings(self.world)

    def export_json(self) -> str:
        return pretty(self.world)

    def _commit(self, draft: dict) -> None:
        clean = normalize_world(draft)
        self.store.save(clean)
        self.world = clean
```

---

## FILE: `src/world_model.py`

```python
"""World JSON contract: ordinary editable data, independent of any UI."""
from __future__ import annotations

from copy import deepcopy
import json
import re

VERSION = 1
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class WorldValidationError(ValueError):
    pass


def blank_world() -> dict:
    return {"version": VERSION, "name": "Untitled World", "start_room": None, "rooms": []}


def normalize_room(value: object) -> dict:
    if not isinstance(value, dict):
        raise WorldValidationError("A room must be a JSON object")
    room = deepcopy(value)
    room_id = room.get("id")
    if not isinstance(room_id, str) or not ID_PATTERN.fullmatch(room_id):
        raise WorldValidationError("Room id is required (letters, digits, dots, underscores, hyphens)")
    name = room.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WorldValidationError(f"Room '{room_id}' needs a name")
    for key, default in (("area", "Ungrouped"), ("description", "")):
        room.setdefault(key, default)
        if not isinstance(room[key], str):
            raise WorldValidationError(f"Room '{room_id}': {key} must be text")
    room["name"] = name.strip()
    room["area"] = room["area"].strip() or "Ungrouped"
    for key in ("exits", "environment"):
        room.setdefault(key, {})
        if not isinstance(room[key], dict):
            raise WorldValidationError(f"Room '{room_id}': {key} must be an object")
    for direction, target in room["exits"].items():
        if not isinstance(direction, str) or not direction.strip() or not isinstance(target, str) or not target.strip():
            raise WorldValidationError(f"Room '{room_id}': exits must map directions to room IDs")
    for key in ("objects", "actors", "secrets"):
        room.setdefault(key, [])
        if not isinstance(room[key], list) or not all(isinstance(item, dict) for item in room[key]):
            raise WorldValidationError(f"Room '{room_id}': {key} must be an array of objects")
    return room


def parse_rooms(payload: object) -> tuple[list[dict], dict | None]:
    """Accept a room, room list, {rooms:[...]}, or a complete world document."""
    source = payload
    world_meta = None
    if isinstance(payload, dict) and "rooms" in payload:
        source = payload["rooms"]
        world_meta = {k: deepcopy(v) for k, v in payload.items() if k != "rooms"}
    elif isinstance(payload, dict) and "id" in payload:
        source = [payload]
    if isinstance(source, dict):
        source = [{**item, "id": item.get("id", key)} if isinstance(item, dict) else item
                  for key, item in source.items()]
    if not isinstance(source, list):
        raise WorldValidationError("Expected one room, a list of rooms, or an object with 'rooms'")
    rooms = [normalize_room(room) for room in source]
    ids = [room["id"] for room in rooms]
    if len(ids) != len(set(ids)):
        raise WorldValidationError("Duplicate room IDs in imported data")
    return rooms, world_meta


def normalize_world(payload: object) -> dict:
    if not isinstance(payload, dict) or "rooms" not in payload:
        raise WorldValidationError("World file must contain 'rooms'")
    rooms, meta = parse_rooms(payload)
    assert meta is not None
    if meta.get("version", VERSION) != VERSION:
        raise WorldValidationError(f"Unsupported world version (expected {VERSION})")
    name = meta.get("name", "Untitled World")
    if not isinstance(name, str) or not name.strip():
        raise WorldValidationError("World name must be nonempty text")
    start = meta.get("start_room")
    if start is not None and start not in {room["id"] for room in rooms}:
        raise WorldValidationError("start_room must reference an existing room")
    return {**meta, "version": VERSION, "name": name.strip(), "start_room": start, "rooms": rooms}


def exit_warnings(world: dict) -> list[str]:
    ids = {room["id"] for room in world["rooms"]}
    return [f"{room['id']}: {direction} points to missing room '{target}'"
            for room in world["rooms"] for direction, target in room["exits"].items()
            if target not in ids]


def pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
```

---

## FILE: `src/world_store.py`

```python
"""Single-file persistence; no UI or project-sidecar dependencies."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .world_model import blank_world, normalize_world, pretty, WorldValidationError


class WorldStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return blank_world()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorldValidationError(f"Cannot read {self.path}: {exc}") from exc
        return normalize_world(raw)

    def save(self, world: dict) -> None:
        valid = normalize_world(world)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                             suffix=".tmp", delete=False) as file:
                tmp = Path(file.name)
                file.write(pretty(valid))
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
```

---

## FILE: `tests/test_game.py`

```python
import json
from pathlib import Path
import tempfile
import unittest

from src.game import GameSession
from src.world_builder import WorldBuilder
from src.world_store import WorldStore


class GameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "world.json"
        self.store = WorldStore(self.path)
        fixture = Path(__file__).resolve().parents[1] / "examples" / "rooms.json"
        builder = WorldBuilder(self.store)
        builder.import_json(fixture.read_text(encoding="utf-8"), mode="replace")
        self.original_bytes = self.path.read_bytes()
        self.game = GameSession(self.store)

    def test_start_and_look(self):
        self.assertEqual(self.game.view().room_id, "hall")
        self.assertIn("Oak Table", self.game.execute("look"))
        self.assertIn("Rain on the roof", self.game.execute("l"))
        self.assertIn("north", self.game.execute("look"))

    def test_movement_and_enter_leave(self):
        self.assertIn("Study", self.game.execute("go north"))
        self.assertEqual(self.game.view().room_id, "study")
        self.assertIn("Inside Wardrobe", self.game.execute("enter wardrobe"))
        self.assertEqual(self.game.view().room_id, "wardrobe")
        self.assertIn("Study", self.game.execute("leave"))
        self.assertEqual(self.game.view().room_id, "study")
        self.assertIn("Entrance Hall", self.game.execute("south"))

    def test_take_drop_and_inspect(self):
        self.game.execute("north")
        self.game.execute("inside")
        self.assertIn("small iron key", self.game.execute("look at key"))
        self.assertIn("Taken: Iron Key", self.game.execute("pick up key"))
        self.assertIn("Iron Key", self.game.execute("inventory"))
        self.assertNotIn("You see:", self.game.execute("look"))
        self.game.execute("outside")
        self.assertIn("Iron Key", self.game.execute("i"))
        self.assertIn("Dropped: Iron Key", self.game.execute("drop iron key"))
        self.assertIn("Iron Key", self.game.execute("look"))
        self.assertIn("empty", self.game.execute("inventory"))

    def test_furniture_not_portable(self):
        self.assertIn("can't take", self.game.execute("take table"))
        self.assertIn("scarred oak table", self.game.execute("inspect table"))

    def test_restart_uses_saved_world_not_session_state(self):
        self.game.execute("north")
        self.game.execute("inside")
        self.game.execute("take key")
        self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.game.restart()
        self.assertEqual(self.game.view().room_id, "hall")
        self.assertEqual(self.game.inventory, [])
        self.game.execute("north")
        self.game.execute("inside")
        self.assertIn("Iron Key", self.game.look())

    def test_reloading_editor_changes(self):
        builder = WorldBuilder(self.store)
        builder.save_room({"id": "attic", "name": "Attic", "exits": {"down": "hall"}})
        hall = builder.room("hall")
        hall["exits"]["up"] = "attic"
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("Attic", self.game.execute("go up"))

    def test_unknown_exit_and_commands(self):
        self.assertIn("No exit", self.game.execute("go west"))
        self.assertIn("Unknown command", self.game.execute("dance"))
        self.assertIn("Commands:", self.game.execute("help"))
        self.assertEqual(self.game.view().room_id, "hall")

    def test_unresolved_exit_graceful(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["exits"]["east"] = "does_not_exist"
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("missing room", self.game.execute("east"))
        self.assertEqual(self.game.view().room_id, "hall")

    def test_empty_world(self):
        WorldBuilder(self.store).import_json(json.dumps({"rooms": []}), mode="replace")
        self.game.restart()
        self.assertIn("no starting room", self.game.look())
        self.assertIn("no starting room", self.game.execute("go north"))

    def test_ambiguous_object_name(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["objects"].append({"id": "dining_table", "name": "Pine Table", "kind": "furniture"})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        # An exact object ID wins over partial name matches.
        self.assertIn("scarred oak", self.game.execute("inspect table"))
        self.assertIn("Pine Table", self.game.execute("inspect pine"))
        hall = builder.room("hall")
        hall["objects"].append({"id": "desk_a", "name": "Red Desk"})
        hall["objects"].append({"id": "desk_b", "name": "Blue Desk"})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("Which one?", self.game.execute("inspect desk"))

    def test_hidden_objects_not_exposed(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["objects"].append({"id": "secret", "name": "Secret", "kind": "item", "hidden": True})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertNotIn("Secret", self.game.look())
        self.assertIn("don't see", self.game.execute("take secret"))

    def test_explicit_portability_override(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["objects"].append({"id": "boulder", "name": "Boulder", "kind": "item", "portable": False})
        hall["objects"].append({"id": "vase", "name": "Vase", "kind": "furniture", "portable": True})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("can't take", self.game.execute("take boulder"))
        self.assertIn("Taken", self.game.execute("take vase"))


if __name__ == "__main__":
    unittest.main()
```

---

## FILE: `tests/test_world_builder.py`

```python
import json
from pathlib import Path
import tempfile
import unittest

from src.world_builder import WorldBuilder
from src.world_model import WorldValidationError
from src.world_store import WorldStore


def room(room_id, exits=None):
    return {"id": room_id, "name": room_id.capitalize(), "area": "House", "exits": exits or {}}


class WorldBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data" / "world.json"
        self.builder = WorldBuilder(WorldStore(self.path))

    def test_create_and_reload(self):
        self.builder.save_room(room("hall"))
        other = WorldBuilder(WorldStore(self.path))
        self.assertEqual(other.world["start_room"], "hall")
        self.assertEqual(other.room("hall")["name"], "Hall")

    def test_import_list_and_merge_duplicates(self):
        self.builder.save_room(room("hall"))
        changed, skipped = self.builder.import_json(json.dumps([room("hall"), room("study")]))
        self.assertEqual((changed, skipped), (1, 1))
        self.assertEqual(len(self.builder.rooms()), 2)

    def test_import_replace_one_and_keep_other(self):
        self.builder.import_json(json.dumps([room("hall"), room("study")]))
        new_study = {**room("study"), "name": "Library", "secrets": [{"id": "panel"}]}
        changed, skipped = self.builder.import_json(json.dumps(new_study), mode="update")
        self.assertEqual((changed, skipped), (1, 0))
        self.assertEqual(self.builder.room("study")["name"], "Library")
        self.assertEqual(len(self.builder.rooms()), 2)
        self.assertEqual(self.builder.room("study")["secrets"][0]["id"], "panel")

    def test_import_world_and_room_map(self):
        source = {"version": 1, "name": "Example", "start_room": "room_a", "rooms": {"room_a": {"name": "A"}}}
        self.builder.import_json(json.dumps(source), mode="replace")
        self.assertEqual(self.builder.world["name"], "Example")
        self.assertEqual(self.builder.world["start_room"], "room_a")

    def test_unresolved_exits_warn_not_block(self):
        self.builder.save_room(room("hall", {"north": "study"}))
        self.assertEqual(len(self.builder.warnings()), 1)
        self.builder.save_room(room("study"))
        self.assertEqual(self.builder.warnings(), [])

    def test_delete_referenced_room_blocked(self):
        self.builder.save_room(room("hall", {"north": "study"}))
        self.builder.save_room(room("study"))
        with self.assertRaises(WorldValidationError):
            self.builder.delete_room("study")
        self.assertEqual(len(self.builder.rooms()), 2)

    def test_bad_import_does_not_change_file(self):
        self.builder.save_room(room("hall"))
        old = self.path.read_bytes()
        with self.assertRaises(WorldValidationError):
            self.builder.import_json('[{"id":"new","name":"Ok"},{"id":"new","name":"Duplicate"}]')
        self.assertEqual(self.path.read_bytes(), old)

    def test_extra_properties_survive_form_style_update(self):
        incoming = {**room("hall"), "visual_fx": {"fog": True}, "actors": [{"id": "keeper"}]}
        self.builder.save_room(incoming)
        updated = self.builder.room("hall")
        updated["description"] = "Edited"
        self.builder.save_room(updated, original_id="hall")
        self.assertEqual(self.builder.room("hall")["visual_fx"], {"fog": True})
        self.assertEqual(self.builder.room("hall")["actors"][0]["id"], "keeper")

    def test_room_id_immutable(self):
        self.builder.save_room(room("hall"))
        with self.assertRaises(WorldValidationError):
            self.builder.save_room(room("new_id"), original_id="hall")


if __name__ == "__main__":
    unittest.main()
```

---

## FILE: `.gitignore`

```text
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
```

---

## FILE: `LICENSE.md`

```markdown
MIT License

Copyright (c) 2026 Jacob Lambert

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## FILE: `README.md`

```markdown
# Adventure — World Builder + Play (v1)

A small, standalone Python text adventure: edit rooms in a **World Builder** tab and explore the same JSON world in a **Play** tab. Standard-library Python and Tkinter only; no development-sidecar, network, model, or third-party package requirements.

## Run

- Windows: double-click `run.bat` (requires Python with the `py` launcher).
- Linux/macOS: `./run.sh` (Linux may need `sudo apt install python3-tk`).
- Or: `python -m src.app` from the project root.

Your editable world definition is stored at `data/world.json`.

**Upgrading an existing installation:** use the separate *upgrade* ZIP and extract its contents into the project root. It contains only source, tests, and README; it **does not contain `data/world.json`** and will not overwrite your world. You can make a backup of your project before upgrading.

## World Builder tab

1. Click **New Room**. Enter a stable `id`, a name, an area, and a description.
2. Define exits one per line, like `north:study` or `inside:wardrobe`.
3. Enter environment values and objects. **Add Object** creates a basic object from a form. **Full Room JSON** exposes additional properties.
4. Click **Save Room**. Changes are written to `data/world.json` immediately. Select a start room and save world settings.
5. Paste generated JSON through **Import / Paste JSON**, or load a `.json` file. To explore the built-in test world, import `examples/rooms.json`.
6. **Export World JSON** saves a copy of the world.

## Play tab

Switch to **Play** to start at the world's configured start room (or its first room if a start room wasn't chosen). The left panel is the command transcript. The right panel contains your location, clickable exits, and carried inventory.

### Commands

| Command | Aliases / notes |
| --- | --- |
| `look` | `l` — describe room, visible objects/actors, environment, exits |
| `inspect <object>` | `x`, `examine`, `look at` — inspect a visible object, actor, or carried item |
| `go <exit>` | `move`, `walk`, or type an exit name like `north` directly |
| `enter <exit or room>` | Move through a connected exit, e.g. `enter wardrobe` |
| `leave` | Follow an `outside` or `out` exit if present |
| `take <item>` | `get`, `pick up` — take a portable object |
| `drop <item>` | Drop carried item in current room |
| `inventory` | `i`, `inv` — see what you're carrying |
| `help` | `?` — list commands |

Example walkthrough after importing `examples/rooms.json`:

1. `look` → Entrance Hall
2. `go north` → Study
3. `inspect wardrobe` → see wardrobe description
4. `enter wardrobe` → Inside Wardrobe
5. `take key` → Iron Key enters inventory
6. `leave` → back to Study, carrying the key

**Reload World / Restart** reads the latest saved `data/world.json` and starts a new session. **Switching back to the Play tab also restarts play**, to make newly saved edits immediately testable. Unsaved changes still sitting in the builder form are not included: click **Save Room** or **Save World Settings** first.

Gameplay state (the player's current room and inventory, plus moved objects) is **in-memory only**. The world builder's JSON is never changed by playing, and there are no saved games yet.

## World JSON contract

Worlds have `version: 1`, `name`, `start_room`, and `rooms` (array). Each room has:

- Required: `id` (stable unique room identifier), `name`
- Common: `area`, `description`, `exits` (`exit-name` → destination room ID), `environment` (object), `objects`/`actors`/`secrets` (arrays of objects)
- Optional extra properties are preserved during editor saves/imports; runtime behavior is implemented only for the subset listed below.

For game objects, use `id`, `name`, `description`, `kind`, and optionally `portable: true/false` or `takeable: true/false`. Only `kind: "item"` is portable by default; other kinds like furniture stay in the room unless explicitly marked portable. An object with `hidden: true` is excluded from ordinary Look, Inspect, and Take. **There is no reveal-secrets command yet.**

Enterable interiors are regular rooms with named exits (`inside:wardrobe`, `outside:study`). The `interior_of` field is retained as metadata; the actual movement always follows an exit. Environment values are displayed as text, not rendered as sound/light/weather effects.

Import accepts an individual room, list of rooms, or a world document containing `rooms` as a list or object keyed by room ID. Options:

- **Add new** — skip already-present IDs.
- **Update matching** — replace matching rooms and add new ones.
- **Replace whole world** — replace rooms and world metadata, after confirmation.

Room IDs cannot be renamed through the form (to protect exit references). Deleting a referenced room is blocked. Unresolved exits generate editor warnings and, in Play, a friendly missing-room message.

## Architecture

```text
src/app.py                    thin app shell; Tk root and two surface tabs
src/surfaces/builder.py       editor surface / forms
src/world_builder.py         editor-domain orchestrator
src/surfaces/game.py          play surface / transcript and command input
src/game.py                   game-domain orchestrator / parser / session state
src/world_model.py           shared world JSON contract and validation
src/world_store.py           shared JSON file manager (atomic writes)
```

Neither surface calls the other. The editor writes the world JSON; a game session loads it and owns a separate mutable copy. Future surfaces can share `world_model` and `world_store` without reusing either UI.

## Deliberately not included yet

No action-rule system, `use`/`open` behavior, container traversal, secret discovery, dialogue, NPC intelligence, combat, audio playback, persistent save games, networking or AI inference. Objects, actors, secrets, and extra metadata can already be authored through Full Room JSON and imports; runtime support can be added one behavior at a time.

Run tests: `python -m unittest discover -s tests -v`.
```

---

## FILE: `run.bat`

```bat
@echo off
cd /d "%~dp0"
py -m src.app
if errorlevel 1 pause
```

---

## FILE: `run.sh`

```bash
#!/usr/bin/env sh
cd "$(dirname "$0")"
python3 -m src.app
```
