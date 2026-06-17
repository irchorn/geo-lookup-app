import os
import secrets
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration settings."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_TYPE = 'filesystem'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///users.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # NYC Geoclient settings
    NYC_GEOCLIENT_URL = os.environ.get('NYC_GEOCLIENT_URL') or "https://api.nyc.gov/geo/geoclient/v2"
    NYC_GEOCLIENT_APP_ID = os.environ.get('NYC_GEOCLIENT_APP_ID')
    NYC_GEOCLIENT_APP_KEY = os.environ.get('NYC_GEOCLIENT_APP_KEY')
    
    # LimeSurvey Configuration
    LIMESURVEY_URL = os.environ.get('LIMESURVEY_URL')
    LIMESURVEY_USERNAME = os.environ.get('LIMESURVEY_USERNAME')
    LIMESURVEY_PASSWORD = os.environ.get('LIMESURVEY_PASSWORD')
    LIMESURVEY_SURVEY_ID = os.environ.get('LIMESURVEY_SURVEY_ID')
    
    # File upload settings
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    ALLOWED_EXTENSIONS = {'csv'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # NTA mapping file
    NTA_MAPPING_FILE = os.environ.get('NTA_MAPPING_FILE') or os.path.join(BASE_DIR, 'zip_to_nta_mapping.csv')
    
    @staticmethod
    def validate_config():
        """Validate required configuration variables."""
        required_vars = {
            'LIMESURVEY_URL': Config.LIMESURVEY_URL,
            'LIMESURVEY_USERNAME': Config.LIMESURVEY_USERNAME,
            'LIMESURVEY_PASSWORD': Config.LIMESURVEY_PASSWORD,
            'LIMESURVEY_SURVEY_ID': Config.LIMESURVEY_SURVEY_ID,
        }
        
        missing = [key for key, value in required_vars.items() if not value]
        
        if missing:
            print("\n⚠️  WARNING: Missing required configuration variables:")
            for var in missing:
                print(f"   - {var}")
            print("\nPlease set these in your .env file")
            return False
        return True


if __name__ == "__main__":
    print("=" * 50)
    print("Configuration Test")
    print("=" * 50)
    print("\nLimeSurvey Config:")
    print(f"  URL: {Config.LIMESURVEY_URL or 'NOT SET'}")
    print(f"  Username: {Config.LIMESURVEY_USERNAME or 'NOT SET'}")
    print(f"  Password: {'SET' if Config.LIMESURVEY_PASSWORD else 'NOT SET'}")
    print(f"  Survey ID: {Config.LIMESURVEY_SURVEY_ID or 'NOT SET'}")
    print("\nNYC Geoclient Config:")
    print(f"  URL: {Config.NYC_GEOCLIENT_URL}")
    print(f"  App ID: {'SET' if Config.NYC_GEOCLIENT_APP_ID else 'NOT SET'}")
    print(f"  App Key: {'SET' if Config.NYC_GEOCLIENT_APP_KEY else 'NOT SET'}")
    print("\nOther Config:")
    print(f"  Upload Folder: {Config.UPLOAD_FOLDER}")
    print(f"  NTA Mapping File: {Config.NTA_MAPPING_FILE}")
    print("=" * 50)
    print("\nValidation:")
    if Config.validate_config():
        print("✓ All required variables are set")
    else:
        print("✗ Some required variables are missing")
    print("=" * 50)