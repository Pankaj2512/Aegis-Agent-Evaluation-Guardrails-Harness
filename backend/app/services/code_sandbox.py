"""Restricted Python execution for the Code node (n8n-style).

Runs user code in a short-lived subprocess so infinite loops and CPU-bound
spin can be hard-killed after ``CODE_TIMEOUT_SECONDS``. Concurrent capacity is
capped so a few runaway nodes cannot exhaust the process.
"""

from __future__ import annotations

import ast
import json
import multiprocessing as mp
import os
import queue
from typing import Any

MAX_CODE_LENGTH = 4000
CODE_TIMEOUT_SECONDS = 5.0
_SANDBOX_MAX_WORKERS = max(1, int(os.environ.get("CODE_SANDBOX_MAX_WORKERS", "8")))
# Bound concurrent sandboxes; slots are held only for the duration of a run.
_sandbox_slots = mp.BoundedSemaphore(_SANDBOX_MAX_WORKERS)

FORBIDDEN_NAMES = frozenset(
    {
        "open",
        "exec",
        "eval",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "help",
        "breakpoint",
        "memoryview",
        "bytearray",
    }
)

SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "round": round,
    "sum": sum,
    "sorted": sorted,
    "enumerate": enumerate,
    "zip": zip,
    "range": range,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "True": True,
    "False": False,
    "None": None,
}


class _SafeJsonNamespace:
    """Expose only loads/dumps — never the stdlib module (avoids codecs.sys escape)."""

    @staticmethod
    def loads(value: str, *args: Any, **kwargs: Any) -> Any:
        return json.loads(value, *args, **kwargs)

    @staticmethod
    def dumps(value: Any, *args: Any, **kwargs: Any) -> str:
        return json.dumps(value, *args, **kwargs)


class _SafetyVisitor(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        raise ValueError("import statements are not allowed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise ValueError("import statements are not allowed")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
            raise ValueError(f"'{node.func.id}' is not allowed in code nodes")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise ValueError("dunder attribute access is not allowed")
        if isinstance(node.value, ast.Name) and node.value.id == "json":
            if node.attr not in {"loads", "dumps"}:
                raise ValueError("only json.loads and json.dumps are allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            raise ValueError(f"'{node.id}' is not allowed in code nodes")
        self.generic_visit(node)


def validate_code_safety(code: str) -> None:
    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(f"code exceeds {MAX_CODE_LENGTH} characters")
    tree = ast.parse(code, mode="exec")
    _SafetyVisitor().visit(tree)


def _execute_code(code: str, local_vars: dict[str, Any]) -> None:
    exec(
        code,
        {"__builtins__": SAFE_BUILTINS, "json": _SafeJsonNamespace()},
        local_vars,
    )


def _subprocess_worker(
    code: str,
    local_vars: dict[str, Any],
    result_queue: mp.Queue,
) -> None:
    """Child process entry: run code and put (ok, payload) on the queue."""
    try:
        _execute_code(code, local_vars)
        result = local_vars.get("result")
        result_queue.put(("ok", result))
    except Exception as exc:  # noqa: BLE001 — surface to parent
        result_queue.put(("err", f"{type(exc).__name__}: {exc}"))


def run_sandboxed_code(code: str, context: dict[str, Any], node_input: str) -> str:
    validate_code_safety(code)
    local_vars: dict[str, Any] = {
        "input": context.get("input", {}),
        "steps": context.get("steps", {}),
        "last_output": context.get("last_output", node_input),
        "memory": context.get("memory", {}),
        "result": None,
    }

    # Reject immediately when the pool is saturated rather than queueing forever.
    acquired = _sandbox_slots.acquire(block=False)
    if not acquired:
        raise ValueError(
            f"Code sandbox is at capacity ({_SANDBOX_MAX_WORKERS} concurrent); "
            "retry after other Code nodes finish."
        )

    try:
        # Spawn context avoids inheriting the parent's threads/locks (macOS default
        # can be fork, which is unsafe under threaded FastAPI).
        ctx = mp.get_context("spawn")
        result_queue: mp.Queue = ctx.Queue(maxsize=1)
        proc = ctx.Process(
            target=_subprocess_worker,
            args=(code, local_vars, result_queue),
            daemon=True,
        )
        proc.start()
        proc.join(timeout=CODE_TIMEOUT_SECONDS)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
            raise ValueError(
                f"Code execution timed out after {int(CODE_TIMEOUT_SECONDS)} seconds"
            )

        try:
            status, payload = result_queue.get_nowait()
        except queue.Empty as exc:
            if proc.exitcode not in (0, None):
                raise ValueError(
                    f"Code execution failed in sandbox (exit {proc.exitcode})"
                ) from exc
            raise ValueError("Code execution produced no result") from exc

        if status == "err":
            raise ValueError(str(payload))

        result = payload
        if result is None:
            return str(node_input)
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return str(result)
    finally:
        _sandbox_slots.release()
