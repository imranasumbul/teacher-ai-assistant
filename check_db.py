# check_db.py
# Quick script to verify database and tables

from db import init_db, get_db_url
from sqlalchemy import create_engine, inspect

print("🔄 Initializing database...")
init_db()

# Create engine to inspect DB
engine = create_engine(get_db_url())
inspector = inspect(engine)

print("\n✅ DATABASE CONNECTED")
print("📁 DB file:", get_db_url())

# List tables
tables = inspector.get_table_names()

print("\n📊 TABLES FOUND:")
if not tables:
    print("❌ No tables found!")
else:
    for table in tables:
        print(f" - {table}")

# Show columns for each table
print("\n📋 TABLE STRUCTURE:")
for table in tables:
    print(f"\n🔹 {table}")
    columns = inspector.get_columns(table)
    for col in columns:
        print(f"   {col['name']} ({col['type']})")

print("\n🎉 DB CHECK COMPLETE")