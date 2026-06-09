"""Async execution and concurrency module for the ETAP AI Engineering Platform."""

import asyncio
import enum
import logging
import threading
import time
import uuid
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, List, Optional, Sequence

logger = logging.getLogger(__name__)

try:
    from engine.error_handler import get_error_handler, ErrorSeverity
    _error_handler_available = True
except ImportError:
    _error_handler_available = False


class TaskPriority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


@dataclass
class AsyncTask:
    task_id: str
    name: str
    coroutine: Optional[Coroutine] = None
    callable: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    timeout: Optional[float] = None


class _PriorityTaskQueue:
    _ORDER = {
        TaskPriority.CRITICAL: 0,
        TaskPriority.HIGH: 1,
        TaskPriority.MEDIUM: 2,
        TaskPriority.LOW: 3,
    }

    def __init__(self, maxsize: int = 0) -> None:
        self._maxsize = maxsize
        self._queues: dict[int, list[AsyncTask]] = {
            v: [] for v in self._ORDER.values()
        }
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def put(self, task: AsyncTask) -> None:
        with self._cond:
            if self._maxsize and self.qsize_unlocked() >= self._maxsize:
                raise RuntimeError(f"Queue full ({self._maxsize} items)")
            prio = self._ORDER[task.priority]
            self._queues[prio].append(task)
            self._cond.notify()

    def get(self, timeout: Optional[float] = None) -> Optional[AsyncTask]:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while True:
                task = self._get_highest_prio()
                if task is not None:
                    return task
                remaining = 0.0
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                self._cond.wait(timeout=remaining)

    def peek(self) -> Optional[AsyncTask]:
        with self._lock:
            return self._get_highest_prio()

    def remove(self, task_id: str) -> Optional[AsyncTask]:
        with self._lock:
            for prio in sorted(self._queues):
                for i, t in enumerate(self._queues[prio]):
                    if t.task_id == task_id:
                        return self._queues[prio].pop(i)
        return None

    def qsize(self) -> int:
        with self._lock:
            return self.qsize_unlocked()

    def qsize_unlocked(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def _get_highest_prio(self) -> Optional[AsyncTask]:
        for prio in sorted(self._queues):
            if self._queues[prio]:
                return self._queues[prio].pop(0)
        return None


class AsyncExecutor:
    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 1000,
    ) -> None:
        self._max_workers = max_workers
        self._max_queue_size = max_queue_size
        self._tasks: dict[str, AsyncTask] = {}
        self._queue = _PriorityTaskQueue(maxsize=max_queue_size)
        self._lock = threading.Lock()
        self._workers: list[threading.Thread] = []
        self._shutdown_event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._stats: dict[str, Any] = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_timed_out": 0,
        }
        self._start_loop()

    def _start_loop(self) -> None:
        def _run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        t = threading.Thread(target=_run_loop, daemon=True, name="AsyncExecutorLoop")
        t.start()
        self._loop_ready.wait(timeout=5)
        for _ in range(self._max_workers):
            w = threading.Thread(target=self._worker_loop, daemon=True, name="AsyncExecutorWorker")
            w.start()
            self._workers.append(w)

    def _worker_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                task = self._queue.get(timeout=0.5)
            except Exception:
                continue
            if task is None:
                continue
            self._execute_task(task)

    def _execute_task(self, task: AsyncTask) -> None:
        with self._lock:
            if task.status == TaskStatus.CANCELLED:
                return
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()

        try:
            if task.coroutine is not None:
                if self._loop is None or not self._loop.is_running():
                    raise RuntimeError("Event loop not available")
                future = asyncio.run_coroutine_threadsafe(task.coroutine, self._loop)
                result = future.result(timeout=task.timeout)
            else:
                fn = task.callable
                if fn is None:
                    raise ValueError("No callable or coroutine provided")
                if task.timeout is not None:
                    with _timeout(task.timeout):
                        result = fn(*task.args, **task.kwargs)
                else:
                    result = fn(*task.args, **task.kwargs)

            with self._lock:
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                self._stats["total_completed"] += 1
        except asyncio.TimeoutError:
            with self._lock:
                task.status = TaskStatus.TIMEOUT
                task.error = "Task timed out"
                task.completed_at = datetime.utcnow()
                self._stats["total_timed_out"] += 1
            if _error_handler_available:
                get_error_handler().handle_error(
                    component="async_executor",
                    message=f"Task '{task.name}' timed out after {task.timeout}s",
                    severity=ErrorSeverity.WARNING,
                )
        except Exception as e:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                self._stats["total_failed"] += 1
            if _error_handler_available:
                get_error_handler().handle_error(
                    component="async_executor",
                    message=f"Task '{task.name}' failed: {e}",
                    severity=ErrorSeverity.ERROR,
                    exception=e,
                )
        finally:
            with self._lock:
                self._stats["total_submitted"] = len(self._tasks)

    def submit_task(
        self,
        fn: Callable,
        *args: Any,
        priority: TaskPriority = TaskPriority.MEDIUM,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        task_id = str(uuid.uuid4())
        task = AsyncTask(
            task_id=task_id,
            name=name or getattr(fn, "__name__", "unknown"),
            callable=fn,
            args=args,
            kwargs=kwargs,
            priority=priority,
            tags=tags or [],
            timeout=timeout,
        )
        with self._lock:
            self._tasks[task_id] = task
        self._queue.put(task)
        return task_id

    def submit_coroutine(
        self,
        coro: Coroutine,
        priority: TaskPriority = TaskPriority.MEDIUM,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        task = AsyncTask(
            task_id=task_id,
            name=name or getattr(coro, "__name__", "coroutine"),
            coroutine=coro,
            priority=priority,
            tags=tags or [],
            timeout=timeout,
        )
        with self._lock:
            self._tasks[task_id] = task
        self._queue.put(task)
        return task_id

    async def run_parallel(
        self,
        tasks: Sequence[Any],
        max_concurrent: Optional[int] = None,
        return_exceptions: bool = False,
    ) -> List[Any]:
        semaphore = asyncio.Semaphore(max_concurrent or len(tasks))

        async def _run_one(t):
            async with semaphore:
                if asyncio.iscoroutine(t):
                    return await t
                if callable(t):
                    result = t()
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
                return t

        coros = [_run_one(t) for t in tasks]
        if return_exceptions:
            return await asyncio.gather(*coros, return_exceptions=True)
        return await asyncio.gather(*coros)

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
                return False
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            self._stats["total_cancelled"] += 1
        removed = self._queue.remove(task_id)
        return removed is not None or task.status == TaskStatus.CANCELLED

    def get_queue_size(self) -> int:
        return self._queue.qsize()

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        self._shutdown_event.set()
        if cancel_pending:
            with self._lock:
                for task in self._tasks.values():
                    if task.status == TaskStatus.PENDING:
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.utcnow()
                        self._stats["total_cancelled"] += 1
        if wait:
            for w in self._workers:
                w.join(timeout=10)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def wait_for_completion(
        self,
        task_ids: List[str],
        timeout: Optional[float] = None,
    ) -> List[AsyncTask]:
        deadline = None if timeout is None else time.monotonic() + timeout
        pending = set(task_ids)
        results: list[AsyncTask] = []
        while pending:
            if deadline is not None and time.monotonic() >= deadline:
                break
            with self._lock:
                done = [
                    tid for tid in pending
                    if tid in self._tasks
                    and self._tasks[tid].status
                    in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT)
                ]
            for tid in done:
                pending.discard(tid)
                task = self.get_task(tid)
                if task:
                    results.append(task)
            if pending:
                time.sleep(0.05)
        return results


class ThreadPoolManager:
    def __init__(
        self,
        max_workers: Optional[int] = None,
        thread_name_prefix: str = "CalcWorker",
    ) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._lock = threading.Lock()
        self._stats: dict[str, Any] = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "max_workers": max_workers,
            "thread_name_prefix": thread_name_prefix,
        }
        self._futures: dict[int, Any] = {}

    def run_in_thread(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        fut = self._executor.submit(fn, *args, **kwargs)
        fid = id(fut)
        with self._lock:
            self._futures[fid] = fut
            self._stats["total_submitted"] += 1
        try:
            result = fut.result()
            with self._lock:
                self._stats["total_completed"] += 1
            return result
        except Exception as e:
            with self._lock:
                self._stats["total_failed"] += 1
            if _error_handler_available:
                get_error_handler().handle_error(
                    component="thread_pool",
                    message=f"Thread execution failed: {e}",
                    severity=ErrorSeverity.ERROR,
                    exception=e,
                )
            raise
        finally:
            with self._lock:
                self._futures.pop(fid, None)

    def run_batch(
        self,
        fns: Sequence[Callable],
        max_concurrent: Optional[int] = None,
    ) -> List[Any]:
        submitted = [self._executor.submit(fn) for fn in fns]
        with self._lock:
            self._stats["total_submitted"] += len(submitted)
        results: list[Any] = []
        for fut in as_completed(submitted):
            try:
                results.append(fut.result())
                with self._lock:
                    self._stats["total_completed"] += 1
            except Exception as e:
                results.append(e)
                with self._lock:
                    self._stats["total_failed"] += 1
                if _error_handler_available:
                    get_error_handler().handle_error(
                        component="thread_pool",
                        message=f"Batch task failed: {e}",
                        severity=ErrorSeverity.ERROR,
                        exception=e,
                    )
        return results

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)


