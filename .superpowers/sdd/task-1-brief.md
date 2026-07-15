# Task 1: Project Skeleton & Constants

**Goal:** Initialize the tinydb package structure, exception hierarchy, and pytest configuration.

## Files to Create

1. `tinydb/__init__.py` — Package docstring
2. `tinydb/exceptions.py` — StorageError hierarchy
3. `tinydb/constants.py` — Page size, magic bytes, header size constants
4. `tests/__init__.py` — Empty init
5. `tests/conftest.py` — Shared fixtures
6. `pyproject.toml` — Build config + pytest settings

## Key Requirements (from Global Constraints)

- Python 3.10+ 标准库，零外部依赖
- 页大小固定 4096 bytes
- 文件 magic bytes: `b"TINYDB\0"`
- BufferPool 默认容量: 100 pages
- NULL 位图: 每列 1 bit，`ceil(n/8)` bytes
- 行编码: INTEGER=int64(8B), FLOAT=double(8B), BOOLEAN=1B, TEXT=4B length + UTF-8

## Global Constraints (verbatim)

- 所有错误通过异常体系处理（StorageError 继承树）
- 不支持并发访问
- 教学优先: 代码清晰可读，关键概念有注释

## Task 1 is NOT TDD — manual verification only

This is a scaffolding task. Skip TDD, but still verify manually:
- `python -c "import tinydb"` succeeds
- `pytest --collect-only` discovers tests directory
