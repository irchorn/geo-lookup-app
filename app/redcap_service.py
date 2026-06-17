import requests
import pandas as pd
from flask import current_app
from werkzeug.utils import secure_filename
import os


class REDCapService:
    """Service for fetching and processing REDCap data."""
    
    # Default field mappings (can be customized)
    DEFAULT_FIELD_MAPPING = {
        'record_id': 'record_id',
        'date': 'aded_selfref_date',
        'first_name': 'aded_selfref_firstname',
        'last_name': 'aded_selfref_lastname',
        'address_1': 'abe_address',
        'address_2': 'abe_address_2',
        'city': 'abe_city',
        'state': 'abe_state',
        'zip_code': 'abe_zip'
    }
    
    def __init__(self, field_mapping=None):
        self.field_mapping = field_mapping or self.DEFAULT_FIELD_MAPPING
    
    def fetch_from_api(self, fields=None):
        """
        Fetch data from REDCap API.
        Returns tuple of (records, error_message).
        """
        try:
            api_url = current_app.config.get('REDCAP_API_URL')
            api_token = current_app.config.get('REDCAP_API_TOKEN')
        except RuntimeError:
            return None, "Application context not available."
        
        if not api_url or not api_token:
            return None, "REDCap API URL or Token not configured."
        
        # Use default fields if not specified
        if fields is None:
            fields = list(self.field_mapping.values())
        
        payload = {
            'token': api_token,
            'content': 'record',
            'format': 'json',
            'fields': ','.join(fields),
            'returnFormat': 'json'
        }
        
        try:
            response = requests.post(api_url, data=payload, timeout=30)
            
            if response.status_code == 200:
                records = response.json()
                return self._normalize_records(records), None
            else:
                error_msg = f"REDCap API error: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail.get('error', '')}"
                except:
                    pass
                return None, error_msg
                
        except requests.exceptions.Timeout:
            return None, "REDCap API request timed out."
        except requests.exceptions.RequestException as e:
            return None, f"REDCap API request failed: {str(e)}"
    
    def load_from_csv(self, file_path):
        """
        Load data from REDCap CSV export.
        Returns tuple of (records, error_message).
        """
        try:
            df = pd.read_csv(file_path)
            
            if df.empty:
                return None, "The CSV file is empty."
            
            # Convert DataFrame to list of dictionaries
            records = df.to_dict('records')
            
            return self._normalize_records(records), None
            
        except pd.errors.EmptyDataError:
            return None, "The CSV file is empty."
        except pd.errors.ParserError as e:
            return None, f"Error parsing CSV file: {str(e)}"
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
        Maps various possible REDCap field names to standard names.
        """
        normalized = []
        
        # Auto-detect field mappings from first record
        if records:
            self._auto_detect_fields(records[0])
        
        for record in records:
            norm_record = {}
            
            # Try to map each field
            for standard_name, redcap_name in self.field_mapping.items():
                # Check for exact match
                if redcap_name in record:
                    norm_record[standard_name] = record[redcap_name]
                # Check for case-insensitive match
                else:
                    for key in record.keys():
                        if key.lower() == redcap_name.lower():
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
            'record_id': ['record_id', 'id', 'participant_id', 'subject_id', 'study_id'],
            'date': ['date', 'aded_selfref_date', 'selfref_date', 'visit_date', 'enrollment_date'],
            'first_name': ['first_name', 'firstname', 'aded_selfref_firstname', 'fname', 'first'],
            'last_name': ['last_name', 'lastname', 'aded_selfref_lastname', 'lname', 'last'],
            'address_1': ['address', 'address_1', 'address1', 'street', 'street_address', 'addr', 'abe_address'],
            'address_2': ['address_2', 'address2', 'apt', 'apartment', 'unit', 'suite', 'abe_address_2'],
            'city': ['city', 'town', 'municipality', 'abe_city'],
            'state': ['state', 'province', 'region', 'abe_state'],
            'zip_code': ['zip', 'zipcode', 'zip_code', 'postal', 'postal_code', 'postcode', 'abe_zip']
        }
        
        for field_type, patterns in field_patterns.items():
            for col in sample_record.keys():
                col_lower = col.lower().strip()
                for pattern in patterns:
                    if pattern in col_lower or col_lower == pattern:
                        self.field_mapping[field_type] = col
                        break
                else:
                    continue
                break


# Global REDCap service instance
redcap_service = REDCapService()