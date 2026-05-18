from __future__ import annotations

from pathlib import Path


_MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def migration_files() -> tuple[Path, ...]:
    return tuple(sorted(_MIGRATIONS_DIR.glob("*.sql")))


def read_migration(filename: str) -> str:
    migrations_dir = _MIGRATIONS_DIR.resolve()
    migration_path = (migrations_dir / filename).resolve()
    if migration_path.parent != migrations_dir or migration_path.suffix != ".sql":
        raise ValueError(f"Invalid migration filename: {filename}")

    return migration_path.read_text(encoding="utf-8")


__all__ = ["migration_files", "read_migration"]
