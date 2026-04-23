from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    raw_dir: Path
    canonical_dir: Path
    derived_dir: Path
    db_path: Path

    @classmethod
    def from_root(cls, root: Path) -> "AppPaths":
        data_dir = root / "data"
        return cls(
            root=root,
            data_dir=data_dir,
            raw_dir=data_dir / "raw",
            canonical_dir=data_dir / "canonical",
            derived_dir=data_dir / "derived",
            db_path=data_dir / "app.db",
        )

    def ensure(self) -> None:
        for path in [
            self.data_dir,
            self.raw_dir,
            self.raw_dir / "whitehouse",
            self.raw_dir / "rev",
            self.raw_dir / "media",
            self.canonical_dir,
            self.canonical_dir / "transcripts",
            self.canonical_dir / "datasets",
            self.derived_dir,
            self.derived_dir / "features",
            self.derived_dir / "datasets",
            self.derived_dir / "transcripts",
            self.derived_dir / "evidence",
        ]:
            path.mkdir(parents=True, exist_ok=True)


def default_paths() -> AppPaths:
    root = Path(__file__).resolve().parent.parent
    return AppPaths.from_root(root)
