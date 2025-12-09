from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# DB file inside Codes:
sqlite_path = BASE_DIR / "liquid_handling.db"
sqlite_url = f"sqlite:///{sqlite_path}"
engine = create_engine(sqlite_url, echo=False)

def get_session() -> Session:
    return Session(engine)

def create_db_and_tables() -> None:
    # import models here so they are registered in SQLModel.metadata
    from .Syringe import Syringe
    from .Solvent import Solvent
    from .SyringeSolventLink import SyringeSolventLink

    SQLModel.metadata.create_all(engine)
