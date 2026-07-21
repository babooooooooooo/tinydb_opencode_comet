"""Tests for tinydb.concurrency.deadlock_detector module."""
from tinydb.concurrency.deadlock_detector import DeadlockDetector


class TestDeadlockDetector:
    def setup_method(self):
        self.dd = DeadlockDetector()

    def test_no_cycle_empty(self):
        assert self.dd.detect_cycle() is None

    def test_no_cycle_single_edge(self):
        self.dd.add_wait_edge(waiter_txn=1, holder_txn=2)
        assert self.dd.detect_cycle() is None

    def test_detect_simple_cycle(self):
        """1→2→3→1 forms a cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        cycle = self.dd.detect_cycle()
        assert cycle is not None
        assert len(cycle) >= 3

    def test_detect_no_cycle_dag(self):
        """1→2→3 is a DAG, no cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        assert self.dd.detect_cycle() is None

    def test_select_victim_youngest(self):
        """Victim is the youngest (highest txn_id) in the cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        cycle = self.dd.detect_cycle()
        victim = self.dd.select_victim(cycle)
        assert victim == 3  # highest txn_id

    def test_remove_edge_breaks_cycle(self):
        """Removing an edge breaks the cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        assert self.dd.detect_cycle() is not None
        self.dd.remove_wait_edge(3, 1)
        assert self.dd.detect_cycle() is None

    def test_clear_txn(self):
        """Clearing a txn removes all its edges."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        self.dd.clear_txn(1)
        assert self.dd.detect_cycle() is None

    def test_self_loop_detected(self):
        """A txn waiting on itself is a cycle."""
        self.dd.add_wait_edge(1, 1)
        cycle = self.dd.detect_cycle()
        assert cycle is not None
