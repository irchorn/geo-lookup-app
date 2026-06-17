from app.lime_survey import limesurvey_service

def test_fetch():
    print("Testing LimeSurvey Data Fetch...")
    print("=" * 50)
    
    # Fetch survey responses
    records, error = limesurvey_service.fetch_from_api()
    
    if error:
        print(f"❌ Error: {error}")
        return
    
    if not records:
        print("⚠️  No records found (survey may be empty)")
        return
    
    print(f"✅ Successfully fetched {len(records)} records!\n")
    
    # Show sample record
    print("Sample Record (normalized fields):")
    print("-" * 40)
    
    sample = records[0]
    for key, value in sample.items():
        if key != '_original':
            print(f"  {key}: {value}")
    
    # Show available original fields
    print("\nOriginal Fields Available:")
    print("-" * 40)
    if '_original' in sample:
        for key in list(sample['_original'].keys())[:10]:
            print(f"  - {key}")
        if len(sample['_original'].keys()) > 10:
            print(f"  ... and {len(sample['_original'].keys()) - 10} more fields")

if __name__ == "__main__":
    test_fetch()