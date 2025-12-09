from .db import create_db_and_tables
from .Syringe import Syringe


def main():
    create_db_and_tables()
    s = Syringe.get_by_id(1)
    if s:
        print(s.name, s.theoretical_correlation_factor)
    else:
        print("No syringe with id=1 in the database.")


if __name__ == "__main__":
    main()
