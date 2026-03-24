from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class GuiSetupConfig(BaseModel):
    name: str
    syringe_id: int
    machine: str
    racks: list[str] = Field(default_factory=list)

    @classmethod
    def load_from_path(cls, path: Path) -> "GuiSetupConfig":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    @classmethod
    def load_all_from_dir(cls, directory: Path) -> list[tuple["GuiSetupConfig", Path]]:
        configs: list[tuple["GuiSetupConfig", Path]] = []
        if not directory.exists():
            return configs
        for path in sorted(directory.glob("*.json")):
            configs.append((cls.load_from_path(path), path))
        return configs

    def to_json_text(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2) + "\n"

    def save_to_path(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json_text(), encoding="utf-8")
        return path

    def save_to_dir(self, directory: Path, *, name: str | None = None) -> Path:
        target_name = self.name if name is None else name
        payload = self if target_name == self.name else GuiSetupConfig(
            name=target_name,
            syringe_id=self.syringe_id,
            machine=self.machine,
            racks=list(self.racks),
        )
        return payload.save_to_path(directory / f"{target_name}.json")

    def with_machine_name(self, machine_name: str) -> "GuiSetupConfig":
        return GuiSetupConfig(
            name=self.name,
            syringe_id=self.syringe_id,
            machine=machine_name,
            racks=list(self.racks),
        )

    def with_rack_names(self, rack_names: list[str]) -> "GuiSetupConfig":
        return GuiSetupConfig(
            name=self.name,
            syringe_id=self.syringe_id,
            machine=self.machine,
            racks=list(rack_names),
        )

