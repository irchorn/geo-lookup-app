import urllib.request
import json
import base64
import csv
from io import StringIO
from flask import current_app
from werkzeug.utils import secure_filename
import os

# Import from Config class
try:
    from config import Config
    LIMESURVEY_URL = Config.LIMESURVEY_URL
    LIMESURVEY_USERNAME = Config.LIMESURVEY_USERNAME
    LIMESURVEY_PASSWORD = Config.LIMESURVEY_PASSWORD
    LIMESURVEY_SURVEY_ID = Config.LIMESURVEY_SURVEY_ID
except ImportError:
    # Fallback to environment variables
    LIMESURVEY_URL = os.environ.get('LIMESURVEY_URL')
    LIMESURVEY_USERNAME = os.environ.get('LIMESURVEY_USERNAME')
    LIMESURVEY_PASSWORD = os.environ.get('LIMESURVEY_PASSWORD')
    LIMESURVEY_SURVEY_ID = os.environ.get('LIMESURVEY_SURVEY_ID')

class LimeSurveyService:
    """Service for fetching and processing LimeSurvey data."""
    
    # Field mappings for Program Interest Form (Survey ID)
    # API uses Q codes, not the full field names from Excel export
    DEFAULT_FIELD_MAPPING = {
        'record_id': '"id"',              
        'date': 'Q001',                   
        'first_name': 'Q002',             
        'last_name': 'Q003',              
        'address_1': 'Q004',              
        'address_2': 'Q005',              
        'city': 'Q006',                   
        'state': 'Q007',                  
        'zip_code': 'Q008'                
    }
    
    def __init__(self, field_mapping=None):
        self.field_mapping = field_mapping or self.DEFAULT_FIELD_MAPPING.copy()
        self.url = None
        self.username = None
        self.password = None
        self.survey_id = None
        self.session_key = None
    
    def _get_config(self):
        """Get configuration from Flask app or fallback to config file."""
        try:
            self.url = current_app.config.get('LIMESURVEY_URL') or LIMESURVEY_URL
            self.username = current_app.config.get('LIMESURVEY_USERNAME') or LIMESURVEY_USERNAME
            self.password = current_app.config.get('LIMESURVEY_PASSWORD') or LIMESURVEY_PASSWORD
            self.survey_id = current_app.config.get('LIMESURVEY_SURVEY_ID') or LIMESURVEY_SURVEY_ID
        except RuntimeError:
            # Outside Flask context, use config file values
            self.url = LIMESURVEY_URL
            self.username = LIMESURVEY_USERNAME
            self.password = LIMESURVEY_PASSWORD
            self.survey_id = LIMESURVEY_SURVEY_ID
    
    def _make_request(self, method, params):
        """Generic method to make API requests."""
        data = json.dumps({
            "method": method,
            "params": params,
            "id": 1
        }).encode('utf-8')
        
        req = urllib.request.Request(
            url=self.url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Connection': 'Keep-Alive'
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('result')
        except urllib.error.URLError as e:
            print(f"LimeSurvey API Error: {e}")
            return None
        except TimeoutError:
            print("LimeSurvey API request timed out.")
            return None
    
    def _connect(self):
        """Authenticate and get session key."""
        self.session_key = self._make_request(
            "get_session_key", 
            [self.username, self.password]
        )
        return self.session_key
    
    def _disconnect(self):
        """Release the session key."""
        if self.session_key:
            self._make_request("release_session_key", [self.session_key])
            self.session_key = None
    
    def list_surveys(self):
        """List all available surveys."""
        if not self.url or not self.username or not self.password:
            return None, "LimeSurvey credentials not configured."
        
        try:
            self._connect()
            
            if not self.session_key or isinstance(self.session_key, dict):
                return None, "Authentication failed."
            
            surveys = self._make_request("list_surveys", [self.session_key])
            self._disconnect()
            
            return surveys, None
        except Exception as e:
            return None, f"Error: {str(e)}"


    def fetch_from_api(self, survey_id=None, fields=None):
        """
        Fetch data from LimeSurvey API.
        Returns tuple of (records, error_message).
        """
        self._get_config()
        
        if not self.url or not self.username or not self.password:
            return None, "LimeSurvey API URL or credentials not configured."
        
        survey_id = survey_id or self.survey_id
        if not survey_id:
            return None, "Survey ID not specified."
        
        try:
            # Connect to API
            session = self._connect()
            
            if not session or isinstance(session, dict):
                error_msg = session.get('status', 'Unknown error') if isinstance(session, dict) else 'Authentication failed'
                return None, f"LimeSurvey authentication failed: {error_msg}"
            
            # Export responses
            result = self._make_request(
                "export_responses",
                [self.session_key, survey_id, "csv", "en", "full"]
            )
            
            # Disconnect
            self._disconnect()
            
            if not result:
                return None, "No data returned from LimeSurvey."
            
            if isinstance(result, dict) and 'status' in result:
                return None, f"LimeSurvey API error: {result['status']}"
            
            # Decode base64 response
            try:
                csv_data = base64.b64decode(result).decode('utf-8')
            except Exception as e:
                return None, f"Error decoding response: {str(e)}"
            
            # Parse CSV to records
            records = self._csv_to_records(csv_data)
            
            if not records:
                return None, "No records found in survey responses."
            
            # Filter fields if specified
            if fields:
                records = self._filter_fields(records, fields)
            
            return self._normalize_records(records), None
            
             # Add this debug output:
            print(f"\n=== LimeSurvey Fetch Debug ===")
            print(f"Total responses fetched: {len(responses)}")
            if responses:
                print(f"First response keys: {responses[0].keys()}")
                print(f"First response data: {responses[0]}")
            print("=" * 50 + "\n")

        except Exception as e:
            return None, f"LimeSurvey API request failed: {str(e)}"
    
    def _csv_to_records(self, csv_data):
        """Convert CSV string to list of dictionaries."""
        if not csv_data:
            return []
        
        try:
            # Try semicolon delimiter first (LimeSurvey default for some languages)
            reader = csv.DictReader(StringIO(csv_data), delimiter=';')
            records = list(reader)
        
            # If only 1 field detected, try comma delimiter
            if records and len(records[0].keys()) <= 1:
                reader = csv.DictReader(StringIO(csv_data), delimiter=',')
                records = list(reader)
        
            return records
        except Exception as e:
             print(f"Error parsing CSV: {e}")
             return []
    
    def _filter_fields(self, records, fields):
        """Filter records to only include specified fields."""
        filtered = []
        for record in records:
            filtered_record = {k: v for k, v in record.items() if k in fields}
            filtered.append(filtered_record)
        return filtered
    
    def load_from_csv(self, file_path):
        """
        Load data from LimeSurvey CSV export.
        Returns tuple of (records, error_message).
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_data = f.read()
            
            records = self._csv_to_records(csv_data)
            
            if not records:
                return None, "The CSV file is empty."
            
            return self._normalize_records(records), None
            
        except FileNotFoundError:
            return None, "CSV file not found."
        except Exception as e:
            return None, f"Error loading CSV file: {str(e)}"
    
    def process_uploaded_file(self, file, upload_folder):
        """
        Process an uploaded CSV file.
        Returns tuple of (file_path, error_message).
        """
        if not file or file.filename == '':
            return None, "No file selected."
        
        filename = secure_filename(file.filename)
        if not filename.lower().endswith('.csv'):
            return None, "Only CSV files are allowed."
        
        # Create upload folder if it doesn't exist
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        file_path = os.path.join(upload_folder, filename)
        
        try:
            file.save(file_path)
            return file_path, None
        except Exception as e:
            return None, f"Error saving file: {str(e)}"
    
    def _normalize_records(self, records):
        """
        Normalize records to use consistent field names.
        Maps various possible LimeSurvey field names to standard names.
        """
        normalized = []
        
        # Auto-detect field mappings from first record
        if records:
            self._auto_detect_fields(records[0])
        
        for record in records:
            norm_record = {}
            
            # Try to map each field
            for standard_name, limesurvey_name in self.field_mapping.items():
                # Check for exact match
                if limesurvey_name in record:
                    norm_record[standard_name] = record[limesurvey_name]
                # Check for case-insensitive match
                else:
                    for key in record.keys():
                        if key.lower() == limesurvey_name.lower():
                            norm_record[standard_name] = record[key]
                            break
                    else:
                        norm_record[standard_name] = ''
            
            # Also include original record data
            norm_record['_original'] = record
            normalized.append(norm_record)
        
        return normalized
    
    def _auto_detect_fields(self, sample_record):
        """
        Auto-detect field mappings from a sample record.
        Updates self.field_mapping with detected fields.
        """
        field_patterns = {
            'record_id': ['record_id', 'id', 'participant_id', 'subject_id', 'study_id', 'response_id', 'Response ID','token'],
            'date': ['date', 'aded_selfref_date', 'selfref_date', 'submitdate', 'startdate', 'datestamp'],
            'first_name': ['first_name', 'firstname', 'aded_selfref_firstname', 'fname', 'first'],
            'last_name': ['last_name', 'lastname', 'aded_selfref_lastname', 'lname'],
            'address_1': ['address', 'address_1', 'address1', 'street', 'street_address', 'addr', 'abe_address'],
            'address_2': ['address_2', 'address2', 'apt', 'apartment', 'unit', 'suite', 'abe_address_2'],
            'city': ['city', 'town', 'municipality', 'abe_city'],
            'state': ['state', 'province', 'region', 'abe_state'],
            'zip_code': ['zip', 'zipcode', 'zip_code', 'postal', 'postal_code', 'postcode', 'abe_zip']
        }
        
        for field_type, patterns in field_patterns.items():
            
        # Skip if already mapped to a Q-code (e.g., Q001, Q002)
            current_mapping = self.field_mapping.get(field_type, '')
            if current_mapping.startswith('Q'):
               continue

            for col in sample_record.keys():
                col_lower = col.lower().strip()
                for pattern in patterns:
                    if pattern in col_lower or col_lower == pattern:
                        self.field_mapping[field_type] = col
                        break
                else:
                    continue
                break
    
    def list_surveys(self):
        """
        List all available surveys.
        Returns tuple of (surveys, error_message).
        """
        self._get_config()
        
        if not self.url or not self.username or not self.password:
            return None, "LimeSurvey API credentials not configured."
        
        try:
            self._connect()
            
            if not self.session_key or isinstance(self.session_key, dict):
                return None, "Authentication failed."
            
            surveys = self._make_request("list_surveys", [self.session_key])
            self._disconnect()
            
            return surveys, None
            
        except Exception as e:
            return None, f"Error listing surveys: {str(e)}"
    
    def get_survey_properties(self, survey_id=None):
        """
        Get properties of a specific survey.
        Returns tuple of (properties, error_message).
        """
        self._get_config()
        survey_id = survey_id or self.survey_id
        
        try:
            self._connect()
            
            if not self.session_key or isinstance(self.session_key, dict):
                return None, "Authentication failed."
            
            properties = self._make_request(
                "get_survey_properties",
                [self.session_key, survey_id, ["sid", "surveyls_title", "active", "expires"]]
            )
            self._disconnect()
            
            return properties, None
            
        except Exception as e:
            return None, f"Error getting survey properties: {str(e)}"


# Global LimeSurvey service instance
limesurvey_service = LimeSurveyService()


# ============================================
# Helper Functions (matching REDCap patterns)
# ============================================

def fetch_limesurvey_data(survey_id=None):
    """
    Fetch all survey responses from LimeSurvey.
    Returns tuple of (records, error_message).
    """
    return limesurvey_service.fetch_from_api(survey_id)


def fetch_limesurvey_data_by_zipcode(zipcode, survey_id=None):
    """
    Fetch survey responses filtered by zip code.
    Returns tuple of (records, error_message).
    """
    records, error = limesurvey_service.fetch_from_api(survey_id)
    
    if error:
        return None, error
    
    if not records:
        return [], None
    
    # Filter by zip code
    filtered = [
        r for r in records 
        if r.get('zip_code', '').strip() == str(zipcode).strip()
    ]
    
    return filtered, None


# ============================================
# Test Function
# ============================================

if __name__ == "__main__":
    print("Testing LimeSurvey Service...")
    print("=" * 50)
    
    service = LimeSurveyService()
    
    # Test listing surveys
    print("\n1. Listing Surveys...")
    surveys, error = service.list_surveys()
    if error:
        print(f"   ✗ Error: {error}")
    else:
        print(f"   ✓ Found {len(surveys) if surveys else 0} surveys")
        if surveys:
            for s in surveys[:3]:  # Show first 3
                print(f"     - {s.get('surveyls_title', 'Untitled')} (ID: {s.get('sid')})")
    
    # Test fetching data
    print("\n2. Fetching Survey Data...")
    records, error = service.fetch_from_api()
    if error:
        print(f"   ✗ Error: {error}")
    else:
        print(f"   ✓ Fetched {len(records)} records")
        if records:
            # Show all available fields
            original = records[0].get('_original', {})
            print(f"\n   📋 Available fields ({len(original)}):")
            for field in original.keys():
                print(f"      - {field}: {str(original[field])[:30]}")
            
            # Show normalized record
            print(f"\n   📝 Normalized record:")
            for key, value in records[0].items():
                if key != '_original':
                    print(f"      {key}: {value}")
    print("\n" + "=" * 50)
    print("Test complete!")