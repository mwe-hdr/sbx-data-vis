import pyodbc
import pandas as pd
import os

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

print("🔌 Connecting to SQL Server...")

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=OMAPI-HCADB19;"
    "DATABASE=CLIENT;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

print("✅ Connected to database")

# --------------------------------------------------
# EXTRACT + SAVE TO CSV
# --------------------------------------------------

query = "SELECT * FROM ecu.emergency_new"

print("⬇️ Pulling data from table...")
df = pd.read_sql(query, conn)

print(f"✅ Retrieved {len(df):,} rows")

# Ensure output directory exists
output_dir = os.path.join(".", "data", "input")
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "ecu_emergency_export.csv")

df.to_csv(output_file, index=False)

print(f"💾 Data exported to {output_file}")

# --------------------------------------------------
# CLEANUP
# --------------------------------------------------

conn.close()
print("🔒 Connection closed")