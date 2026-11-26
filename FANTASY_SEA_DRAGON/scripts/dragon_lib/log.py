"""Logging and milestone bookkeeping.

Every milestone script runs inside ``MilestoneRun`` which

* streams log lines to stdout and ``reports/pipeline.log``;
* records outputs, validation results and errors;
* writes ``reports/milestones/<ID>.json``;
* appends a section to ``reports/milestone_log.md``;
* updates ``reports/pipeline_state.json`` (latest .blend per milestone).

A milestone is only marked COMPLETE when no validation check FAILed and no
exception escaped.  Exceptions are re-raised so the process exit code is
non-zero – failures are never silently ignored.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
import time
import traceback
from pathlib import Path

from . import config

_LOGGER = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    config.DIRS["reports"].mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger("fsd")
    lg.setLevel(logging.INFO)
    lg.propagate = False
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(config.PIPELINE_LOG, encoding="utf-8")
    fh.setFormatter(fmt)
    lg.addHandler(sh)
    lg.addHandler(fh)
    _LOGGER = lg
    return lg


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def load_state() -> dict:
    if config.STATE_JSON.exists():
        return json.loads(config.STATE_JSON.read_text())
    return {"milestones": {}}


def save_state(state: dict) -> None:
    config.STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_JSON.write_text(json.dumps(state, indent=2))


def latest_blend(milestone_id: str) -> Path:
    """Path of the most recent .blend saved by *milestone_id* (must exist)."""
    st = load_state()["milestones"].get(milestone_id)
    if not st or not st.get("blend"):
        raise RuntimeError(f"Milestone {milestone_id} has no saved project – run it first.")
    p = config.ROOT / st["blend"]
    if not p.exists():
        raise FileNotFoundError(p)
    return p


def rel(p) -> str:
    try:
        return str(Path(p).resolve().relative_to(config.ROOT))
    except ValueError:
        return str(p)


class MilestoneRun:
    """Context manager recording one milestone execution."""

    def __init__(self, milestone_id: str, title: str, scripts: list[str]):
        self.id = milestone_id
        self.title = title
        self.scripts = scripts
        self.log = get_logger()
        self.outputs: dict[str, list[str]] = {}
        self.checks: list[dict] = []
        self.notes: list[str] = []
        self.assumptions: list[str] = []
        self.metrics: dict = {}
        self.blend: str | None = None
        self.status = "RUNNING"

    # ---- recording helpers -------------------------------------------------
    def output(self, kind: str, path) -> None:
        self.outputs.setdefault(kind, []).append(rel(path))

    def add_checks(self, checks: list[dict]) -> None:
        for c in checks:
            self.checks.append(c)
            lvl = {"PASS": logging.INFO, "WARNING": logging.WARNING}.get(c["status"], logging.ERROR)
            self.log.log(lvl, "  [%s] %s: %s", c["status"], c["check"], c.get("detail", ""))

    def note(self, text: str) -> None:
        self.notes.append(text)
        self.log.info("NOTE: %s", text)

    def assume(self, text: str) -> None:
        self.assumptions.append(text)
        self.log.info("ASSUMPTION: %s", text)

    # ---- context protocol --------------------------------------------------
    def __enter__(self):
        self.t0 = time.time()
        self.started = _now()
        self.log.info("=" * 72)
        self.log.info("%s – %s  (quality=%s)", self.id, self.title, config.QUALITY)
        self.log.info("=" * 72)
        return self

    def __exit__(self, exc_type, exc, tb):
        dur = time.time() - self.t0
        error = None
        if exc is not None:
            self.status = "FAILED"
            error = "".join(traceback.format_exception(exc_type, exc, tb))
            self.log.error("Milestone %s raised:\n%s", self.id, error)
        elif any(c["status"] == "FAIL" for c in self.checks):
            self.status = "FAILED_VALIDATION"
        elif any(c["status"] == "WARNING" for c in self.checks):
            self.status = "COMPLETE_WITH_WARNINGS"
        else:
            self.status = "COMPLETE"

        record = dict(id=self.id, title=self.title, scripts=self.scripts,
                      quality=config.QUALITY, started=self.started,
                      finished=_now(), duration_s=round(dur, 2),
                      status=self.status, blend=self.blend,
                      outputs=self.outputs, metrics=self.metrics,
                      checks=self.checks, notes=self.notes,
                      assumptions=self.assumptions, error=error)
        mdir = config.DIRS["reports"] / "milestones"
        mdir.mkdir(parents=True, exist_ok=True)
        (mdir / f"{self.id}.json").write_text(json.dumps(record, indent=2, default=str))

        state = load_state()
        state["milestones"][self.id] = dict(
            title=self.title, status=self.status, blend=self.blend,
            finished=record["finished"], quality=config.QUALITY)
        save_state(state)
        self._append_markdown(record)
        self.log.info("%s finished: %s (%.1fs)", self.id, self.status, dur)
        if self.status == "FAILED_VALIDATION" and exc is None:
            raise SystemExit(f"{self.id}: validation FAILED – see reports/milestones/{self.id}.json")
        return False  # re-raise exceptions

    def _append_markdown(self, r: dict) -> None:
        counts = {k: sum(1 for c in r["checks"] if c["status"] == k)
                  for k in ("PASS", "WARNING", "FAIL")}
        lines = [f"\n## {r['id']} – {r['title']}",
                 f"* **Status:** {r['status']}  ",
                 f"* **Finished:** {r['finished']} ({r['duration_s']} s, quality `{r['quality']}`)  ",
                 f"* **Scripts:** {', '.join(r['scripts'])}  ",
                 f"* **Project file:** `{r['blend']}`  ",
                 f"* **Checks:** {counts['PASS']} PASS / {counts['WARNING']} WARNING / {counts['FAIL']} FAIL  "]
        for k, v in r["metrics"].items():
            lines.append(f"* {k}: {v}  ")
        if r["assumptions"]:
            lines.append("* **Assumptions:**")
            lines += [f"  * {a}" for a in r["assumptions"]]
        if r["notes"]:
            lines.append("* **Notes:**")
            lines += [f"  * {n}" for n in r["notes"]]
        if r["error"]:
            lines.append("```\n" + r["error"][-1500:] + "\n```")
        if not config.MILESTONE_LOG_MD.exists():
            config.MILESTONE_LOG_MD.write_text("# Fantasy Sea Dragon – Milestone Log\n")
        with open(config.MILESTONE_LOG_MD, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def check(name: str, status: str, detail: str = "", value=None, threshold=None) -> dict:
    assert status in ("PASS", "WARNING", "FAIL"), status
    return dict(check=name, status=status, detail=detail, value=value, threshold=threshold)
