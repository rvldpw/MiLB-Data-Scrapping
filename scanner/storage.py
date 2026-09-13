"""Read a pinned snapshot and commit data plus progress together."""
from pathlib import Path, PurePosixPath
import json
import os

from huggingface_hub import HfApi, CommitOperationAdd, hf_hub_download
from huggingface_hub.errors import RemoteEntryNotFoundError


def safe_path(path):
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or not parsed.parts or "\\" in path:
        raise ValueError(f"Unsafe dataset path: {path}")
    return str(parsed)


class LocalStore:
    """Single-writer local preview. Data precedes progress for retry safety."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def read(self, path):
        file = self.root / safe_path(path)
        return file.read_bytes() if file.exists() else None

    def commit(self, files, message):
        for path in sorted(files, key=lambda p: (p.startswith("state/"), p == "state/index.json", p)):
            file = self.root / safe_path(path)
            file.parent.mkdir(parents=True, exist_ok=True)
            temporary = file.with_suffix(file.suffix + ".tmp")
            temporary.write_bytes(files[path])
            os.replace(temporary, file)


class HubStore:
    def __init__(self, repo_id, token, private=True):
        if not repo_id or not token:
            raise ValueError("Set HF_REPO_ID and HF_TOKEN, or use --local-dir for a local run")
        if len(repo_id.split("/")) != 2:
            raise ValueError("HF_REPO_ID must be owner/dataset-name")
        self.repo_id, self.token = repo_id, token
        self.api = HfApi(token=token)
        self.api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
        self.revision = self.api.repo_info(repo_id=repo_id, repo_type="dataset").sha
        self.cache = {}

    def read(self, path):
        path = safe_path(path)
        if path not in self.cache:
            try:
                downloaded = hf_hub_download(repo_id=self.repo_id, filename=path, repo_type="dataset",
                                             revision=self.revision, token=self.token)
                self.cache[path] = Path(downloaded).read_bytes()
            except RemoteEntryNotFoundError:
                self.cache[path] = None
        return self.cache[path]

    def commit(self, files, message):
        operations = [CommitOperationAdd(path_in_repo=safe_path(path), path_or_fileobj=data)
                      for path, data in sorted(files.items())]
        result = self.api.create_commit(repo_id=self.repo_id, repo_type="dataset", revision="main",
                                        parent_commit=self.revision, operations=operations,
                                        commit_message=message)
        self.revision = result.oid
        self.cache.update(files)


def read_json(store, path, default):
    raw = store.read(path)
    if raw is None:
        return default
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
