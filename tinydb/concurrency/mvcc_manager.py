"""Multi-Version Concurrency Control: page version chain and snapshot reads."""
import time
from dataclasses import dataclass, field


@dataclass
class PageVersion:
    """A single version of a page in the MVCC version chain."""
    data: bytes
    created_txn: int
    deleted_txn: int | None = None
    next: "PageVersion | None" = None


@dataclass
class Snapshot:
    """A point-in-time snapshot for MVCC reads."""
    active_txns: set[int]
    timestamp: float = field(default_factory=time.time)


class MVCCManager:
    """Manages page version chains for MVCC snapshot reads."""

    def __init__(self):
        # page_id -> PageVersion (head of chain, newest first)
        self._versions: dict[int, PageVersion] = {}

    def create_version(self, page_id: int, data: bytes, txn_id: int) -> PageVersion:
        """Create a new version of a page. Inserts at head of chain (descending txn_id)."""
        new_version = PageVersion(data=data, created_txn=txn_id)
        if page_id in self._versions:
            new_version.next = self._versions[page_id]
        self._versions[page_id] = new_version
        return new_version

    def get_visible_version(self, page_id: int, snapshot: Snapshot) -> bytes | None:
        """Find the visible version of a page for the given snapshot."""
        if page_id not in self._versions:
            return None
        current = self._versions[page_id]
        while current is not None:
            if self._is_visible(current, snapshot):
                return current.data
            current = current.next
        return None

    def mark_deleted(self, page_id: int, version_txn_id: int, txn_id: int) -> bool:
        """Mark a version as deleted by setting deleted_txn."""
        current = self._versions.get(page_id)
        while current is not None:
            if current.created_txn == version_txn_id:
                current.deleted_txn = txn_id
                return True
            current = current.next
        return False

    def gc(self, active_txns: set[int]) -> int:
        """Garbage collect versions not visible to any active transaction. Returns count freed."""
        freed = 0
        for page_id in list(self._versions.keys()):
            current = self._versions.get(page_id)
            prev = None
            while current is not None:
                can_gc = (
                    current.created_txn not in active_txns
                    and self._no_active_txn_can_see(current, active_txns)
                )
                if can_gc:
                    if prev is None:
                        self._versions[page_id] = current.next
                        if current.next is None:
                            del self._versions[page_id]
                    else:
                        prev.next = current.next
                    freed += 1
                    current = current.next if prev is None else prev.next
                else:
                    prev = current
                    current = current.next
        return freed

    def _is_visible(self, version: PageVersion, snapshot: Snapshot) -> bool:
        """Visibility rule: created_txn in snapshot AND deleted_txn NOT in snapshot."""
        if version.created_txn not in snapshot.active_txns:
            return False
        if version.deleted_txn is not None and version.deleted_txn in snapshot.active_txns:
            return False
        return True

    def _no_active_txn_can_see(self, version: PageVersion, active_txns: set[int]) -> bool:
        """Check if no active transaction could see this version.

        A version can be GC'd only if it was created by a transaction older
        than all currently active transactions (i.e., no active or future
        transaction could ever need it).
        """
        if not active_txns:
            return True
        return version.created_txn < min(active_txns)
