import hashlib
import json
import logging
import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from cachetools import LRUCache, TLRUCache
    HAS_CACHETOOLS = True
except ImportError:
    HAS_CACHETOOLS = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    LRU = "lru"
    TTL = "ttl"
    LFU = "lfu"
    FIFO = "fifo"


class _CacheEntry:
    __slots__ = ("value", "expires_at", "tags", "size_bytes", "access_count", "created_at", "last_access")

    def __init__(self, value: Any, expires_at: Optional[float] = None, tags: Optional[List[str]] = None):
        self.value = value
        self.expires_at = expires_at
        self.tags = tags or []
        self.size_bytes = _estimate_size(value)
        self.access_count = 0
        self.created_at = time.time()
        self.last_access = self.created_at


def _estimate_size(value: Any) -> int:
    try:
        raw = json.dumps(value, default=str)
        return len(raw.encode("utf-8"))
    except (TypeError, ValueError, RecursionError):
        return len(str(value).encode("utf-8"))


class CalculationCache:
    def __init__(
        self,
        max_size_mb: int = 512,
        strategy: CacheStrategy = CacheStrategy.LRU,
        default_ttl_seconds: int = 3600,
    ):
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._strategy = strategy
        self._default_ttl = default_ttl_seconds
        self._lock = threading.Lock()
        self._entries: Dict[str, _CacheEntry] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._access_order: List[str] = []
        self._hits = 0
        self._misses = 0
        self._current_size_bytes = 0

        if HAS_CACHETOOLS and strategy in (CacheStrategy.LRU, CacheStrategy.TTL):
            maxsize = max(1, int(max_size_mb * 1024 * 1024 / 512))
            if strategy == CacheStrategy.TTL:
                self._cachetools_cache = TLRUCache(maxsize=maxsize, ttu=lambda k, v, now: now + (v.ttl or default_ttl_seconds))  # type: ignore
            else:
                self._cachetools_cache = LRUCache(maxsize=maxsize)
            self._cachetools_data: Dict[str, Tuple[Any, Optional[float], List[str]]] = {}
        else:
            self._cachetools_cache = None

    def get(self, cache_key: str) -> Optional[Any]:
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is None:
                if self._cachetools_cache is not None:
                    raw = self._cachetools_cache.get(cache_key)
                    if raw is not None:
                        self._hits += 1
                        return self._cachetools_data.get(cache_key, (raw, None, None))[0]
                self._misses += 1
                return None
            if entry.expires_at is not None and time.time() > entry.expires_at:
                self._remove_entry(cache_key)
                self._misses += 1
                return None
            entry.access_count += 1
            entry.last_access = time.time()
            self._hits += 1
            if self._strategy == CacheStrategy.LRU:
                if cache_key in self._access_order:
                    self._access_order.remove(cache_key)
                self._access_order.append(cache_key)
            return entry.value

    def set(
        self,
        cache_key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.time() + ttl if ttl > 0 else None
        entry = _CacheEntry(value, expires_at=expires_at, tags=tags)
        with self._lock:
            old_entry = self._entries.get(cache_key)
            if old_entry is not None:
                self._current_size_bytes -= old_entry.size_bytes
                self._remove_from_tag_index(cache_key, old_entry.tags)
            self._current_size_bytes += entry.size_bytes
            self._entries[cache_key] = entry
            for tag in (tags or []):
                self._tag_index.setdefault(tag, set()).add(cache_key)
            if self._strategy == CacheStrategy.LRU:
                if cache_key in self._access_order:
                    self._access_order.remove(cache_key)
                self._access_order.append(cache_key)
            self._evict_if_needed(0)

            if self._cachetools_cache is not None:
                try:
                    self._cachetools_cache[cache_key] = value
                    self._cachetools_data[cache_key] = (value, expires_at, tags or [])
                except ValueError:
                    logger.debug("Cachetools cache set skipped for key %s (value too large)", cache_key)

    def invalidate(self, cache_key: str) -> bool:
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is None:
                return False
            self._remove_entry(cache_key)
            if self._cachetools_cache is not None:
                self._cachetools_cache.pop(cache_key, None)
                self._cachetools_data.pop(cache_key, None)
            return True

    def invalidate_by_tag(self, tag: str) -> int:
        with self._lock:
            keys = self._tag_index.pop(tag, set())
            count = 0
            for key in list(keys):
                if key in self._entries:
                    self._remove_entry(key)
                    count += 1
                if self._cachetools_cache is not None:
                    self._cachetools_cache.pop(key, None)
                    self._cachetools_data.pop(key, None)
            return count

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._tag_index.clear()
            self._access_order.clear()
            self._current_size_bytes = 0
            self._hits = 0
            self._misses = 0
            if self._cachetools_cache is not None:
                self._cachetools_cache.clear()
                self._cachetools_data.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "entries": len(self._entries),
                "size_bytes": self._current_size_bytes,
                "size_mb": round(self._current_size_bytes / (1024 * 1024), 2),
                "max_size_mb": round(self._max_size_bytes / (1024 * 1024), 2),
                "memory_usage": round(self._current_size_bytes / self._max_size_bytes * 100, 2) if self._max_size_bytes > 0 else 0.0,
                "strategy": self._strategy.value,
            }

    def get_cache_keys(self, pattern: Optional[str] = None) -> List[str]:
        with self._lock:
            if pattern is None:
                return list(self._entries.keys())
            import re
            regex = re.compile(pattern)
            return [k for k in self._entries if regex.search(k)]

    def exists(self, cache_key: str) -> bool:
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is None:
                return False
            if entry.expires_at is not None and time.time() > entry.expires_at:
                self._remove_entry(cache_key)
                return False
            return True

    def _remove_entry(self, cache_key: str) -> None:
        entry = self._entries.pop(cache_key, None)
        if entry is None:
            return
        self._current_size_bytes -= entry.size_bytes
        self._remove_from_tag_index(cache_key, entry.tags)
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)

    def _remove_from_tag_index(self, cache_key: str, tags: List[str]) -> None:
        for tag in tags:
            key_set = self._tag_index.get(tag)
            if key_set:
                key_set.discard(cache_key)
                if not key_set:
                    self._tag_index.pop(tag, None)

    def _evict_if_needed(self, required_mb: int) -> None:
        required_bytes = required_mb * 1024 * 1024
        while self._current_size_bytes + required_bytes > self._max_size_bytes and self._entries:
            if self._strategy in (CacheStrategy.LRU, CacheStrategy.FIFO):
                if self._access_order:
                    victim = self._access_order.pop(0)
                    self._remove_entry(victim)
            elif self._strategy == CacheStrategy.LFU:
                victim = min(self._entries, key=lambda k: self._entries[k].access_count)
                self._remove_entry(victim)
            else:
                victim = next(iter(self._entries))
                self._remove_entry(victim)

    def _get_lfu_victim(self) -> Optional[str]:
        if not self._entries:
            return None
        min_count = float("inf")
        victim = None
        for key, entry in self._entries.items():
            if entry.access_count < min_count:
                min_count = entry.access_count
                victim = key
        return victim


