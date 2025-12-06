from Syringe import Syringe
from db import create_db_and_tables

if __name__ == "__main__":
    create_db_and_tables()
    s = Syringe.get_by_id(1)
    if s:
        print(s.name, s.theoretical_correlation_factor)
