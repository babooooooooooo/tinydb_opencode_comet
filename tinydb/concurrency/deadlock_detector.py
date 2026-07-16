"""Deadlock detection using wait-for graph and cycle detection."""
import threading
from collections import defaultdict


class DeadlockDetector:
    """Detects deadlocks via wait-for graph cycle detection."""

    def __init__(self):
        self._lock = threading.Lock()
        # txn_id -> set of txn_ids it waits for
        self._wait_for: dict[int, set[int]] = defaultdict(set)

    def add_wait_edge(self, waiter_txn: int, holder_txn: int) -> None:
        """Add an edge: waiter_txn waits for holder_txn."""
        with self._lock:
            self._wait_for[waiter_txn].add(holder_txn)

    def remove_wait_edge(self, waiter_txn: int, holder_txn: int) -> None:
        """Remove an edge: waiter_txn no longer waits for holder_txn."""
        with self._lock:
            if waiter_txn in self._wait_for:
                self._wait_for[waiter_txn].discard(holder_txn)
                if not self._wait_for[waiter_txn]:
                    del self._wait_for[waiter_txn]

    def detect_cycle(self) -> list[int] | None:
        """Detect a cycle in the wait-for graph using DFS. Returns the cycle or None."""
        with self._lock:
            WHITE, GRAY, BLACK = 0, 1, 2
            color: dict[int, int] = defaultdict(int)
            parent: dict[int, int | None] = {}

            def dfs(u: int) -> list[int] | None:
                color[u] = GRAY
                for v in self._wait_for.get(u, set()):
                    if color[v] == GRAY:
                        # Found cycle — reconstruct it
                        cycle = [v, u]
                        node = u
                        while parent.get(node) is not None and parent[node] != v:
                            node = parent[node]  # type: ignore
                            cycle.append(node)
                        cycle.reverse()
                        return cycle
                    if color[v] == WHITE:
                        parent[v] = u
                        result = dfs(v)
                        if result is not None:
                            return result
                color[u] = BLACK
                return None

            for node in list(self._wait_for.keys()):
                if color[node] == WHITE:
                    result = dfs(node)
                    if result is not None:
                        return result
            return None

    def select_victim(self, cycle: list[int]) -> int:
        """Select the youngest transaction (highest txn_id) as victim."""
        return max(cycle)

    def clear_txn(self, txn_id: int) -> None:
        """Remove all edges involving a transaction."""
        with self._lock:
            # Remove outgoing edges
            if txn_id in self._wait_for:
                del self._wait_for[txn_id]
            # Remove incoming edges
            for waiter in list(self._wait_for.keys()):
                self._wait_for[waiter].discard(txn_id)
                if not self._wait_for[waiter]:
                    del self._wait_for[waiter]
