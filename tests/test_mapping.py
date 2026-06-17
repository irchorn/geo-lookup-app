from app.geocoding import geocoding_service

# Load the mapping
print("Loading NTA mapping...")
ok = geocoding_service.load_nta_mapping(
    r"C:\Users\chorni02\OneDrive - NYU Langone Health\Python\NTA Lookup\zip_to_nta_mapping.csv"
)

print(f"Loaded: {ok}")
print(f"Mapping status: {geocoding_service.nta_mapping_loaded}")
print(f"Total ZIP mappings: {len(geocoding_service.zip_to_nta)}")
print(f"Total NTA names: {len(geocoding_service.nta_name_dict)}")

# Test with actual ZIP codes from your LimeSurvey data
test_zips = ["11232", "11220", "11215", "11234", "11411", "11379", "10307", "10471", "11001"]

print("\nTesting ZIP lookups:")
for zip_code in test_zips:
    nta_code, nta_name = geocoding_service.get_nta_from_zip(zip_code)
    print(f"  {zip_code} -> {nta_code}: {nta_name}")