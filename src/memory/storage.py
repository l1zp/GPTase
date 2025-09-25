"""
Memory storage implementations for persistent and temporary storage
"""

import json
import os
import asyncio
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import aiofiles
from src.memory.types import Memory, MemoryType

class MemoryStorage(ABC):
    """Abstract base class for memory storage backends."""
    
    @abstractmethod
    async def store(self, memory: Memory) -> str:
        """Store a memory and return its ID."""
        pass
        
    @abstractmethod
    async def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID."""
        pass
        
    @abstractmethod
    async def search(self, query: Dict[str, Any]) -> List[Memory]:
        """Search memories based on criteria."""
        pass
        
    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        pass
        
    @abstractmethod
    async def list_all(self, memory_type: MemoryType = None) -> List[Memory]:
        """List all memories, optionally filtered by type."""
        pass

class LocalMemoryStorage(MemoryStorage):
    """Local file-based memory storage."""
    
    def __init__(self, storage_path: str = "memory_store.json"):
        self.storage_path = storage_path
        self._lock = asyncio.Lock()
        self._cache: Dict[str, Memory] = {}
        
    async def _load_from_disk(self) -> Dict[str, Any]:
        """Load memories from disk."""
        if not os.path.exists(self.storage_path):
            return {}
            
        try:
            async with aiofiles.open(self.storage_path, 'r') as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except Exception as e:
            # Handle corrupted file
            backup_path = f"{self.storage_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(self.storage_path, backup_path)
            return {}
            
    async def _save_to_disk(self, data: Dict[str, Any]) -> None:
        """Save memories to disk."""
        async with self._lock:
            temp_path = f"{self.storage_path}.tmp"
            async with aiofiles.open(temp_path, 'w') as f:
                await f.write(json.dumps(data, default=str, indent=2))
            
            # Atomic rename
            if os.path.exists(self.storage_path):
                os.rename(self.storage_path, f"{self.storage_path}.backup")
            os.rename(temp_path, self.storage_path)
            
    async def store(self, memory: Memory) -> str:
        """Store a memory and return its ID."""
        memories = await self._load_from_disk()
        
        memory_dict = memory.model_dump()
        memories[memory.id] = memory_dict
        
        await self._save_to_disk(memories)
        self._cache[memory.id] = memory
        
        return memory.id
        
    async def retrieve(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a memory by ID."""
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
        """Search memories based on criteria."""
        memories = await self._load_from_disk()
        results = []
        
        for memory_data in memories.values():
            memory = Memory(**memory_data)
            match = True
            
            # Check type filter
            if "type" in query and memory.type != query["type"]:
                match = False
                
            # Check tags filter
            if "tags" in query:
                query_tags = set(query["tags"])
                memory_tags = set(memory.tags)
                if not query_tags.issubset(memory_tags):
                    match = False
                    
            # Check content search
            if "content_contains" in query:
                search_term = query["content_contains"].lower()
                if search_term not in str(memory.content).lower():
                    match = False
                    
            # Check time range
            if "after" in query and memory.timestamp < query["after"]:
                match = False
            if "before" in query and memory.timestamp > query["before"]:
                match = False
                
            # Check importance threshold
            if "min_importance" in query and memory.importance < query["min_importance"]:
                match = False
                
            if match:
                results.append(memory)
                
        return results
        
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        memories = await self._load_from_disk()
        
        if memory_id in memories:
            del memories[memory_id]
            await self._save_to_disk(memories)
            if memory_id in self._cache:
                del self._cache[memory_id]
            return True
        return False
        
    async def list_all(self, memory_type: MemoryType = None) -> List[Memory]:
        """List all memories, optionally filtered by type."""
        memories = await self._load_from_disk()
        results = []
        
        for memory_data in memories.values():
            memory = Memory(**memory_data)
            if memory_type is None or memory.type == memory_type:
                results.append(memory)
                
        return sorted(results, key=lambda m: m.timestamp, reverse=True)
        
    async def cleanup_old_memories(self, max_age_days: int = 30) -> int:
        """Clean up old memories beyond max_age_days."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        memories = await self._load_from_disk()
        
        deleted_count = 0
        to_delete = []
        
        for memory_id, memory_data in memories.items():
            memory = Memory(**memory_data)
            if memory.timestamp < cutoff_date and memory.importance < 0.5:
                to_delete.append(memory_id)
                
        for memory_id in to_delete:
            if await self.delete(memory_id):
                deleted_count += 1
                
        return deleted_count

class InMemoryStorage(MemoryStorage):
    """In-memory storage for testing and temporary use."""
    
    def __init__(self):
        self._storage: Dict[str, Memory] = {}
        
    async def store(self, memory: Memory) -> str:
        self._storage[memory.id] = memory
        return memory.id
        
    async def retrieve(self, memory_id: str) -> Optional[Memory]:
        return self._storage.get(memory_id)
        
    async def search(self, query: Dict[str, Any]) -> List[Memory]:
        results = []
        for memory in self._storage.values():
            # Simple search implementation
            match = True
            if "type" in query and memory.type != query["type"]:
                match = False
            if match:
                results.append(memory)
        return results
        
    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._storage:
            del self._storage[memory_id]
            return True
        return False
        
    async def list_all(self, memory_type: MemoryType = None) -> List[Memory]:
        memories = list(self._storage.values())
        if memory_type:
            memories = [m for m in memories if m.type == memory_type]
        return sorted(memories, key=lambda m: m.timestamp, reverse=True)