class ProcessPoolManager:
    def __init__(self, max_workers: Optional[int] = None) -> None:
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._stats: dict[str, Any] = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "max_workers": max_workers,
        }
        self._futures: dict[int, Any] = {}

    def run_in_process(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        fut = self._executor.submit(fn, *args, **kwargs)
        fid = id(fut)
        with self._lock:
            self._futures[fid] = fut
            self._stats["total_submitted"] += 1
        try:
            result = fut.result()
            with self._lock:
                self._stats["total_completed"] += 1
            return result
        except Exception as e:
            with self._lock:
                self._stats["total_failed"] += 1
            if _error_handler_available:
                get_error_handler().handle_error(
                    component="process_pool",
                    message=f"Process execution failed: {e}",
                    severity=ErrorSeverity.ERROR,
                    exception=e,
                )
            raise
        finally:
            with self._lock:
                self._futures.pop(fid, None)

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)


class _TimeoutContext:
    def __init__(self, seconds: float) -> None:
        self._seconds = seconds
        self._deadline = time.monotonic() + seconds

    def __enter__(self) -> "_TimeoutContext":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        if exc_type is not None:
            return False
        if time.monotonic() > self._deadline:
            raise TimeoutError(f"Operation timed out after {self._seconds}s")
        return None

    @property
    def remaining(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    @property
    def expired(self) -> bool:
        return time.monotonic() > self._deadline


class _RetryContext:
    def __init__(self, max_retries: int, delay: float) -> None:
        self._max_retries = max_retries
        self._delay = delay
        self._attempt = 0

    def __enter__(self) -> "_RetryContext":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        if exc_type is None:
            return None
        self._attempt += 1
        if self._attempt < self._max_retries:
            logger.warning(
                "Retry attempt %d/%d after error: %s",
                self._attempt,
                self._max_retries,
                exc_val,
            )
            time.sleep(self._delay)
            return True
        if _error_handler_available:
            get_error_handler().handle_error(
                component="async_context",
                message=f"Retry exhausted after {self._max_retries} attempts: {exc_val}",
                severity=ErrorSeverity.ERROR,
            )
        return False


def async_timeout(seconds: float) -> _TimeoutContext:
    return _TimeoutContext(seconds)


def async_retry(max_retries: int, delay: float) -> _RetryContext:
    return _RetryContext(max_retries, delay)


class _WorkflowStep:
    def __init__(
        self,
        name: str,
        fn: Callable,
        depends_on: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.name = name
        self.fn = fn
        self.depends_on = depends_on or []
        self.timeout = timeout


class WorkflowOrchestrator:
    def __init__(self, async_executor: AsyncExecutor) -> None:
        self._executor = async_executor
        self._workflows: dict[str, dict] = {}
        self._lock = threading.Lock()

    def define_workflow(self, steps: List[dict]) -> str:
        workflow_id = str(uuid.uuid4())
        parsed: list[_WorkflowStep] = []
        for s in steps:
            parsed.append(
                _WorkflowStep(
                    name=s["name"],
                    fn=s["fn"],
                    depends_on=s.get("depends_on", []),
                    timeout=s.get("timeout"),
                )
            )
        with self._lock:
            self._workflows[workflow_id] = {
                "steps": parsed,
                "status": "defined",
                "results": {},
                "errors": {},
                "created_at": datetime.utcnow(),
            }
        return workflow_id

    def execute_workflow(
        self,
        workflow_id: str,
        initial_params: Optional[dict] = None,
    ) -> dict:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                raise ValueError(f"Workflow {workflow_id} not found")
            wf["status"] = "running"

        steps: list[_WorkflowStep] = wf["steps"]
        step_map = {s.name: s for s in steps}
        completed: dict[str, Any] = dict(initial_params or {})
        errors: dict[str, str] = {}
        ordered: list[_WorkflowStep] = []
        remaining = set(step_map.keys())

        dep_graph: dict[str, set[str]] = {}
        for s in steps:
            dep_graph[s.name] = set(s.depends_on)

        while remaining:
            ready = [
                n for n in remaining
                if dep_graph[n].issubset(set(completed.keys()) | set(errors.keys()))
            ]
            if not ready:
                for n in remaining:
                    for d in dep_graph[n]:
                        if d not in step_map:
                            errors[n] = f"Dependency '{d}' not found"
                break
            for name in ready:
                remaining.discard(name)
                ordered.append(step_map[name])

        for step in ordered:
            if step.name in errors:
                continue
            fn_kwargs = {k: v for k, v in completed.items() if k in step.depends_on}
            try:
                result = step.fn(**fn_kwargs) if fn_kwargs else step.fn()
                completed[step.name] = result
            except Exception as e:
                err_msg = str(e)
                errors[step.name] = err_msg
                if _error_handler_available:
                    get_error_handler().handle_error(
                        component="workflow_orchestrator",
                        message=f"Workflow step '{step.name}' failed: {err_msg}",
                        severity=ErrorSeverity.ERROR,
                        exception=e,
                    )

        with self._lock:
            wf["status"] = "completed" if not errors else "failed"
            wf["results"] = completed
            wf["errors"] = errors
            wf["completed_at"] = datetime.utcnow()

        return {
            "workflow_id": workflow_id,
            "status": wf["status"],
            "results": completed,
            "errors": errors,
        }

    def get_workflow_status(self, workflow_id: str) -> Optional[dict]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return None
            return {
                "workflow_id": workflow_id,
                "status": wf["status"],
                "results": dict(wf["results"]),
                "errors": dict(wf["errors"]),
                "created_at": wf["created_at"],
                "completed_at": wf.get("completed_at"),
            }


@contextmanager
def _timeout(seconds: float):
    import signal

    def _handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds}s")

    if hasattr(signal, "SIGALRM"):
        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(int(seconds))
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    else:
        yield


_async_executor: Optional[AsyncExecutor] = None
_thread_pool: Optional[ThreadPoolManager] = None
_process_pool: Optional[ProcessPoolManager] = None
_singleton_lock = threading.Lock()


def get_async_executor(
    max_workers: int = 4,
    max_queue_size: int = 1000,
) -> AsyncExecutor:
    global _async_executor
    if _async_executor is None:
        with _singleton_lock:
            if _async_executor is None:
                _async_executor = AsyncExecutor(
                    max_workers=max_workers,
                    max_queue_size=max_queue_size,
                )
    return _async_executor


def get_thread_pool_manager(
    max_workers: Optional[int] = None,
    thread_name_prefix: str = "CalcWorker",
) -> ThreadPoolManager:
    global _thread_pool
    if _thread_pool is None:
        with _singleton_lock:
            if _thread_pool is None:
                _thread_pool = ThreadPoolManager(
                    max_workers=max_workers,
                    thread_name_prefix=thread_name_prefix,
                )
    return _thread_pool


def get_process_pool_manager(
    max_workers: Optional[int] = None,
) -> ProcessPoolManager:
    global _process_pool
    if _process_pool is None:
        with _singleton_lock:
            if _process_pool is None:
                _process_pool = ProcessPoolManager(
                    max_workers=max_workers,
                )
    return _process_pool
