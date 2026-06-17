"""
Filter ADI data to NYC counties and save
"""

import pandas as pd
import os

# Path to your NTA Lookup project
BASE_DIR = r"C:\Users\chorni02\OneDrive - NYU Langone Health\Python\NTA Lookup"

OUTPUT_FOLDER = os.path.join(BASE_DIR, "files")

# Load the downloaded ADI file
#INPUT_FILE = pd.read_csv("files/NY_2023_ADI_Census_Block_Group_v4_0_1.csv")

INPUT_FILE = os.path.join(BASE_DIR, "files/NY_2023_ADI_Census_Block_Group_v4_0_1.csv")
#OUTPUT_FILE = "NY_2023_ADI_Census_Block_Group"
OUTPUT_FILE = "NY_2023_ADI_Census_Block_Group_filtered.csv"  # 👈 note the .csv

# =============================================================================
# Processing
# =============================================================================

# Create files folder if it doesn't exist
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)
    print(f"📁 Created folder: {OUTPUT_FOLDER}")

# Load the downloaded ADI file
print(f"📂 Loading: {INPUT_FILE}")
adi_data = pd.read_csv(INPUT_FILE)


# Define NYC county FIPS prefixes
nyc_fips_prefixes = ['36005', '36047', '36061', '36081', '36085']

# Ensure FIPS is string and extract county portion (first 5 digits)

adi_data['FIPS'] = adi_data['FIPS'].astype(str).str.zfill(12)  # Pad to 12 digits
adi_data['county_fips'] = adi_data['FIPS'].str[:5]

# Filter to NYC only
adi_nyc = adi_data[adi_data['county_fips'].isin(nyc_fips_prefixes)].copy()

# Add borough names for clarity
borough_map = {
    '36005': 'Bronx',
    '36047': 'Brooklyn',
    '36061': 'Manhattan',
    '36081': 'Queens',
    '36085': 'Staten Island'
}
adi_nyc['borough'] = adi_nyc['county_fips'].map(borough_map)

# Display summary
print(f"\n📊 Summary:")
print(f"   Original records: {len(adi_data):,}")
print(f"   NYC records: {len(adi_nyc):,}")
print(f"\n   Records by borough:")
for borough, count in adi_nyc['borough'].value_counts().items():
    print(f"      {borough}: {count:,}")

# Drop the helper column if not needed
#adi_nyc = adi_nyc.drop(columns=['county_fips'])


# Save to new CSV file
output_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)
adi_nyc.to_csv(output_path, index=False)

print(f"\n✅ Saved filtered file to: {output_path}")
print(f"   File size: {os.path.getsize(output_path) / 1024:.1f} KB")