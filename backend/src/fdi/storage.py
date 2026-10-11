"""Private original-file storage. Keys are random UUIDs, never user-supplied paths."""
import os
from pathlib import Path
from uuid import UUID, uuid4
from fdi.db.config import ROOT

DEFAULT_ROOT = ROOT / 'storage/documents'


class LocalStorage:
    """Single-host volume; replaceable by private object storage behind the same methods."""

    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root)

    def path(self, storage_key):
        return self.root / f'{UUID(str(storage_key))}.pdf'

    def put(self, data):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = uuid4()
        fd = os.open(self.path(key), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        return key
