# database/base.py
import asyncio

import aiosqlite


class _CursorContext:
    """Mirrors aiosqlite's Result: usable as `await conn.execute(...)` and
    `async with conn.execute(...) as cursor:` (closing the cursor on exit)."""

    def __init__(self, coro):
        self._coro = coro
        self._cursor = None

    def __await__(self):
        return self._coro.__await__()

    async def __aenter__(self):
        self._cursor = await self._coro
        return self._cursor

    async def __aexit__(self, exc_type, exc, tb):
        if self._cursor is not None:
            await self._cursor.close()


class GuardedConnection:
    """Wraps the shared aiosqlite connection to support managed transactions.

    Repositories commit inline after every write. Inside a managed
    transaction (DatabaseManager.transaction), those inline commits and
    rollbacks become no-ops for the owning task, so all writes in the block
    land in one implicit SQLite transaction that the manager commits or
    rolls back at exit. While a transaction is in flight, statements from
    other tasks wait for it to finish so their writes can never be swept
    into (or lost with) someone else's rollback.
    """

    _WRAPPER_ATTRS = frozenset({"_real", "_tx_lock", "_tx_owner"})

    def __init__(self, real: aiosqlite.Connection):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_tx_lock", asyncio.Lock())
        object.__setattr__(self, "_tx_owner", None)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        if name in self._WRAPPER_ATTRS:
            object.__setattr__(self, name, value)
        else:
            setattr(self._real, name, value)

    def _owns_transaction(self) -> bool:
        return self._tx_owner is not None and self._tx_owner is asyncio.current_task()

    async def _wait_for_foreign_tx(self) -> None:
        if self._tx_owner is not None and not self._owns_transaction():
            async with self._tx_lock:
                pass

    async def _guarded(self, method, *args, **kwargs):
        await self._wait_for_foreign_tx()
        return await method(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return _CursorContext(self._guarded(self._real.execute, *args, **kwargs))

    def executemany(self, *args, **kwargs):
        return _CursorContext(self._guarded(self._real.executemany, *args, **kwargs))

    def executescript(self, *args, **kwargs):
        return _CursorContext(self._guarded(self._real.executescript, *args, **kwargs))

    async def commit(self):
        if self._owns_transaction():
            return  # deferred to the managed transaction's exit
        await self._wait_for_foreign_tx()
        await self._real.commit()

    async def rollback(self):
        if self._owns_transaction():
            # A nested rollback (e.g. fuse_companions' internal handler) must
            # not tear down the outer transaction; the exception it raises
            # propagates and the transaction context rolls back once.
            return
        await self._wait_for_foreign_tx()
        await self._real.rollback()


class BaseRepository:
    def __init__(self, connection):
        self.connection = connection

    async def commit(self):
        await self.connection.commit()