class CacheKeyBuilder:
    @staticmethod
    def build_key(component: str, method: str, params_hash: str) -> str:
        return f"{component}:{method}:{params_hash}"

    @staticmethod
    def hash_params(*args: Any, **kwargs: Any) -> str:
        hasher = hashlib.sha256()
        for arg in args:
            hasher.update(json.dumps(arg, default=str, sort_keys=True).encode("utf-8"))
        for key in sorted(kwargs.keys()):
            hasher.update(key.encode("utf-8"))
            hasher.update(json.dumps(kwargs[key], default=str, sort_keys=True).encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def hash_system_state(system: Any) -> str:
        hasher = hashlib.sha256()
        try:
            buses = sorted(getattr(system, "buses", {}).items())
            for bid, bus in buses:
                hasher.update(str(bid).encode("utf-8"))
                hasher.update(str(getattr(bus, "voltage", "")).encode("utf-8"))
                hasher.update(str(getattr(bus, "angle", "")).encode("utf-8"))
                hasher.update(str(getattr(bus, "connected", True)).encode("utf-8"))
            branches = sorted(getattr(system, "branches", {}).items())
            for bid, branch in branches:
                hasher.update(str(bid).encode("utf-8"))
                hasher.update(str(getattr(branch, "status", True)).encode("utf-8"))
                hasher.update(str(getattr(branch, "tap", 1.0)).encode("utf-8"))
            generators = sorted(getattr(system, "generators", {}).items())
            for gid, gen in generators:
                hasher.update(str(gid).encode("utf-8"))
                hasher.update(str(getattr(gen, "status", True)).encode("utf-8"))
                hasher.update(str(getattr(gen, "p_output", 0.0)).encode("utf-8"))
        except Exception:
            hasher.update(json.dumps(str(system), default=str).encode("utf-8"))
        return hasher.hexdigest()


TTL_RECOMMENDATIONS: Dict[str, int] = {
    "load_flow": 300,
    "fault_analysis": 600,
    "harmonic_analysis": 600,
    "opf": 300,
    "system_build": 3600,
    "coordination": 1800,
}


class SmartCacheStrategy:
    def __init__(self, cache: CalculationCache):
        self._cache = cache
        self._lock = threading.Lock()

    def should_cache(
        self,
        component: str,
        params: Dict[str, Any],
        frequency_estimate: Optional[float] = None,
    ) -> bool:
        if frequency_estimate is not None and frequency_estimate < 0.01:
            return False
        expensive = component in ("load_flow", "fault_analysis", "opf", "harmonic_analysis", "coordination")
        if expensive:
            return True
        size_estimate = _estimate_size(params)
        if size_estimate > 1024 * 100:
            return False
        return True

    def get_cache_ttl(self, component: str, result_type: Optional[str] = None) -> int:
        mapped = component
        if "load_flow" in component or "loadflow" in component:
            mapped = "load_flow"
        elif "fault" in component:
            mapped = "fault_analysis"
        elif "harmonic" in component:
            mapped = "harmonic_analysis"
        elif "opf" in component or "optimal" in component:
            mapped = "opf"
        elif "coordination" in component:
            mapped = "coordination"
        elif "build" in component or "data" in component or "system" in component:
            mapped = "system_build"
        return TTL_RECOMMENDATIONS.get(mapped, self._cache._default_ttl)

    def pre_warm(self, system: Any, study_types: List[str]) -> int:
        pre_warmed = 0
        builder = CacheKeyBuilder()
        for study in study_types:
            if study == "load_flow":
                key = builder.build_key("load_flow", "solve", builder.hash_system_state(system))
                if not self._cache.exists(key):
                    self._cache.set(key, None, ttl_seconds=TTL_RECOMMENDATIONS["load_flow"], tags=["prewarm", "load_flow"])
                    pre_warmed += 1
            elif study == "fault_analysis":
                key = builder.build_key("fault_analysis", "analyze", builder.hash_system_state(system))
                if not self._cache.exists(key):
                    self._cache.set(key, None, ttl_seconds=TTL_RECOMMENDATIONS["fault_analysis"], tags=["prewarm", "fault_analysis"])
                    pre_warmed += 1
            elif study == "coordination":
                key = builder.build_key("coordination", "evaluate", builder.hash_system_state(system))
                if not self._cache.exists(key):
                    self._cache.set(key, None, ttl_seconds=TTL_RECOMMENDATIONS["coordination"], tags=["prewarm", "coordination"])
                    pre_warmed += 1
        return pre_warmed


class MemoryManager:
    def __init__(self, cache: CalculationCache, max_memory_percent: float = 80.0):
        self._cache = cache
        self._max_memory_percent = max_memory_percent
        self._lock = threading.Lock()

    def get_memory_usage(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "cache_size_mb": round(self._cache._current_size_bytes / (1024 * 1024), 2),
            "max_cache_mb": round(self._cache._max_size_bytes / (1024 * 1024), 2),
            "cache_utilization": 0.0,
        }
        if HAS_PSUTIL:
            proc = psutil.Process()
            mem_info = proc.memory_info()
            total = psutil.virtual_memory().total
            result["process_rss_mb"] = round(mem_info.rss / (1024 * 1024), 2)
            result["process_vms_mb"] = round(mem_info.vms / (1024 * 1024), 2)
            result["system_total_mb"] = round(total / (1024 * 1024), 2)
            result["system_percent"] = psutil.virtual_memory().percent
            result["cache_utilization"] = round(
                self._cache._current_size_bytes / self._cache._max_size_bytes * 100, 2
            ) if self._cache._max_size_bytes > 0 else 0.0
        else:
            result["process_rss_mb"] = 0.0
            result["system_percent"] = 0.0
            cache_max = self._cache._max_size_bytes
            result["cache_utilization"] = round(
                self._cache._current_size_bytes / cache_max * 100, 2
            ) if cache_max > 0 else 0.0
        return result

    def evict_if_needed(self, required_mb: int = 0) -> bool:
        with self._lock:
            usage = self.get_memory_usage()
            if HAS_PSUTIL:
                current_percent = usage.get("system_percent", 0.0)
                if current_percent < self._max_memory_percent:
                    cache_util = usage["cache_utilization"]
                    if cache_util < 90.0:
                        return False
            evicted = 0
            while self._cache._entries:
                cache_util = (
                    self._cache._current_size_bytes / self._cache._max_size_bytes * 100
                ) if self._cache._max_size_bytes > 0 else 0
                if cache_util < 70.0 and (not HAS_PSUTIL or psutil.virtual_memory().percent < self._max_memory_percent):
                    break
                if self._cache._strategy in (CacheStrategy.LRU, CacheStrategy.FIFO):
                    if self._cache._access_order:
                        victim = self._cache._access_order.pop(0)
                        self._cache._remove_entry(victim)
                        evicted += 1
                elif self._cache._strategy == CacheStrategy.LFU:
                    victim = self._cache._get_lfu_victim()
                    if victim:
                        self._cache._remove_entry(victim)
                        evicted += 1
                else:
                    victim = next(iter(self._cache._entries))
                    self._cache._remove_entry(victim)
                    evicted += 1
            return evicted > 0

    def optimize(self) -> Dict[str, int]:
        removed_expired = 0
        removed_orphaned = 0
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, e in self._cache._entries.items()
                if e.expires_at is not None and now > e.expires_at
            ]
            for key in expired_keys:
                self._cache._remove_entry(key)
                removed_expired += 1
            empty_tags = [t for t, s in self._cache._tag_index.items() if not s]
            for t in empty_tags:
                self._cache._tag_index.pop(t, None)
        return {"expired_removed": removed_expired, "orphaned_tags_removed": removed_orphaned}

    def get_memory_report(self) -> Dict[str, Any]:
        usage = self.get_memory_usage()
        stats = self._cache.get_stats()
        return {
            "memory": usage,
            "cache_stats": stats,
            "recommendations": self._generate_recommendations(usage, stats),
        }

    def _generate_recommendations(self, usage: Dict[str, Any], stats: Dict[str, Any]) -> List[str]:
        recs: List[str] = []
        if usage.get("cache_utilization", 0) > 90:
            recs.append("Cache utilization exceeds 90%. Consider increasing max_size_mb.")
        if stats.get("hit_rate", 100) < 50:
            recs.append(f"Low hit rate ({stats['hit_rate']}%). Review TTL values or caching strategy.")
        if usage.get("system_percent", 0) > self._max_memory_percent:
            recs.append(f"System memory at {usage['system_percent']}% (limit: {self._max_memory_percent}%). Aggressive eviction recommended.")
        if not recs:
            recs.append("Cache health is good.")
        return recs


