"""Assemble evaluator payloads from .json config + .py / .prompt criteria files.

The criteria that HoneyHive stores is a STRING of source code (or, for an LLM
metric, a prompt template). Keeping that source in a real .py file means it is
lintable, diffable and testable; this module turns it back into the JSON payload
the API expects.

It also validates against the evaluator sandbox BEFORE anything is uploaded. That
matters because a sandbox failure is silent per-span — the metric simply produces
no score — so a broken evaluator looks identical to a quiet day.
"""

import ast
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent

# Builtins the sandbox does not provide. Verified via POST /v1/metrics/run.
FORBIDDEN_NAMES = {
    "any": "NameError in sandbox — use an explicit for-loop",
    "all": "NameError in sandbox — use an explicit for-loop",
    "type": "NameError in sandbox — use isinstance(x, str)",
    "enumerate": "NameError in sandbox — track an index manually",
    "hasattr": "NameError in sandbox",
    "getattr": "NameError in sandbox",
    "list": "the name `list` raises TypeError in sandbox — build [] literals",
    "tuple": "the name `tuple` raises TypeError in sandbox",
}


class EvaluatorError(Exception):
    """Raised when an evaluator would fail on the platform."""


def _extract_function(source: str, entrypoint: str, path: Path) -> str:
    """Return the source of `entrypoint`, validated against the sandbox rules.

    Only the function is returned. Module-level imports, docstrings and
    TYPE_CHECKING stubs stay local — they exist for the editor, not the platform.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise EvaluatorError(f"{path.name}: invalid Python — {exc}") from exc

    fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == entrypoint
        ),
        None,
    )
    if fn is None:
        defined = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        raise EvaluatorError(
            f"{path.name}: no top-level function named {entrypoint!r}. "
            f"Found: {defined or 'none'}"
        )

    # The sandbox calls the function with no arguments and injects event data as
    # globals. A declared parameter raises TypeError on every event.
    args = fn.args
    n_args = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    if n_args or args.vararg or args.kwarg:
        names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
        raise EvaluatorError(
            f"{path.name}: {entrypoint}() must take NO arguments, got {names}. "
            "The sandbox injects `metadata`, `event`, `inputs`, `outputs` as "
            "globals; a parameter raises TypeError on every event."
        )

    problems = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            problems.append(f"line {node.lineno}: {node.id}() — {FORBIDDEN_NAMES[node.id]}")
        # isinstance(x, (a, b)) — the tuple-of-types form raises TypeError
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Tuple)
        ):
            problems.append(
                f"line {node.lineno}: isinstance(x, (...)) — the tuple form raises "
                "TypeError in sandbox; test one type at a time"
            )
    if problems:
        raise EvaluatorError(
            f"{path.name}: uses constructs the evaluator sandbox rejects:\n    "
            + "\n    ".join(problems)
        )

    segment = ast.get_source_segment(source, fn)
    if not segment:
        raise EvaluatorError(f"{path.name}: could not extract {entrypoint} source")
    return segment.rstrip() + "\n"


def load(config_path: Path) -> dict:
    """Build the API payload for one evaluator from its .json config."""
    cfg = json.loads(config_path.read_text())

    for required in ("name", "type", "criteria_file"):
        if required not in cfg:
            raise EvaluatorError(f"{config_path.name}: missing {required!r}")

    criteria_path = config_path.parent / cfg.pop("criteria_file")
    if not criteria_path.exists():
        raise EvaluatorError(f"{config_path.name}: {criteria_path.name} not found")

    source = criteria_path.read_text()
    entrypoint = cfg.pop("entrypoint", None)

    if cfg["type"] == "PYTHON":
        if not entrypoint:
            raise EvaluatorError(f"{config_path.name}: PYTHON needs 'entrypoint'")
        cfg["criteria"] = _extract_function(source, entrypoint, criteria_path)
    else:
        # LLM metric: the criteria is a prompt template, uploaded verbatim.
        if "{{" not in source:
            raise EvaluatorError(
                f"{criteria_path.name}: prompt has no {{{{ }}}} template variables"
            )
        cfg["criteria"] = source

    if cfg.get("sampling_percentage") != 100:
        raise EvaluatorError(
            f"{config_path.name}: sampling_percentage is "
            f"{cfg.get('sampling_percentage')}, expected 100. The platform default "
            "of 10 silently drops most events."
        )

    return cfg


def load_all() -> list[tuple[Path, dict]]:
    """Every evaluator in this directory, sorted by filename."""
    return [(p, load(p)) for p in sorted(EVAL_DIR.glob("*.json"))]
