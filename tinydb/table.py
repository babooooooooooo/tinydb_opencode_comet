# tinydb/table.py
"""Table-level CRUD API.

INSERT: find slot with enough space → serialize row → write to page
SCAN:   traverse page chain → pin each page → read all rows → unpin
GET:    locate page + slot → deserialize row
DELETE: mark slot as deleted
UPDATE: in-place update if space allows, else delete + re-insert
"""
import struct
from tinydb.types import ColumnDef, convert_value
from tinydb.row_format import serialize_row, deserialize_row
from tinydb.page import (
    PageType, RowId, create_empty_page,
    insert_row_into_page, get_row_from_page, delete_row_from_page,
    parse_page_header, pack_page_header,
)
from tinydb.concurrency.lock_manager import LockMode


class Table:
    """Provides row-level CRUD operations on a table's data pages."""

    def __init__(self, table_name: str, columns: list[ColumnDef], root_page: int, primary_key: str = ""):
        self.table_name = table_name
        self.columns = columns
        self.root_page = root_page
        self.primary_key = primary_key

    def insert(self, buffer_pool, row: list, ctx=None) -> RowId:
        """Insert a row. Returns the RowId."""
        # Validate and convert values
        converted = []
        for val, col in zip(row, self.columns):
            converted.append(convert_value(val, col))

        serialized = serialize_row(converted, self.columns)

        # Acquire exclusive lock on root page to serialize writes
        if ctx is not None:
            self._acquire_lock(ctx, self.root_page, LockMode.EXCLUSIVE)

        # Traverse page chain to find space
        page_id = self.root_page
        data_page_id = None
        last_page_id = None

        while page_id != 0:
            page_data = buffer_pool.get_page(page_id)
            header = parse_page_header(page_data)
            if header["page_type"] != PageType.DATA:
                break
            last_page_id = page_id
            if get_free_space_raw(page_data) >= len(serialized) + 4:  # 4 = slot entry
                data_page_id = page_id
                break
            page_id = header["next_page_id"]

        if data_page_id is None:
            # No room: allocate new page and append to chain
            new_page_id = buffer_pool._fm.alloc_page()

            # Update previous page's next_page_id
            if last_page_id is not None:
                prev_data = bytearray(buffer_pool.get_page(last_page_id))
                prev_header = parse_page_header(bytes(prev_data))
                new_header = pack_page_header(
                    page_id=prev_header["page_id"],
                    page_type=prev_header["page_type"],
                    slot_count=prev_header["slot_count"],
                    free_space=prev_header["free_space"],
                    free_offset=prev_header["free_offset"],
                    next_page_id=new_page_id,
                    flags=prev_header["flags"],
                )
                prev_data[:len(new_header)] = new_header
                buffer_pool.set_page_data(last_page_id, bytes(prev_data))

            # Create new empty data page
            new_page = create_empty_page(new_page_id, PageType.DATA)
            buffer_pool._fm.write_page(new_page_id, new_page.data)
            data_page_id = new_page_id

        # Insert the row
        page_data = bytearray(buffer_pool.get_page(data_page_id))
        page = _page_from_data(data_page_id, page_data)
        slot_idx = insert_row_into_page(page, serialized)

        # Mark dirty in buffer pool
        buffer_pool.set_page_data(data_page_id, page.data)

        return RowId(page_id=data_page_id, slot_index=slot_idx)

    def scan(self, buffer_pool, ctx=None):
        """Yield (RowId, row_values) tuples for all rows in the table."""
        page_id = self.root_page
        txn_id = ctx.txn_id if ctx else None

        # Acquire shared lock on root page for duration of scan to prevent
        # concurrent page chain modifications.
        if txn_id is not None:
            buffer_pool.pin(page_id, txn_id=txn_id, mode=LockMode.SHARED)

        try:
            while page_id != 0:
                snapshot = ctx.snapshot if ctx else None
                page_data = buffer_pool.get_page(page_id, txn_id=txn_id, snapshot=snapshot)
                header = parse_page_header(page_data)
                if header["page_type"] != PageType.DATA:
                    break

                # Read all valid rows from this page
                page = _page_from_data(page_id, page_data)
                for slot_idx in range(header["slot_count"]):
                    row_data = get_row_from_page(page, slot_idx)
                    if row_data is None:
                        continue
                    values = deserialize_row(row_data, self.columns)
                    if values is not None:
                        yield RowId(page_id=page_id, slot_index=slot_idx), values

                page_id = header["next_page_id"]
        finally:
            if txn_id is not None:
                buffer_pool.unpin(self.root_page, txn_id=txn_id)

    def get(self, buffer_pool, row_id: RowId) -> list | None:
        """Get a single row by RowId."""
        page_data = buffer_pool.get_page(row_id.page_id)
        page = _page_from_data(row_id.page_id, page_data)
        row_data = get_row_from_page(page, row_id.slot_index)
        if row_data is None:
            return None
        return deserialize_row(row_data, self.columns)

    def delete(self, buffer_pool, row_id: RowId, ctx=None) -> None:
        """Delete a row by RowId."""
        if ctx is not None:
            self._acquire_lock(ctx, row_id.page_id, LockMode.EXCLUSIVE)

        page_data = bytearray(buffer_pool.get_page(row_id.page_id))
        page = _page_from_data(row_id.page_id, page_data)
        delete_row_from_page(page, row_id.slot_index)

        # Mark dirty
        buffer_pool.set_page_data(row_id.page_id, page.data)

    def update(self, buffer_pool, row_id: RowId, new_row: list, ctx=None) -> RowId:
        """更新行。空间足够时原地更新并保留原 RowId，否则删除旧行后重新插入并返回新 RowId。"""
        if ctx is not None:
            self._acquire_lock(ctx, row_id.page_id, LockMode.EXCLUSIVE)

        # Validate and convert
        converted = []
        for val, col in zip(new_row, self.columns):
            converted.append(convert_value(val, col))

        serialized = serialize_row(converted, self.columns)

        page_data = bytearray(buffer_pool.get_page(row_id.page_id))
        header = parse_page_header(bytes(page_data))

        # Read old slot info for space reclamation
        slot_off = 32 + row_id.slot_index * 4
        old_offset, old_length = struct.unpack_from("<HH", page_data, slot_off)

        # Calculate available space: current free_space + old row length
        avail = header["free_space"] + old_length

        if len(serialized) <= avail:
            # Enough space: write new data and update slot in-place
            # Reclaim old slot space first
            new_free_offset = header["free_offset"]
            new_free_space = header["free_space"] + old_length

            # Write serialized data at new_free_offset - len(serialized)
            write_offset = new_free_offset - len(serialized)
            page_data[write_offset:write_offset + len(serialized)] = serialized

            # Update the slot to point to new location
            struct.pack_into("<HH", page_data, slot_off, write_offset, len(serialized))

            # Update page header
            new_header = pack_page_header(
                page_id=header["page_id"],
                page_type=header["page_type"],
                slot_count=header["slot_count"],
                free_space=new_free_space - len(serialized) - 0,  # no new slot added
                free_offset=write_offset,
                next_page_id=header["next_page_id"],
                flags=header["flags"],
            )
            page_data[:32] = new_header
            buffer_pool.set_page_data(row_id.page_id, bytes(page_data))
            return row_id
        else:
            # Not enough space: delete old + insert new on same page chain
            # Mark old slot deleted
            struct.pack_into("<HH", page_data, slot_off, 0, 0)
            buffer_pool.set_page_data(row_id.page_id, bytes(page_data))
            # Re-insert using insert logic
            return self.insert(buffer_pool, new_row, ctx=ctx)

    @staticmethod
    def _acquire_lock(ctx, page_id: int, mode) -> None:
        """Acquire a lock via the lock manager, raising on timeout."""
        acquired = ctx.lock_mgr.acquire(ctx.txn_id, page_id, mode)
        if not acquired:
            from tinydb.transaction.txn_manager import TransactionError
            raise TransactionError(f"Lock timeout: txn {ctx.txn_id} waiting for page {page_id}")


def _page_from_data(page_id: int, data: bytes):
    """Create a Page object from raw data for use with page operations."""
    from tinydb.page import Page
    header = parse_page_header(data)
    return Page(
        page_id=page_id,
        page_type=header["page_type"],
        data=data,
        dirty=False,
    )


def get_free_space_raw(data: bytes) -> int:
    """Get free space from raw page data."""
    header = parse_page_header(data)
    return header["free_space"]