_singleton_lock = threading.Lock()
_calculation_cache_instance: Optional[CalculationCache] = None
_smart_strategy_instance: Optional[SmartCacheStrategy] = None
_memory_manager_instance: Optional[MemoryManager] = None


def get_calculation_cache(
    max_size_mb: int = 512,
    strategy: CacheStrategy = CacheStrategy.LRU,
    default_ttl_seconds: int = 3600,
) -> CalculationCache:
    global _calculation_cache_instance
    if _calculation_cache_instance is None:
        with _singleton_lock:
            if _calculation_cache_instance is None:
                _calculation_cache_instance = CalculationCache(
                    max_size_mb=max_size_mb,
                    strategy=strategy,
                    default_ttl_seconds=default_ttl_seconds,
                )
    return _calculation_cache_instance


def get_smart_cache_strategy() -> SmartCacheStrategy:
    global _smart_strategy_instance
    if _smart_strategy_instance is None:
        with _singleton_lock:
            if _smart_strategy_instance is None:
                _smart_strategy_instance = SmartCacheStrategy(get_calculation_cache())
    return _smart_strategy_instance


def get_memory_manager(max_memory_percent: float = 80.0) -> MemoryManager:
    global _memory_manager_instance
    if _memory_manager_instance is None:
        with _singleton_lock:
            if _memory_manager_instance is None:
                _memory_manager_instance = MemoryManager(
                    get_calculation_cache(),
                    max_memory_percent=max_memory_percent,
                )
    return _memory_manager_instance


def cached(
    component: str,
    ttl_seconds: Optional[int] = None,
    tags: Optional[List[str]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_calculation_cache()
            builder = CacheKeyBuilder()
            params_hash = builder.hash_params(*args, **kwargs)
            method = func.__name__
            cache_key = builder.build_key(component, method, params_hash)
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds=ttl_seconds, tags=tags)
            return result
        return wrapper
    return decorator
