from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict, model_validator, PositiveFloat, PositiveInt
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os

SOLVENT_DB_PATH = Path(__file__).with_name("solvents_db.json")


def _load_db() -> Dict[str, Any]:
    if not SOLVENT_DB_PATH.exists():
        return {}
    with SOLVENT_DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(db: Dict[str, Any]) -> None:
    SOLVENT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SOLVENT_DB_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(SOLVENT_DB_PATH)


def _next_id(db: Dict[str, Any]) -> int:
    numeric_keys = [int(k) for k in db.keys() if str(k).isdigit()]
    return (max(numeric_keys) + 1) if numeric_keys else 1


class Solvent(BaseModel):
    existing: bool = Field(False)
    id: Optional[PositiveInt] = Field(default=None)
    name: Optional[str] = Field(default=None)
    density_g_ml: Optional[PositiveFloat] = None
    notes: Optional[str] = None

    model_config = ConfigDict(validate_assignment=True, revalidate_instances="never")

    @model_validator(mode="after")
    def _create_or_load(self) -> Solvent:
        db = _load_db()
        if self.existing:
            if self.id is None:
                raise ValueError("existing=True requires 'id'.")
            rec = db.get(str(self.id))
            if rec is None:
                raise ValueError(f"No solvent with id={self.id} in {SOLVENT_DB_PATH}.")
            for field, value in rec.items():
                if field in type(self).model_fields:
                    object.__setattr__(self, field, value)
                return self
        if self.id is None:
            self.id = _next_id(db)
        else:
            if str(self.id) in db:
                raise ValueError(f"id={self.id} already exists.")
        if not self.name:
            raise ValueError("'name' is required to create a new solvent.")
        db[str(self.id)] = self._record_dict()
        _save_db(db)
        return self

    def _record_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "density_g_ml": self.density_g_ml,
            "notes": self.notes,
        }

    def save(self) -> None:
        if self.id is None:
            raise ValueError("Cannot save without an id.")
        db = _load_db()
        db[str(self.id)] = self._record_dict()
        _save_db(db)

    @classmethod
    def load(cls, id: int) -> Solvent:
        db = _load_db()
        rec = db.get(str(id))
        if rec is None:
            raise ValueError(f"No solvent with id={id} in {SOLVENT_DB_PATH}.")
        return cls(**rec, existing=True)

    @classmethod
    def all(cls) -> Dict[int, Solvent]:
        db = _load_db()
        out: Dict[int, Solvent] = {}
        for k, v in db.items():
            if str(k).isdigit():
                out[int(k)] = cls(**v, existing=True)
        return out


if __name__ == "__main__":
    print("Creating a new solvent...")
    acn = Solvent(name="Acetonitrile", density_g_ml=0.786, notes="HPLC grade")
    print(f"Created solvent: {acn}")

    print("\nLoading the same solvent by ID...")
    loaded_acn = Solvent(id=acn.id, existing=True)
    print(f"Loaded solvent: {loaded_acn}")

    print("\nModifying the solvent and saving...")
    loaded_acn.notes = "Anhydrous grade"
    loaded_acn.save()
    print(f"Updated solvent: {loaded_acn}")

    print("\nListing all solvents in database:")
    for sid, solvent in Solvent.all().items():
        print(f"  ID={sid}: {solvent.name}, density={solvent.density_g_ml}, notes={solvent.notes}")