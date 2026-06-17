from app.lime_survey import limesurvey_service

def check_fields():
    print("Checking LimeSurvey Fields...")
    print("=" * 60)
    
    records, error = limesurvey_service.fetch_from_api()
    
    if error:
        print(f"❌ Error: {error}")
        return
    
    if not records:
        print("No records found")
        return
    
    # Get original record (before normalization)
    original = records[0].get('_original', {})
    
    print(f"\n📋 Found {len(original)} fields in your survey:\n")
    print("-" * 60)
    
    for i, (field_name, value) in enumerate(original.items(), 1):
        # Truncate long values
        display_value = str(value)[:50] + "..." if len(str(value)) > 50 else value
        print(f"{i:3}. {field_name}")
        print(f"     Value: {display_value}\n")

if __name__ == "__main__":
    check_fields()