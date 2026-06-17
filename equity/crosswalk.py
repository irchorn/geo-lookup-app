import geopandas as gpd

# Load NTA boundaries
nta_boundaries = gpd.read_file("geofiles/nynta2010.shp")

# Load Census Block Group boundaries (from Census TIGER files)
block_groups = gpd.read_file("geofiles/tl_2020_36_bg.shp")

# Verify columns exist
print("Block Group columns:", block_groups.columns.tolist())
print("NTA columns:", nta_boundaries.columns.tolist())

# Ensure matching CRS
if block_groups.crs != nta_boundaries.crs:
    print(f"Reprojecting block groups from {block_groups.crs} to {nta_boundaries.crs}")
    block_groups = block_groups.to_crs(nta_boundaries.crs)

# Filter to NYC
nyc_fips = ['36005', '36047', '36061', '36081', '36085']
block_groups_nyc = block_groups[
    (block_groups['STATEFP'] + block_groups['COUNTYFP']).isin(nyc_fips)
]


# Spatial join - assign each block group to the NTA it falls within
crosswalk = gpd.sjoin(
    block_groups_nyc,
    nta_boundaries,
    how='left',
    predicate='within'
)

# Check for unmatched block groups
unmatched = crosswalk['NTACode'].isna().sum()
print(f"Unmatched block groups: {unmatched}")

# Export crosswalk
crosswalk[['GEOID', 'NTACode']].to_csv("blockgroup_to_nta_crosswalk.csv", index=False)
print("Crosswalk exported successfully!")