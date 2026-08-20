from app.db.session import engine
from sqlalchemy import text

with engine.connect() as connection:

    print("\n========== CONSTRAINTS ==========\n")

    result = connection.execute(
        text("""
            SELECT
                conname,
                contype,
                pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'menu_cycles'::regclass
            ORDER BY conname
        """)
    )

    for row in result:
        print(row)

    print("\n========== INDEXES ==========\n")

    result = connection.execute(
        text("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = 'menu_cycles'
            ORDER BY indexname
        """)
    )

    for row in result:
        print(row)