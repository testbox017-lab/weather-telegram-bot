"""Проверка для Docker HEALTHCHECK: жив ли бот внутри (см. health.heartbeat_loop).

Код 0 — всё в порядке, 1 — проблема (текст попадает в docker inspect, State.Health.Log).
"""
import os
import sys
from pathlib import Path

from health import HEARTBEAT_FILE, heartbeat_problem


def main() -> int:
    path = Path(os.getenv("DATA_DIR") or Path(__file__).parent) / HEARTBEAT_FILE
    problem = heartbeat_problem(path)
    print(problem or "ok")
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
