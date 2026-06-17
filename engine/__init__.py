"""Engine - Core power system simulation engine.

Provides the main PowerSystemEngine along with supporting modules for
asynchronous execution, caching, data optimization, error handling,
numerical safety, resilience, and distributed scalability.
"""

from engine.async_executor import (
    AsyncExecutor,
    AsyncTask,
    ProcessPoolManager,
    TaskPriority,
    TaskStatus,
    ThreadPoolManager,
    WorkflowOrchestrator,
    async_retry,
    async_timeout,
    get_async_executor,
    get_process_pool_manager,
    get_thread_pool_manager,
)
from engine.cache_manager import (
    CacheKeyBuilder,
    CacheStrategy,
    CalculationCache,
    MemoryManager,
    SmartCacheStrategy,
    cached,
    get_calculation_cache,
    get_memory_manager,
    get_smart_cache_strategy,
)
from engine.caching import (
    StudyCache,
    get_study_cache,
)
from engine.data_optimizer import (
    BatchProcessor,
    DataCompressor,
    LargeSystemAdapter,
    MemoryOptimizedSystem,
    PerformanceProfiler,
    SparseMatrixManager,
)
from engine.engine import PowerSystemEngine
from engine.error_handler import (
    AlertManager,
    AutoRecoveryManager,
    EngineSystemError,
    ErrorHandler,
    ErrorSeverity,
    component_guard,
    get_alert_manager,
    get_auto_recovery_manager,
    get_error_handler,
)
from engine.gpu_solver import (
    GPUSolver,
)
from engine.interfaces import (
    ArcFlashEngineProtocol,
    CoordinationEngineProtocol,
    FaultAnalyzerProtocol,
    LoadFlowSolverProtocol,
    VisualizerProtocol,
)
from engine.numerical_safety import (
    ConsistencyCheck,
    ConvergenceMonitor,
    MatrixStabilizer,
    NumericalBounds,
    NumericalGuard,
    safe_calculation,
    wrap_solver,
)
from engine.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    MultiLevelRecovery,
    RecoveryResult,
    RetryHandler,
    StabilityEnforcer,
    get_all_circuit_breakers,
    get_circuit_breaker,
    get_resilience_stats,
    register_circuit_breaker,
    with_retry,
)
from engine.scalability import (
    ClusterManager,
    ClusterNode,
    DistributedOrchestrator,
    DistributedTaskQueue,
    HorizontalScaler,
    LoadBalancer,
    LoadBalancingStrategy,
    Partition,
    PartitionManager,
    PartitionType,
    WorkerNode,
)
from engine.scalability import (
    TaskPriority as ScalabilityTaskPriority,
)
from engine.sparse_solver import (
    BranchData,
    BusData,
    SparseConvergenceResult,
    SparseYBus,
    create_ieee_test_system,
)

__all__ = [
    "PowerSystemEngine",
    "LoadFlowSolverProtocol",
    "FaultAnalyzerProtocol",
    "ArcFlashEngineProtocol",
    "CoordinationEngineProtocol",
    "VisualizerProtocol",
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
    # caching (Redis-backed)
    "StudyCache",
    "get_study_cache",
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
    # sparse_solver
    "SparseYBus",
    "BusData",
    "BranchData",
    "SparseConvergenceResult",
    "create_ieee_test_system",
    # gpu_solver
    "GPUSolver",
]
