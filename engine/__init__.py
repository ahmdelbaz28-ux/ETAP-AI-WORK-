"""Engine - Core power system simulation engine.

Provides the main PowerSystemEngine along with supporting modules for
asynchronous execution, caching, data optimization, error handling,
numerical safety, resilience, and distributed scalability.
"""

from engine.engine import PowerSystemEngine

from engine.async_executor import (
    AsyncExecutor,
    AsyncTask,
    TaskPriority,
    TaskStatus,
    ThreadPoolManager,
    ProcessPoolManager,
    WorkflowOrchestrator,
    async_timeout,
    async_retry,
    get_async_executor,
    get_thread_pool_manager,
    get_process_pool_manager,
)

from engine.cache_manager import (
    CalculationCache,
    CacheKeyBuilder,
    CacheStrategy,
    SmartCacheStrategy,
    MemoryManager,
    cached,
    get_calculation_cache,
    get_smart_cache_strategy,
    get_memory_manager,
)

from engine.data_optimizer import (
    SparseMatrixManager,
    MemoryOptimizedSystem,
    BatchProcessor,
    DataCompressor,
    PerformanceProfiler,
    LargeSystemAdapter,
)

from engine.error_handler import (
    ErrorHandler,
    ErrorSeverity,
    EngineSystemError,
    AlertManager,
    AutoRecoveryManager,
    component_guard,
    get_error_handler,
    get_alert_manager,
    get_auto_recovery_manager,
)

from engine.numerical_safety import (
    NumericalBounds,
    NumericalGuard,
    ConvergenceMonitor,
    ConsistencyCheck,
    MatrixStabilizer,
    wrap_solver,
    safe_calculation,
)

from engine.resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    RetryHandler,
    RecoveryResult,
    MultiLevelRecovery,
    StabilityEnforcer,
    with_retry,
    register_circuit_breaker,
    get_circuit_breaker,
    get_all_circuit_breakers,
    get_resilience_stats,
)

from engine.scalability import (
    LoadBalancer,
    LoadBalancingStrategy,
    WorkerNode,
    DistributedTaskQueue,
    ClusterManager,
    ClusterNode,
    HorizontalScaler,
    PartitionManager,
    PartitionType,
    Partition,
    DistributedOrchestrator,
    TaskPriority as ScalabilityTaskPriority,
)

__all__ = [
    "PowerSystemEngine",
    # async_executor
    "AsyncExecutor",
    "AsyncTask",
    "TaskPriority",
    "TaskStatus",
    "ThreadPoolManager",
    "ProcessPoolManager",
    "WorkflowOrchestrator",
    "async_timeout",
    "async_retry",
    "get_async_executor",
    "get_thread_pool_manager",
    "get_process_pool_manager",
    # cache_manager
    "CalculationCache",
    "CacheKeyBuilder",
    "CacheStrategy",
    "SmartCacheStrategy",
    "MemoryManager",
    "cached",
    "get_calculation_cache",
    "get_smart_cache_strategy",
    "get_memory_manager",
    # data_optimizer
    "SparseMatrixManager",
    "MemoryOptimizedSystem",
    "BatchProcessor",
    "DataCompressor",
    "PerformanceProfiler",
    "LargeSystemAdapter",
    # error_handler
    "ErrorHandler",
    "ErrorSeverity",
    "EngineSystemError",
    "AlertManager",
    "AutoRecoveryManager",
    "component_guard",
    "get_error_handler",
    "get_alert_manager",
    "get_auto_recovery_manager",
    # numerical_safety
    "NumericalBounds",
    "NumericalGuard",
    "ConvergenceMonitor",
    "ConsistencyCheck",
    "MatrixStabilizer",
    "wrap_solver",
    "safe_calculation",
    # resilience
    "CircuitBreaker",
    "CircuitBreakerState",
    "CircuitBreakerOpenError",
    "RetryHandler",
    "RecoveryResult",
    "MultiLevelRecovery",
    "StabilityEnforcer",
    "with_retry",
    "register_circuit_breaker",
    "get_circuit_breaker",
    "get_all_circuit_breakers",
    "get_resilience_stats",
    # scalability
    "LoadBalancer",
    "LoadBalancingStrategy",
    "WorkerNode",
    "DistributedTaskQueue",
    "ClusterManager",
    "ClusterNode",
    "HorizontalScaler",
    "PartitionManager",
    "PartitionType",
    "Partition",
    "DistributedOrchestrator",
    "ScalabilityTaskPriority",
]
