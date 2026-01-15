"""Memory storage implementations for persistent and temporary storage."""

from abc import ABC
from abc import abstractmethod
import asyncio
from datetime import datetime
from datetime import timedelta
import json
import os
from typing import Any, Dict, List, Optional

import aiofiles

from src.memory.types import Memory
from src.memory.types import MemoryType

# File suffixes
TEMP_FILE_SUFFIX = ".tmp"
BACKUP_FILE_SUFFIX = ".backup"

# Cleanup thresholds
LOW_IMPORTANCE_THRESHOLD = 0.5

# Date format for backup files
BACKUP_DATE_FORMAT = "%Y%m%d_%H%M%S"


class MemoryStorage(ABC):
    """Abstract base class for memory storage backends.

    Defines the interface for storage implementations that persist
    and retrieve memory objects.
    """

    @abstractmethod
    async def store(self, memory: Memory) -> str:
        """Store a memory and return its ID.

        Args:
            memory: Memory instance to store.

        Returns:
            ID of the stored memory.
        """
        raise NotImplementedError

    @abstractmethod
    async def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            Memory instance or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: Dict[str, Any]) -> List[Memory]:
        """Search memories based on criteria.

        Args:
            query: Search criteria dictionary.

        Returns:
            List of matching memories.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            True if deleted, False if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_all(self, memory_type: Optional[MemoryType] = None) -> List[Memory]:
        """List all memories, optionally filtered by type.

        Args:
            memory_type: Optional filter by memory type.

        Returns:
            List of memories sorted by timestamp descending.
        """
        raise NotImplementedError


class LocalMemoryStorage(MemoryStorage):
    """Local file-based memory storage with atomic writes.

    Stores memories in a JSON file on disk. Uses atomic writes
    (write to temp file, then rename) to prevent corruption.

    Attributes:
        storage_path: Path to the JSON storage file.
        _lock: Async lock for disk operations.
        _cache: In-memory cache of loaded memories.
    """

    def __init__(self, storage_path: str = "memory_store.json") -> None:
        self.storage_path = storage_path
        self._lock = asyncio.Lock()
        self._cache: Dict[str, Memory] = {}

    async def _load_from_disk(self) -> Dict[str, Any]:
        """Load memories from disk.

        Returns:
            Dictionary of memory data keyed by ID.
        """
        if not os.path.exists(self.storage_path):
            return {}

        try:
            async with aiofiles.open(self.storage_path, "r") as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except Exception:
            # Handle corrupted file by backing up and starting fresh
            backup_path = self._create_backup_path()
            os.rename(self.storage_path, backup_path)
            return {}

    def _create_backup_path(self) -> str:
        """Create a backup file path with timestamp.

        Returns:
            Backup file path string.
        """
        timestamp = datetime.now().strftime(BACKUP_DATE_FORMAT)
        return f"{self.storage_path}.backup.{timestamp}"

    async def _save_to_disk(self, data: Dict[str, Any]) -> None:
        """Save memories to disk atomically.

        Args:
            data: Dictionary of memory data to save.
        """
        async with self._lock:
            temp_path = self.storage_path + TEMP_FILE_SUFFIX
            async with aiofiles.open(temp_path, "w") as f:
                await f.write(json.dumps(data, default=str, indent=2))

            # Atomic rename with backup
            if os.path.exists(self.storage_path):
                os.rename(self.storage_path, self.storage_path + BACKUP_FILE_SUFFIX)
            os.rename(temp_path, self.storage_path)

    async def store(self, memory: Memory) -> str:
        """Store a memory and return its ID.

        Args:
            memory: Memory instance to store.

        Returns:
            ID of the stored memory.
        """
        memories = await self._load_from_disk()

        memory_dict = memory.model_dump()
        memories[memory.id] = memory_dict

        await self._save_to_disk(memories)
        self._cache[memory.id] = memory

        return memory.id

    async def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            Memory instance or None if not found.
        """
        if memory_id in self._cache:
            return self._cache[memory_id]

        memories = await self._load_from_disk()
        if memory_id not in memories:
            return None

        memory_data = memories[memory_id]
        memory = Memory(**memory_data)
        self._cache[memory_id] = memory

        return memory

    async def search(self, query: Dict[str, Any]) -> List[Memory]:
        """Search memories based on criteria.

        Args:
            query: Dictionary of search criteria.

        Returns:
            List of matching memories.
        """
        memories = await self._load_from_disk()
        results = []

        for memory_data in memories.values():
            memory = Memory(**memory_data)
            if self._matches_query(memory, query):
                results.append(memory)

        return results

    def _matches_query(self, memory: Memory, query: Dict[str, Any]) -> bool:
        """Check if a memory matches the search query.

        Args:
            memory: Memory to check.
            query: Search criteria.

        Returns:
            True if memory matches all criteria.
        """
        # Check type filter
        if "type" in query and memory.type != query["type"]:
            return False

        # Check tags filter
        if "tags" in query:
            query_tags = set(query["tags"])
            memory_tags = set(memory.tags)
            if not query_tags.issubset(memory_tags):
                return False

        # Check content search
        if "content_contains" in query:
            search_term = query["content_contains"].lower()
            if search_term not in str(memory.content).lower():
                return False

        # Check time range
        if "after" in query and memory.timestamp < query["after"]:
            return False
        if "before" in query and memory.timestamp > query["before"]:
            return False

        # Check importance threshold
        if "min_importance" in query and memory.importance < query["min_importance"]:
            return False

        return True

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            True if deleted, False if not found.
        """
        memories = await self._load_from_disk()

        if memory_id in memories:
            del memories[memory_id]
            await self._save_to_disk(memories)
            if memory_id in self._cache:
                del self._cache[memory_id]
            return True
        return False

    async def list_all(self, memory_type: Optional[MemoryType] = None) -> List[Memory]:
        """List all memories, optionally filtered by type.

        Args:
            memory_type: Optional filter by memory type.

        Returns:
            List of memories sorted by timestamp descending.
        """
        memories = await self._load_from_disk()
        results = []

        for memory_data in memories.values():
            memory = Memory(**memory_data)
            if memory_type is None or memory.type == memory_type:
                results.append(memory)

        return sorted(results, key=lambda m: m.timestamp, reverse=True)

    async def cleanup_old_memories(self, max_age_days: int = 30) -> int:
        """Clean up old memories beyond max_age_days.

        Only removes memories with low importance (< 0.5).

        Args:
            max_age_days: Maximum age in days.

        Returns:
            Number of memories deleted.
        """
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        memories = await self._load_from_disk()

        deleted_count = 0
        for memory_id, memory_data in memories.items():
            memory = Memory(**memory_data)
            if (memory.timestamp < cutoff_date
                    and memory.importance < LOW_IMPORTANCE_THRESHOLD):
                if await self.delete(memory_id):
                    deleted_count += 1

        return deleted_count


class InMemoryStorage(MemoryStorage):
    """In-memory storage for testing and temporary use.

    Simple in-memory dictionary-backed storage. Data is lost
    when the instance is destroyed.

    Attributes:
        _storage: Dictionary mapping memory IDs to Memory instances.
    """

    def __init__(self) -> None:
        self._storage: Dict[str, Memory] = {}

    async def store(self, memory: Memory) -> str:
        """Store a memory.

        Args:
            memory: Memory instance to store.

        Returns:
            ID of the stored memory.
        """
        self._storage[memory.id] = memory
        return memory.id

    async def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            Memory instance or None if not found.
        """
        return self._storage.get(memory_id)

    async def search(self, query: Dict[str, Any]) -> List[Memory]:
        """Search memories based on criteria.

        Args:
            query: Dictionary of search criteria.

        Returns:
            List of matching memories.
        """
        results = []
        for memory in self._storage.values():
            if "type" in query and memory.type != query["type"]:
                continue
            results.append(memory)
        return results

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            True if deleted, False if not found.
        """
        if memory_id in self._storage:
            del self._storage[memory_id]
            return True
        return False

    async def list_all(self, memory_type: Optional[MemoryType] = None) -> List[Memory]:
        """List all memories, optionally filtered by type.

        Args:
            memory_type: Optional filter by memory type.

        Returns:
            List of memories sorted by timestamp descending.
        """
        memories = list(self._storage.values())
        if memory_type:
            memories = [m for m in memories if m.type == memory_type]
        return sorted(memories, key=lambda m: m.timestamp, reverse=True)
