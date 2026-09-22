"""Atomic-write / locked-rewrite helpers (Phase 0 concurrency-safety fixes)."""

from orchestrator.brand_state import atomic_write, locked_rewrite


def test_atomic_write_leaves_no_tmp_file_and_the_final_content(tmp_path):
    path = tmp_path / "sub" / "file.md"
    atomic_write(path, "hello\n")
    assert path.read_text() == "hello\n"
    assert not path.with_name("file.md.tmp").exists()
    atomic_write(path, "overwritten\n")  # replaces cleanly
    assert path.read_text() == "overwritten\n"


def test_locked_rewrite_applies_the_mutation_and_leaves_no_lock_content(tmp_path):
    path = tmp_path / "shared" / "ledger.md"

    def add_line(text: str) -> str:
        return text + "one\n"

    locked_rewrite(path, add_line)
    locked_rewrite(path, add_line)
    assert path.read_text() == "one\none\n"


def test_locked_rewrite_skips_the_write_when_mutate_returns_none(tmp_path):
    path = tmp_path / "ledger.md"
    path.write_text("already there\n")
    locked_rewrite(path, lambda text: None)  # e.g. header already present — idempotent on resume
    assert path.read_text() == "already there\n"


def test_locked_rewrite_serialises_concurrent_writers(tmp_path):
    """Two threads racing append_ledger-style writes must not lose either one's update."""
    import threading

    path = tmp_path / "ledger.md"

    def append(tag: str) -> None:
        locked_rewrite(path, lambda text: text + f"{tag}\n")

    threads = [threading.Thread(target=append, args=(f"writer-{i}",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = path.read_text().splitlines()
    assert len(lines) == 20  # every writer's line survived; none were lost to a lost-update race
    assert {f"writer-{i}" for i in range(20)} == set(lines)
