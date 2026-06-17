import pandas as pd

# Load your mapping file
df = pd.read_csv('zip_to_nta_mapping.csv')

print("=" * 60)
print("COLUMN NAMES (exact):")
print("=" * 60)
for i, col in enumerate(df.columns):
    print(f"  {i}: '{col}' (length: {len(col)})")

print("\n" + "=" * 60)
print("SAMPLE DATA FOR ZIP 11220:")
print("=" * 60)

# Find ZIP column
zip_col = None
for col in df.columns:
    if 'ZIP' in col.upper() or 'ZCTA' in col.upper():
        zip_col = col
        break

if zip_col:
    print(f"Using ZIP column: '{zip_col}'")
    df[zip_col] = df[zip_col].astype(str).str.strip().str.zfill(5)
    sample = df[df[zip_col] == '11220'].head(3)
    print(sample.to_string())
    
    print("\n" + "=" * 60)
    print("ALL COLUMNS FOR ONE ROW:")
    print("=" * 60)
    if len(sample) > 0:
        for col in df.columns:
            print(f"  '{col}': '{sample.iloc[0][col]}'")