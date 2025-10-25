from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict, model_validator, PositiveFloat, PositiveInt
from typing import Optional, Dict, Any
from pathlib import Path
import json


# Simple file-based registry for solvents. You can version-control this JSON in GitHub.
SOLVENT_DB_PATH = Path("./solvents_db.json")


def _load_db() -> Dict[str, Any]:
    if SOLVENT_DB_PATH.exists():
        try:
            return json.loads(SOLVENT_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt file fallback
            return {}
    return {}


def _save_db(db: Dict[str, Any]) -> None:
    SOLVENT_DB_PATH.write_text(json.dumps(db, indent=2, sort_keys=True), encoding="utf-8")


def _next_id(db: Dict[str, Any]) -> int:
    # IDs are stored as strings in JSON keys for stability
    if not db:
        return 1
    try:
        return max(int(k) for k in db.keys()) + 1
    except ValueError:
        # If keys are not numeric, rebase to 1
        return 1


class Solvent(BaseModel):
    """Solvent model with optional persistence.

    Usage patterns:
      # Create a NEW solvent → auto-assign id and persist
      s = Solvent(name="Acetonitrile", existing=False)

      # Load an EXISTING solvent from db by id
      s = Solvent(id=3, existing=True)

      # Update and persist
      s.name = "ACN"
      s.save()
    """

    # Toggle: set existing=True to load by id; existing=False (default) to create+persist.
    existing: bool = Field(False, description="If True, load by id from local DB; if False, create and persist.")

    # Identity
    id: Optional[PositiveInt] = Field(default=None, description="Integer ID assigned in local DB")
    name: Optional[str] = Field(default=None, description="Human-readable name (not unique)")

    # Add additional optional metadata fields as needed (density, viscosity, etc.)
    density_g_ml: Optional[PositiveFloat] = None
    notes: Optional[str] = None

    # Validate on assignment so changes can be persisted safely after edits
    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _create_or_load(self) -> Solvent:
        db = _load_db()

        if self.existing:
            # Must have an id; load record and populate fields
            if self.id is None:
                raise ValueError("existing=True requires 'id' to be provided.")
            key = str(self.id)
            rec = db.get(key)
            if rec is None:
                raise ValueError(f"No solvent with id={self.id} in local DB {SOLVENT_DB_PATH}.")
            # Apply stored values (do not overwrite the 'existing' toggle)
            for field, value in rec.items():
                # avoid clobbering None with missing keys
                if field in self.model_fields:
                    setattr(self, field, value)
            return self

        # existing == False → create new if id not supplied; if id supplied and free, use it
        if self.id is None:
            self.id = _next_id(db)
        else:
            if str(self.id) in db:
                raise ValueError(f"id={self.id} already exists. Use existing=True to load, or omit id to auto-assign.")

        # Minimal validation
        if not self.name:
            raise ValueError("Creating a new solvent requires a 'name'.")

        # Persist new record
        db[str(self.id)] = self._record_dict()
        _save_db(db)
        return self

    # --- Convenience methods ---
    def _record_dict(self) -> Dict[str, Any]:
        # Only persist serializable fields (exclude 'existing')
        return {
            "id": self.id,
            "name": self.name,
            "density_g_ml": self.density_g_ml,
            "notes": self.notes,
        }

    def save(self) -> None:
        """Persist current state back to the local JSON DB."""
        if self.id is None:
            raise ValueError("Cannot save solvent without an id.")
        db = _load_db()
        db[str(self.id)] = self._record_dict()
        _save_db(db)

    @classmethod
    def load(cls, id: int) -> Solvent:
        """Explicit loader (alternative to Solvent(id=..., existing=True))."""
        db = _load_db()
        rec = db.get(str(id))
        if rec is None:
            raise ValueError(f"No solvent with id={id} in local DB {SOLVENT_DB_PATH}.")
        return cls(**rec, existing=True)

    @classmethod
    def all(cls) -> Dict[int, Solvent]:
        """Load all solvents from local DB as {id: Solvent}."""
        db = _load_db()
        return {int(k): cls(**v, existing=True) for k, v in db.items()}


if __name__ == "__main__":
    # Example usage to test the Solvent class
    print("Creating a new solvent...")
    acn = Solvent(name="Acetonitrile", density_g_ml=0.786, notes="HPLC grade")
    print(f"Created solvent: {acn}")

    # print("\nLoading the same solvent by ID...")
    # loaded_acn = Solvent(id=acn.id, existing=True)
    # print(f"Loaded solvent: {loaded_acn}")
    #
    # print("\nModifying the solvent and saving...")
    # loaded_acn.notes = "Anhydrous grade"
    # loaded_acn.save()
    # print(f"Updated solvent: {loaded_acn}")
    #
    # print("\nListing all solvents in database:")
    # for sid, solvent in Solvent.all().items():
    #     print(f"  ID={sid}: {solvent.name}, density={solvent.density_g_ml}, notes={solvent.notes}")
    #







