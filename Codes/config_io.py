from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar, Type

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"

def load_model(cls: Type[T], name: str) -> T:
    subdir = cls.__name__.lower() + "s"
    path = CONFIG_DIR / subdir / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return cls.model_validate(data)

def save_model(model: BaseModel, name: str) -> Path:
    """
    Save a Pydantic model to Codes/config/<models>/<name>.json
    Folder is derived from the model class name.
    """
    subdir = model.__class__.__name__.lower() + "s"
    out_dir = CONFIG_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / f"{name}.json"
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    return path

def delete_model(model_cls: type[BaseModel], name: str) -> None:
    subdir = model_cls.__name__.lower() + "s"
    path = CONFIG_DIR / subdir / f"{name}.json"

    if not path.is_file():
        raise FileNotFoundError(f"No such config file: {path}")

    path.unlink()
