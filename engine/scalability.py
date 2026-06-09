"""
Scalability and distributed computing for the ETAP AI Engineering Platform.

Provides horizontal scaling, load balancing, task queuing, cluster management,
data partitioning, and distributed orchestration for large power system studies.
"""

import enum, heapq, logging, random, threading, time, uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LoadBalancer
# ---------------------------------------------------------------------------

class LoadBalancingStrategy(str, enum.Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED = "weighted"


@dataclass
class WorkerNode:
    worker_id: str
    capacity: float
    weight: float = 1.0
    current_load: float = 0.0
    healthy: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    tasks_completed: int = 0
    tasks_failed: int = 0


class LoadBalancer:
    def __init__(self, strategy: str = "round_robin") -> None:
        self._strategy = LoadBalancingStrategy(strategy)
        self._workers: Dict[str, WorkerNode] = {}
        self._lock = threading.Lock()
        self._rr_index: int = 0

    def register_worker(self, worker_id: str, capacity: float, weight: float = 1.0) -> None:
        with self._lock:
            self._workers[worker_id] = WorkerNode(worker_id=worker_id, capacity=capacity, weight=max(weight, 0.1))

    def unregister_worker(self, worker_id: str) -> None:
        with self._lock:
            self._workers.pop(worker_id, None)

    def get_next_worker(self, task_size: Optional[float] = None) -> Optional[str]:
        with self._lock:
            healthy = {wid: w for wid, w in self._workers.items() if w.healthy}
            if not healthy:
                return None
            if self._strategy == LoadBalancingStrategy.ROUND_ROBIN:
                ids = list(healthy.keys())
                idx = self._rr_index % len(ids)
                self._rr_index = (self._rr_index + 1) % len(ids)
                return ids[idx]
            elif self._strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                return min(healthy, key=lambda wid: healthy[wid].current_load / max(healthy[wid].capacity, 1e-9))
            elif self._strategy == LoadBalancingStrategy.RANDOM:
                return random.choice(list(healthy.keys()))
            elif self._strategy == LoadBalancingStrategy.WEIGHTED:
                total = sum(w.weight for w in healthy.values())
                r = random.uniform(0, total)
                cumulative = 0.0
                for wid, w in healthy.items():
                    cumulative += w.weight
                    if r <= cumulative:
                        return wid
                return list(healthy.keys())[-1]
            return list(healthy.keys())[0]

    def get_worker_status(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None:
                return None
            return {"worker_id": w.worker_id, "capacity": w.capacity, "current_load": w.current_load,
                    "utilization": w.current_load / max(w.capacity, 1e-9), "healthy": w.healthy,
                    "tasks_completed": w.tasks_completed, "tasks_failed": w.tasks_failed, "weight": w.weight}

    def get_all_workers_status(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self.get_worker_status(wid) for wid in self._workers]

    def set_strategy(self, strategy: str) -> None:
        with self._lock:
            self._strategy = LoadBalancingStrategy(strategy)

    def update_worker_load(self, worker_id: str, current_load: float) -> None:
        with self._lock:
            w = self._workers.get(worker_id)
            if w is not None:
                w.current_load = max(0.0, current_load)
                w.last_heartbeat = time.time()


# ---------------------------------------------------------------------------
# DistributedTaskQueue
# ---------------------------------------------------------------------------

class TaskPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


_PRIORITY_MAP = {TaskPriority.LOW: 3, TaskPriority.NORMAL: 2, TaskPriority.HIGH: 1}


@dataclass(order=True)
class TaskItem:
    priority: int
    enqueued_at: float
    task_id: str = field(compare=False)
    task_data: Any = field(compare=False)
    status: str = field(default="queued", compare=False)
    assigned_worker: Optional[str] = field(default=None, compare=False)
    retries: int = field(default=0, compare=False)


class DistributedTaskQueue:
    def __init__(self, queue_type: str = "memory") -> None:
        self.queue_type = queue_type
        self._lock = threading.Lock()
        self._queue: List[TaskItem] = []
        self._tasks: Dict[str, TaskItem] = {}
        self._completed: Dict[str, TaskItem] = {}
        self._failed: Dict[str, TaskItem] = {}
        if queue_type == "redis":
            try:
                from redis import Redis
                self._redis = Redis()
            except ImportError:
                logger.warning("redis not installed; falling back to in-memory")
                self.queue_type = "memory"
        elif queue_type == "rabbitmq":
            try:
                from kombu import Connection
                self._rabbitmq = Connection("amqp://guest:guest@localhost:5672//")
            except ImportError:
                logger.warning("kombu not installed; falling back to in-memory")
                self.queue_type = "memory"

    def enqueue(self, task_data: Any, priority: str = "normal") -> str:
        task_id = str(uuid.uuid4())
        prio = _PRIORITY_MAP.get(TaskPriority(priority), _PRIORITY_MAP[TaskPriority.NORMAL])
        item = TaskItem(priority=prio, enqueued_at=time.time(), task_id=task_id, task_data=task_data)
        with self._lock:
            heapq.heappush(self._queue, item)
            self._tasks[task_id] = item
        return task_id

    def dequeue(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            while self._queue:
                item = heapq.heappop(self._queue)
                if item.status == "queued":
                    item.status = "in_progress"
                    item.assigned_worker = worker_id
                    return {"task_id": item.task_id, "task_data": item.task_data}
            return None

    def acknowledge(self, task_id: str, worker_id: str) -> bool:
        with self._lock:
            item = self._tasks.get(task_id)
            if item is None or item.status != "in_progress":
                return False
            item.status = "completed"
            self._completed[task_id] = item
            return True

    def requeue_failed(self, task_id: str) -> bool:
        with self._lock:
            item = self._tasks.get(task_id)
            if item is None:
                return False
            item.status = "queued"
            item.assigned_worker = None
            item.retries += 1
            self._failed.pop(task_id, None)
            heapq.heappush(self._queue, item)
            return True

    def get_queue_depth(self) -> int:
        with self._lock:
            return len(self._queue)

    def get_queue_statistics(self) -> Dict[str, Any]:
        with self._lock:
            queued = self.get_queue_depth()
            in_progress = sum(1 for t in self._tasks.values() if t.status == "in_progress")
            completed = len(self._completed)
            failed = sum(1 for t in self._tasks.values() if t.status == "failed")
            total = len(self._tasks)
            return {"queue_type": self.queue_type, "queued": queued, "in_progress": in_progress,
                    "completed": completed, "failed": failed, "total": total,
                    "failure_rate": failed / max(total, 1)}


# ---------------------------------------------------------------------------
# ClusterManager
# ---------------------------------------------------------------------------

@dataclass
class ClusterNode:
    node_id: str
    host: str
    port: int
    capabilities: Dict[str, Any]
    healthy: bool = True
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    current_load: float = 0.0
    active_studies: List[str] = field(default_factory=list)


class ClusterManager:
    def __init__(self, cluster_name: str = "etap-platform") -> None:
        self.cluster_name = cluster_name
        self._nodes: Dict[str, ClusterNode] = {}
        self._lock = threading.Lock()
        self._failure_handlers: List[Callable[[str], None]] = []

    def register_node(self, node_id: str, host: str, port: int, capabilities: Dict[str, Any]) -> None:
        with self._lock:
            self._nodes[node_id] = ClusterNode(node_id=node_id, host=host, port=port, capabilities=capabilities)

    def discover_nodes(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"node_id": n.node_id, "host": n.host, "port": n.port,
                     "capabilities": n.capabilities, "healthy": n.healthy}
                    for n in self._nodes.values()]

    def get_active_nodes(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [{"node_id": n.node_id, "host": n.host, "port": n.port,
                     "capabilities": n.capabilities, "current_load": n.current_load}
                    for n in self._nodes.values() if n.healthy]

    def get_node_capabilities(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            node = self._nodes.get(node_id)
            return node.capabilities if node else None

    def assign_study(self, study_type: str, system_size: float) -> Optional[Dict[str, Any]]:
        with self._lock:
            candidates = [n for n in self._nodes.values()
                          if n.healthy and study_type in n.capabilities.get("study_types", [])]
            if not candidates:
                return None
            best = min(candidates, key=lambda n: n.current_load)
            best.active_studies.append(study_type)
            best.current_load += system_size * 0.01
            return {"node_id": best.node_id, "host": best.host, "port": best.port, "capabilities": best.capabilities}

    def handle_node_failure(self, node_id: str) -> List[str]:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return []
            node.healthy = False
            reassigned = list(node.active_studies)
            node.active_studies.clear()
            node.current_load = 0.0
            for handler in self._failure_handlers:
                try:
                    handler(node_id)
                except Exception:
                    logger.debug("Failure handler error for node %s", node_id)
            return reassigned

    def register_failure_handler(self, handler: Callable[[str], None]) -> None:
        self._failure_handlers.append(handler)

    def get_cluster_health(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._nodes)
            healthy = sum(1 for n in self._nodes.values() if n.healthy)
            total_load = sum(n.current_load for n in self._nodes.values())
            total_capacity = sum(n.capabilities.get("max_load", 100.0) for n in self._nodes.values())
            return {"cluster_name": self.cluster_name, "total_nodes": total, "healthy_nodes": healthy,
                    "unhealthy_nodes": total - healthy, "total_load": total_load,
                    "total_capacity": total_capacity,
                    "utilization": total_load / max(total_capacity, 1e-9),
                    "status": "healthy" if healthy == total else "degraded" if healthy > 0 else "down"}


# ---------------------------------------------------------------------------
# HorizontalScaler
# ---------------------------------------------------------------------------

class HorizontalScaler:
    def __init__(self, min_nodes: int = 1, max_nodes: int = 10,
                 scale_up_threshold: float = 0.8, scale_down_threshold: float = 0.2) -> None:
        self.min_nodes = max(1, min_nodes)
        self.max_nodes = max(self.min_nodes, max_nodes)
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self._current_nodes = self.min_nodes
        self._scale_up_cbs: List[Callable[[int], None]] = []
        self._scale_down_cbs: List[Callable[[int], None]] = []
        self._lock = threading.Lock()

    def evaluate_scaling(self, current_load: float) -> Optional[str]:
        if current_load >= self.scale_up_threshold and self._current_nodes < self.max_nodes:
            return "scale_up"
        if current_load <= self.scale_down_threshold and self._current_nodes > self.min_nodes:
            return "scale_down"
        return None

    def scale_up(self, nodes: int = 1) -> int:
        with self._lock:
            actual = min(nodes, self.max_nodes - self._current_nodes)
            if actual <= 0:
                return self._current_nodes
            self._current_nodes += actual
            for cb in self._scale_up_cbs:
                try:
                    cb(actual)
                except Exception:
                    logger.exception("Scale-up callback error")
            return self._current_nodes

    def scale_down(self, nodes: int = 1) -> int:
        with self._lock:
            actual = min(nodes, self._current_nodes - self.min_nodes)
            if actual <= 0:
                return self._current_nodes
            self._current_nodes -= actual
            for cb in self._scale_down_cbs:
                try:
                    cb(actual)
                except Exception:
                    logger.exception("Scale-down callback error")
            return self._current_nodes

    def get_scaling_recommendation(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        avg_util = sum(metrics.values()) / max(len(metrics), 1)
        action = self.evaluate_scaling(avg_util)
        suggested = self._current_nodes
        if action == "scale_up":
            suggested = min(self._current_nodes + 1, self.max_nodes)
        elif action == "scale_down":
            suggested = max(self._current_nodes - 1, self.min_nodes)
        reason = (f"Utilization {avg_util:.1%} exceeds {self.scale_up_threshold:.0%}" if action == "scale_up" else
                  f"Utilization {avg_util:.1%} below {self.scale_down_threshold:.0%}" if action == "scale_down" else
                  f"Utilization {avg_util:.1%} within normal range")
        return {"action": action, "reason": reason, "current_nodes": self._current_nodes,
                "suggested_nodes": suggested, "average_utilization": avg_util}

    def get_current_capacity(self) -> int:
        return self._current_nodes

    def on_scale_up(self, callback: Callable[[int], None]) -> None:
        self._scale_up_cbs.append(callback)

    def on_scale_down(self, callback: Callable[[int], None]) -> None:
        self._scale_down_cbs.append(callback)


# ---------------------------------------------------------------------------
# PartitionManager
# ---------------------------------------------------------------------------

class PartitionType(str, enum.Enum):
    BUS_BASED = "bus_based"
    ZONE_BASED = "zone_based"
    VOLTAGE_LEVEL = "voltage_level"


@dataclass
class Partition:
    partition_id: str
    buses: List[int]
    boundary_buses: List[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


class PartitionManager:
    def __init__(self, partition_type: str = "bus_based") -> None:
        self.partition_type = PartitionType(partition_type)
        self._partitions: Dict[str, Partition] = {}
        self._original_buses: List[int] = []

    def partition_system(self, system: Any, num_partitions: int) -> List[Dict[str, Any]]:
        bus_ids = self._extract_bus_ids(system)
        self._original_buses = list(bus_ids)
        self._partitions.clear()

        if self.partition_type == PartitionType.BUS_BASED:
            partitions = self._bus_based(bus_ids, num_partitions)
        elif self.partition_type == PartitionType.ZONE_BASED:
            partitions = self._zone_based(bus_ids, num_partitions)
        elif self.partition_type == PartitionType.VOLTAGE_LEVEL:
            partitions = self._voltage_level(bus_ids, num_partitions, system)
        else:
            partitions = self._bus_based(bus_ids, num_partitions)

        results = []
        for pid, buses, boundaries in partitions:
            p = Partition(partition_id=pid, buses=buses, boundary_buses=boundaries,
                          metadata={"num_buses": len(buses), "num_boundaries": len(boundaries)})
            self._partitions[pid] = p
            results.append({"partition_id": pid, "buses": buses,
                            "boundary_buses": boundaries, "num_buses": len(buses)})
        return results

    def get_partition(self, partition_id: str) -> Optional[Dict[str, Any]]:
        p = self._partitions.get(partition_id)
        if p is None:
            return None
        return {"partition_id": p.partition_id, "buses": p.buses,
                "boundary_buses": p.boundary_buses, "metadata": p.metadata}

    def merge_results(self, partition_results: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {"partitions_merged": len(partition_results), "status": "success"}
        for pid, result in partition_results.items():
            if isinstance(result, dict):
                for key, value in result.items():
                    if key == "bus_voltages" and isinstance(value, dict):
                        merged.setdefault("bus_voltages", {}).update(value)
                    elif key == "power_flows" and isinstance(value, list):
                        merged.setdefault("power_flows", []).extend(value)
                    else:
                        merged.setdefault(f"partition_{pid}", result)
        return merged

    def get_boundary_buses(self) -> List[int]:
        boundary_set: set[int] = set()
        for p in self._partitions.values():
            boundary_set.update(p.boundary_buses)
        return sorted(boundary_set)

    def verify_partition_integrity(self) -> bool:
        all_buses: List[int] = []
        for p in self._partitions.values():
            all_buses.extend(p.buses)
        restored = set(all_buses)
        if len(restored) != len(self._original_buses):
            logger.error("Integrity check failed: %d original vs %d restored",
                         len(self._original_buses), len(restored))
            return False
        missing = set(self._original_buses) - restored
        if missing:
            logger.error("Missing buses: %s", missing)
            return False
        return True

    def _extract_bus_ids(self, system: Any) -> List[int]:
        if hasattr(system, "buses"):
            return [b.id if hasattr(b, "id") else b for b in system.buses]
        if hasattr(system, "bus_ids"):
            return list(system.bus_ids)
        return list(range(100))

    def _bus_based(self, bus_ids: List[int], num: int) -> List[Tuple[str, List[int], List[int]]]:
        num = max(1, min(num, len(bus_ids)))
        chunks = [bus_ids[i::num] for i in range(num)]
        results = []
        for i, chunk in enumerate(chunks):
            pid = f"bus_partition_{i:04d}"
            boundaries = self._compute_boundaries(chunk, chunks)
            results.append((pid, chunk, boundaries))
        return results

    def _zone_based(self, bus_ids: List[int], num: int) -> List[Tuple[str, List[int], List[int]]]:
        return self._bus_based(sorted(bus_ids), num)

    def _voltage_level(self, bus_ids: List[int], num: int, system: Any) -> List[Tuple[str, List[int], List[int]]]:
        kv_groups: Dict[float, List[int]] = defaultdict(list)
        for bid in bus_ids:
                kv = 13.8
                if hasattr(system, "get_bus_voltage"):
                    try:
                        kv = system.get_bus_voltage(bid)
                    except Exception as kv_err:
                        # If a single bus voltage lookup fails (e.g. disconnected
                        # bus, backend error), keep the default 13.8 kV bucket so
                        # the bus is still placed somewhere and isn't lost.
                        logger.debug(
                            "get_bus_voltage(%s) failed (%s); using 13.8 kV default",
                            bid, type(kv_err).__name__,
                        )
                kv_groups[kv].append(bid)
        groups = list(kv_groups.values())
        num = max(1, min(num, len(groups)))
        chunks = [groups[i::num] for i in range(num)]
        results = []
        for i, chunk in enumerate(chunks):
            flat = [b for g in chunk for b in g]
            pid = f"voltage_partition_{i:04d}"
            boundaries = self._compute_boundaries(flat, chunks)
            results.append((pid, flat, boundaries))
        return results

    @staticmethod
    def _compute_boundaries(chunk: List[int], all_chunks: List[List[int]]) -> List[int]:
        chunk_set = set(chunk)
        boundaries: set[int] = set()
        for other in all_chunks:
            other_set = set(other)
            if other_set != chunk_set:
                boundaries.update(chunk_set & other_set)
        return sorted(boundaries)


# ---------------------------------------------------------------------------
# DistributedOrchestrator
# ---------------------------------------------------------------------------

class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionPlan:
    study_type: str
    num_nodes: int
    num_partitions: int
    estimated_duration: float
    partition_strategy: str
    steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Execution:
    task_id: str
    study_type: str
    status: ExecutionStatus
    plan: ExecutionPlan
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None
    partial_results: Dict[str, Any] = field(default_factory=dict)


class DistributedOrchestrator:
    def __init__(self, cluster_manager: ClusterManager, task_queue: DistributedTaskQueue) -> None:
        self.cluster_manager = cluster_manager
        self.task_queue = task_queue
        self._executions: Dict[str, Execution] = {}
        self._lock = threading.Lock()

    def execute_distributed_study(self, study_type: str, system: Any, params: Dict[str, Any]) -> str:
        system_size = self._estimate_system_size(system)
        plan = self._build_plan(study_type, system_size, params)
        task_id = str(uuid.uuid4())
        execution = Execution(task_id=task_id, study_type=study_type,
                              status=ExecutionStatus.RUNNING, plan=plan)
        with self._lock:
            self._executions[task_id] = execution
        for step in plan.steps:
            self.task_queue.enqueue(
                task_data={"study_type": study_type, "step": step, "params": params, "execution_id": task_id},
                priority=params.get("priority", "normal"),
            )
        return task_id

    def get_execution_plan(self, study_type: str, system_size: float) -> ExecutionPlan:
        return self._build_plan(study_type, system_size, {})

    def monitor_execution(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            execution = self._executions.get(task_id)
            if execution is None:
                return None
            return {"task_id": execution.task_id, "study_type": execution.study_type,
                    "status": execution.status.value,
                    "plan": {"num_nodes": execution.plan.num_nodes,
                             "num_partitions": execution.plan.num_partitions,
                             "estimated_duration": execution.plan.estimated_duration},
                    "started_at": execution.started_at, "completed_at": execution.completed_at,
                    "error": execution.error, "partial_results_count": len(execution.partial_results)}

    def cancel_execution(self, task_id: str) -> bool:
        with self._lock:
            execution = self._executions.get(task_id)
            if execution is None or execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED):
                return False
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = time.time()
            return True

    def _build_plan(self, study_type: str, system_size: float, params: Dict[str, Any]) -> ExecutionPlan:
        num_nodes = params.get("num_nodes", 2)
        num_partitions = params.get("num_partitions", min(int(system_size / 10) + 1, 8))
        partition_strategy = params.get("partition_strategy", "bus_based")
        est_duration = self._estimate_duration(study_type, system_size, num_partitions)
        steps = [{"step_id": f"step_{i:04d}", "partition_id": f"partition_{i:04d}",
                  "assigned_node": None, "estimated_cost": system_size / num_partitions}
                 for i in range(num_partitions)]
        return ExecutionPlan(study_type=study_type, num_nodes=num_nodes,
                             num_partitions=num_partitions, estimated_duration=est_duration,
                             partition_strategy=partition_strategy, steps=steps)

    @staticmethod
    def _estimate_system_size(system: Any) -> float:
        if hasattr(system, "buses"):
            return float(len(system.buses))
        if hasattr(system, "bus_ids"):
            return float(len(system.bus_ids))
        return 100.0

    @staticmethod
    def _estimate_duration(study_type: str, system_size: float, num_partitions: int) -> float:
        base = {"load_flow": 0.5, "fault_analysis": 1.0, "coordination": 2.0}
        cost = base.get(study_type, 1.0) * system_size * 0.01
        return cost / max(num_partitions, 1)
