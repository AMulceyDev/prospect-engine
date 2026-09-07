from dataclasses import dataclass


@dataclass
class _ProgressState:
    task: str = ""    # "websites" | "analyze" | ""
    current: int = 0
    total: int = 0

    def set(self, task: str, current: int, total: int) -> None:
        self.task = task
        self.current = current
        self.total = total

    def reset(self) -> None:
        self.task = ""
        self.current = 0
        self.total = 0

    def to_dict(self) -> dict:
        return {"task": self.task, "current": self.current, "total": self.total}


# Module-level singleton — Python's GIL makes int/str assignment atomic enough
# for this single-writer / many-readers use case.
progress = _ProgressState()
