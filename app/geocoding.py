import csv
import logging
import os
import requests
from typing import Dict, Optional, Tuple
from collections import Counter


# Configure logging
logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and assigning NTAs without pandas dependency."""
    
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 10, max_retries: int = 3):
        self.base_url = (base_url or "https://api.nyc.gov/geo/geoclient/v2").rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        """
        Initialize GeocodingService.
        
        Args:
            base_url: NYC Geoclient API base URL. Defaults to official NYC endpoint.
            timeout: Request timeout in seconds. Default 10.
            max_retries: Number of retries for transient failures. Default 3.
        """
        
        
        self.nta_name_dict: Dict[str, str] = {}  # {nta_code: nta_name}
        self.zip_to_nta: Dict[str, str] = {}     # {zip_code: nta_code}
        self._zip_nta_counts: Dict[str, Counter] = {}  # {zip_code: Counter({nta_code: count})}
        self.nta_mapping_loaded = False
        
        # Create requests session with retry logic
        self._session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry adapter for transient failures."""
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            session = requests.Session()
            
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                backoff_factor=1  # 1s, 2s, 4s backoff
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            return session
        except Exception as e:
            # Fallback: return basic session without retry logic
            logger.warning(f"Failed to create session with retries: {e}. Using basic session.")
            return requests.Session()
    
    def _normalize_zip(self, raw_zip: str) -> str:
        """
        Normalize ZIP code to 5-digit format.
        
        Args:
            raw_zip: Raw ZIP code string (may include ZIP+4, spaces, etc.)
        
        Returns:
            Normalized 5-digit ZIP code, or empty string if invalid.
        """
        if raw_zip is None:
            return ''
        
        # Convert to string and strip whitespace
        z = str(raw_zip).strip()
        
        # Remove non-digits (e.g., ZIP+4: 11232-1234 -> 11232)
        z = ''.join(ch for ch in z if ch.isdigit())
        
        # Ensure it's at least 5 digits, take first 5
        if len(z) >= 5:
            z = z[:5]
        
        # Pad with leading zeros if needed
        return z.zfill(5) if z else ''
    
    def load_nta_mapping(self, filepath: str) -> bool:
        """
        Load NTA mapping from CSV file using standard library.
        
        Expected columns (flexible naming):
        - zip_code (or ZIP Code, ZIP, Zip, etc.)
        - nta_code (or NTACode, NTA_CODE, etc.)
        - nta_name (or NTAName, NTA Name, NTA_NAME, etc.)
        
        Args:
            filepath: Path to CSV file containing ZIP→NTA mappings.
        
        Returns:
            True if mappings loaded successfully, False otherwise.
        """
        if not os.path.exists(filepath):
            logger.warning(f"NTA mapping file not found: {"data/zip_to_nta_mapping.csv"}")
            return False
        
        try:
            # Clear previous mappings to avoid duplicates on reload
            self.nta_name_dict.clear()
            self.zip_to_nta.clear()
            self._zip_nta_counts.clear()
            
            with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                
                if not reader.fieldnames:
                    logger.error("CSV file is empty or has no headers")
                    return False
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                    try:
                        # Extract ZIP code - support multiple column name variations
                        zip_raw = (
                            row.get('zip_code') or
                            row.get('ZIP Code') or
                            row.get('Zip Code') or
                            row.get('ZIP') or
                            row.get('Zip') or
                            row.get('zip') or
                            ''
                        )
                        
                        # Extract NTA code
                        nta_code_raw = (
                            row.get('nta_code') or
                            row.get('NTACode') or
                            row.get('NTA Code') or
                            row.get('NTA_CODE') or
                            row.get('NTA code') or
                            ''
                        )
                        
                        # Extract NTA name
                        nta_name_raw = (
                            row.get('nta_name') or
                            row.get('NTAName') or
                            row.get('NTA Name') or
                            row.get('NTA_NAME') or
                            ''
                        )
                        
                        # Normalize values
                        zip_code = self._normalize_zip(zip_raw)
                        nta_code = str(nta_code_raw).strip().upper() if nta_code_raw else ''
                        nta_name = str(nta_name_raw).strip() if nta_name_raw else ''
                        
                        # Store mappings
                        if zip_code and nta_code:
                            self._zip_nta_counts.setdefault(zip_code, Counter())
                            self._zip_nta_counts[zip_code][nta_code] += 1
                        
                        if nta_code and nta_name:
                            if nta_code not in self.nta_name_dict or not self.nta_name_dict[nta_code]:
                                self.nta_name_dict[nta_code] = nta_name
                    
                    except Exception as e:
                        logger.warning(f"Error processing row {row_num}: {e}")
                        continue
            
            # Choose the most frequent NTA per ZIP
            for z, counter in self._zip_nta_counts.items():
                if counter:
                    top_nta, count = counter.most_common(1)[0]
                    self.zip_to_nta[z] = top_nta
            
            self.nta_mapping_loaded = bool(self.zip_to_nta)
            logger.info(f"Loaded {len(self.zip_to_nta)} ZIP→NTA mappings from {filepath}")
            logger.info(f"Loaded {len(self.nta_name_dict)} NTA names")
            return self.nta_mapping_loaded
        
        except Exception as e:
            logger.error(f"Error loading NTA mapping from {filepath}: {e}", exc_info=True)
            self.nta_mapping_loaded = False
            return False
    
    def get_nta_from_zip(self, zip_code: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get NTA code and name from ZIP code.
        
        Args:
            zip_code: ZIP code (5-digit or ZIP+4 format).
        
        Returns:
            Tuple of (nta_code, nta_name) or (None, None) if not found.
        """
        z = self._normalize_zip(zip_code)
        nta_code = self.zip_to_nta.get(z)
        nta_name = self.nta_name_dict.get(nta_code) if nta_code else None
        return nta_code, nta_name
    

    def geocode_with_nyc_api(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        app_id: str = None,
        app_key: str = None
    ) -> Dict[str, Optional[str]]:
        if not app_id or not app_key:
            logging.getLogger(__name__).debug("NYC Geoclient credentials not provided; skipping API geocoding")
            return {}

        try:
            street = (street or '').strip()
            city = (city or '').strip()
            state = (state or '').strip()
            zip_code = (zip_code or '').strip()
            if not street:
                return {}

            # Build correct endpoint (avoid urljoin which can drop 'v2')
            url = f"{self.base_url.rstrip('/')}/search.json"
            input_str = f"{street}, {city}, {state} {zip_code}".strip()

            params = {
                'input': input_str,
                'app_id': app_id,
                'app_key': app_key
            }

            logger = logging.getLogger(__name__)
            logger.debug(f"NYC Geoclient request URL: {url}")
            logger.debug(f"NYC Geoclient params: input='{input_str[:200]}...'")

            # First try with query params (supported by Geoclient)
            response = self._session.get(url, params=params, timeout=self.timeout)
            status = response.status_code

            # If unauthorized, try header-based auth fallback
            if status in (401, 403):
                headers = {
                    'x-app-id': app_id,
                    'x-app-key': app_key
                }
                # Remove credentials from query params for header attempt
                params_fallback = {'input': input_str}
                logger.debug("Retrying Geoclient with header-based credentials")
                response = self._session.get(url, params=params_fallback, headers=headers, timeout=self.timeout)
                status = response.status_code

            response.raise_for_status()
            data = response.json()

            if data.get('results'):
                response_data = data['results'][0].get('response', {}) or {}
                nta_code = response_data.get('nta')
                if isinstance(nta_code, str):
                    nta_code = nta_code.strip().upper()

                result = {
                    'latitude': response_data.get('latitude'),
                    'longitude': response_data.get('longitude'),
                    'nta_code': nta_code,
                    'nta_name': response_data.get('ntaName'),
                    'source': 'nyc_geoclient_api'
                }
                logger.debug(f"Geoclient result NTA: {nta_code}, Name: {result['nta_name']}")
                return result

            logger.debug(f"NYC Geoclient returned no results for input='{input_str}'")
            return {}

        except requests.exceptions.RequestException as e:
            logging.getLogger(__name__).warning(f"NYC Geoclient API request failed: {e}")
            return {}
        except ValueError as e:
            logging.getLogger(__name__).warning(f"Failed to parse NYC Geoclient API response: {e}")
            return {}
        except Exception as e:
            logging.getLogger(__name__).error(f"Unexpected error in NYC Geoclient API call: {e}", exc_info=True)
            return {}
    
    def assign_nta(
        self,
        address_line_1: str,
        city: str,
        state: str,
        zip_code: str,
        app_id: str = None,
        app_key: str = None
    ) -> Dict[str, Optional[str]]:
        """
        Assign NTA to an address using multiple fallback methods:
        1. NYC Geoclient API (if credentials provided)
        2. ZIP code mapping
        
        Args:
            address_line_1: Street address.
            city: City name.
            state: State abbreviation.
            zip_code: ZIP code.
            app_id: NYC Geoclient app ID (optional).
            app_key: NYC Geoclient app key (optional).
        
        Returns:
            Dictionary with nta_code, nta_name, latitude, longitude, and source.
            Returns 'Unknown' for missing values.
        """
        result = {
            'nta_code': 'Unknown',
            'nta_name': 'Unknown',
            'latitude': None,
            'longitude': None,
            'source': 'unknown'
        }
        
        # Try NYC Geoclient API first
        if app_id and app_key:
            api_result = self.geocode_with_nyc_api(
                address_line_1, city, state, zip_code, app_id, app_key
            )
            
            if api_result.get('nta_code'):
                result.update(api_result)
                logger.debug(f"NTA assigned via API: {result['nta_code']}")
                return result
        
        # Fall back to ZIP code mapping
        if self.nta_mapping_loaded:
            nta_code, nta_name = self.get_nta_from_zip(zip_code)
            
            if nta_code:
                result['nta_code'] = nta_code
                result['nta_name'] = nta_name or 'Unknown'
                result['source'] = 'zip_mapping'
                logger.debug(f"NTA assigned via ZIP mapping: {nta_code}")
                return result
        
        logger.debug(f"Could not assign NTA for address: {address_line_1}, {city}, {state} {zip_code}")
        return result
    
    def close(self) -> None:
        """Close the requests session (call when done with the service)."""
        if self._session:
            self._session.close()
            logger.debug("Geocoding service session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global instance factory
def create_geocoding_service(
    base_url: Optional[str] = None,
    nta_mapping_filepath: Optional[str] = None
) -> GeocodingService:
    """
    Create and optionally initialize a GeocodingService instance.
    
    Args:
        base_url: NYC Geoclient API base URL (defaults to official endpoint).
        nta_mapping_filepath: Path to NTA mapping CSV file to load.
    
    Returns:
        Initialized GeocodingService instance.
    """
    service = GeocodingService(base_url=base_url)
    
    if nta_mapping_filepath:
        service.load_nta_mapping(nta_mapping_filepath)
    
    return service


# Global instance (for backward compatibility)
geocoding_service: Optional[GeocodingService] = None


def initialize_geocoding_service(
    base_url: Optional[str] = None,
    nta_mapping_filepath: Optional[str] = None
) -> GeocodingService:
    """
    Initialize the global geocoding service instance.
    
    Args:
        base_url: NYC Geoclient API base URL.
        nta_mapping_filepath: Path to NTA mapping CSV file.
    
    Returns:
        The initialized global geocoding_service instance.
    """
    global geocoding_service
    geocoding_service = create_geocoding_service(base_url, nta_mapping_filepath)
    return geocoding_service