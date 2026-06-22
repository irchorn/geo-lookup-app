import csv
import logging
import os
import requests
from typing import Dict, List, Optional, Tuple
from collections import Counter
from math import radians, sin, cos, sqrt, atan2

# Configure logging
logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses and assigning NTAs with spatial matching."""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 15, max_retries: int = 3):
        """
        Initialize GeocodingService.
        
        Args:
            base_url: NYC Geoclient API base URL (optional).
            timeout: Request timeout in seconds. Default 15.
            max_retries: Number of retries for transient failures. Default 3.
        """
        self.base_url = (base_url or "https://api.nyc.gov/geo/geoclient/v2").rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Census Geocoder URL
        self.census_geocoder_url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
        
        # NTA mapping dictionaries
        self.nta_name_dict: Dict[str, str] = {}  # {nta_code: nta_name}
        self.zip_to_nta: Dict[str, str] = {}     # {zip_code: nta_code} (fallback)
        self._zip_nta_counts: Dict[str, Counter] = {}
        
        # Spatial matching data - coordinate points from CSV
        self.nta_points: List[Dict] = []
        
        self.nta_mapping_loaded = False
        
        # Create requests session
        self._session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry adapter."""
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            session = requests.Session()
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                backoff_factor=1
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            return session
        except Exception as e:
            logger.warning(f"Failed to create session with retries: {e}")
            return requests.Session()
    
    def _normalize_zip(self, raw_zip) -> str:
        """Normalize ZIP code to 5-digit format."""
        if raw_zip is None:
            return ''
        z = str(raw_zip).strip()
        z = ''.join(ch for ch in z if ch.isdigit())
        if len(z) >= 5:
            z = z[:5]
        return z.zfill(5) if z else ''
    
    def _parse_float(self, value) -> Optional[float]:
        """Safely parse a value to float."""
        if value is None:
            return None
        try:
            val = str(value).strip()
            if val == '' or val.lower() == 'nan':
                return None
            return float(val)
        except (ValueError, TypeError):
            return None
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two points in meters.
        
        Args:
            lat1, lon1: First point coordinates (degrees)
            lat2, lon2: Second point coordinates (degrees)
            
        Returns:
            Distance in meters.
        """
        R = 6371000  # Earth's radius in meters
        
        lat1_rad, lon1_rad = radians(lat1), radians(lon1)
        lat2_rad, lon2_rad = radians(lat2), radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def load_nta_mapping(self, filepath: str) -> bool:
        """
        Load NTA mapping from CSV file with coordinates for spatial matching.
        
        Expected columns:
        - ZIP Code (or zip_code, ZIP, etc.)
        - NTACode (or nta_code, NTA, etc.)
        - NTAName (or nta_name, etc.)
        - INTPTLAT10 (or latitude, LAT, etc.)
        - INTPTLON10 (or longitude, LON, etc.)
        - BoroName (optional)
        
        Args:
            filepath: Path to CSV file.
            
        Returns:
            True if loaded successfully, False otherwise.
        """
        if not os.path.exists(filepath):
            logger.warning(f"NTA mapping file not found: {filepath}")
            return False
        
        try:
            # Clear previous mappings
            self.nta_name_dict.clear()
            self.zip_to_nta.clear()
            self._zip_nta_counts.clear()
            self.nta_points.clear()
            
            with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                
                if not reader.fieldnames:
                    logger.error("CSV file is empty or has no headers")
                    return False
                
                print("=" * 70)
                print(f"Loading NTA mapping from: {filepath}")
                print(f"CSV columns: {reader.fieldnames}")
                print("=" * 70)
                
                # Build column name lookup (case-insensitive)
                col_lookup = {fn.upper().strip().replace(' ', '_'): fn for fn in reader.fieldnames}
                
                # Find columns helper
                def find_column(patterns):
                    for pattern in patterns:
                        pattern_norm = pattern.upper().replace(' ', '_')
                        for col_norm, col_orig in col_lookup.items():
                            if pattern_norm in col_norm or col_norm == pattern_norm:
                                return col_orig
                    return None
                
                # Identify columns
                zip_col = find_column(['ZIP_CODE', 'ZIP CODE', 'ZIPCODE', 'ZIP'])
                nta_code_col = find_column(['NTACODE', 'NTA_CODE', 'NTA CODE', 'NTA2020', 'NTA2010', 'NTA'])
                nta_name_col = find_column(['NTANAME', 'NTA_NAME', 'NTA NAME'])
                lat_col = find_column(['INTPTLAT10', 'INTPTLAT20', 'INTPTLAT', 'LATITUDE', 'LAT'])
                lon_col = find_column(['INTPTLON10', 'INTPTLON20', 'INTPTLON', 'LONGITUDE', 'LON', 'LNG'])
                boro_col = find_column(['BORONAME', 'BORO_NAME', 'BOROUGH', 'BORO'])
                
                print(f"Identified columns:")
                print(f"  ✓ ZIP: {zip_col}")
                print(f"  ✓ NTA Code: {nta_code_col}")
                print(f"  ✓ NTA Name: {nta_name_col}")
                print(f"  ✓ Latitude: {lat_col}")
                print(f"  ✓ Longitude: {lon_col}")
                print(f"  ✓ Borough: {boro_col}")
                
                if not lat_col or not lon_col:
                    print("  ⚠ WARNING: Latitude/Longitude columns not found!")
                    print("    Spatial matching will NOT be available.")
                
                # Process rows
                rows_processed = 0
                coords_loaded = 0
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Extract values
                        zip_code = self._normalize_zip(row.get(zip_col, '')) if zip_col else ''
                        nta_code = str(row.get(nta_code_col, '')).strip().upper() if nta_code_col else ''
                        nta_name = str(row.get(nta_name_col, '')).strip() if nta_name_col else ''
                        latitude = self._parse_float(row.get(lat_col, '')) if lat_col else None
                        longitude = self._parse_float(row.get(lon_col, '')) if lon_col else None
                        borough = str(row.get(boro_col, '')).strip() if boro_col else ''
                        
                        # Store ZIP → NTA mapping (for fallback)
                        if zip_code and nta_code:
                            self._zip_nta_counts.setdefault(zip_code, Counter())
                            self._zip_nta_counts[zip_code][nta_code] += 1
                        
                        # Store NTA code → name
                        if nta_code and nta_name and nta_code not in self.nta_name_dict:
                            self.nta_name_dict[nta_code] = nta_name
                        
                        # Store coordinate point for spatial matching
                        if latitude is not None and longitude is not None and nta_code:
                            self.nta_points.append({
                                'lat': latitude,
                                'lon': longitude,
                                'nta_code': nta_code,
                                'nta_name': nta_name,
                                'borough': borough,
                                'zip_code': zip_code
                            })
                            coords_loaded += 1
                        
                        rows_processed += 1
                        
                    except Exception as e:
                        logger.warning(f"Error processing row {row_num}: {e}")
                        continue
            
            # Build ZIP → most common NTA (fallback)
            for z, counter in self._zip_nta_counts.items():
                if counter:
                    top_nta, _ = counter.most_common(1)[0]
                    self.zip_to_nta[z] = top_nta
            
            self.nta_mapping_loaded = bool(self.zip_to_nta) or bool(self.nta_points)
            
            print("=" * 70)
            print("NTA MAPPING LOAD SUMMARY:")
            print(f"  Total rows processed: {rows_processed}")
            print(f"  ZIP→NTA mappings (fallback): {len(self.zip_to_nta)}")
            print(f"  NTA names loaded: {len(self.nta_name_dict)}")
            print(f"  Coordinate points for spatial matching: {coords_loaded}")
            print("=" * 70)
            
            if coords_loaded > 0:
                print("\nSample coordinate points for spatial matching:")
                for point in self.nta_points[:5]:
                    print(f"  ({point['lat']:.6f}, {point['lon']:.6f}) -> {point['nta_code']} - {point['nta_name']}")
                print()
            else:
                print("\n⚠ WARNING: No coordinate points loaded!")
                print("  Spatial matching will NOT be available.")
                print("  Will use ZIP-based fallback (less accurate).\n")
            
            return self.nta_mapping_loaded
            
        except Exception as e:
            logger.error(f"Error loading NTA mapping: {e}", exc_info=True)
            print(f"ERROR loading NTA mapping: {e}")
            return False
    
    def find_nearest_nta(self, latitude: float, longitude: float, max_distance_meters: float = 5000) -> Optional[Dict]:
        """
        Find nearest NTA to given coordinates using spatial matching.
        
        Args:
            latitude: Address latitude
            longitude: Address longitude
            max_distance_meters: Maximum distance threshold (default 5km)
            
        Returns:
            Dict with NTA info and distance, or None if no match.
        """
        if not self.nta_points:
            return None
        
        if latitude is None or longitude is None:
            return None
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            return None
        
        # Find nearest point
        min_distance = float('inf')
        nearest_point = None
        
        for point in self.nta_points:
            distance = self._haversine_distance(
                latitude, longitude,
                point['lat'], point['lon']
            )
            if distance < min_distance:
                min_distance = distance
                nearest_point = point
        
        if nearest_point:
            result = {
                'nta_code': nearest_point.get('nta_code'),
                'nta_name': nearest_point.get('nta_name'),
                'borough': nearest_point.get('borough'),
                'distance_meters': min_distance,
                'matched_lat': nearest_point['lat'],
                'matched_lon': nearest_point['lon']
            }
            
            if min_distance > max_distance_meters:
                result['warning'] = f'distance_exceeds_{max_distance_meters}m'
            
            return result
        
        return None
    
    def get_nta_from_zip(self, zip_code: str) -> Tuple[Optional[str], Optional[str]]:
        """Get NTA from ZIP code (fallback method)."""
        z = self._normalize_zip(zip_code)
        nta_code = self.zip_to_nta.get(z)
        nta_name = self.nta_name_dict.get(nta_code) if nta_code else None
        return nta_code, nta_name
    
    def geocode_with_census(self, street: str, city: str, state: str, zip_code: str) -> Dict[str, Optional[str]]:
        """
        Geocode address using US Census Bureau Geocoding API.
        
        This is a FREE service with NO API key required.
        
        Args:
            street: Street address
            city: City name
            state: State abbreviation
            zip_code: ZIP code
            
        Returns:
            Dict with latitude, longitude, or empty dict if geocoding failed.
        """
        try:
            street = (street or '').strip()
            city = (city or '').strip()
            state = (state or '').strip()
            zip_code = (zip_code or '').strip()
            
            if not street:
                return {}
            
            # Build full address string
            address_str = f"{street}, {city}, {state} {zip_code}".strip()
            
            params = {
                'address': address_str,
                'benchmark': 'Public_AR_Current',
                'format': 'json'
            }
            
            print(f"  📍 Census geocoding: {address_str[:60]}...", end=" ")
            
            response = self._session.get(
                self.census_geocoder_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            matches = data.get('result', {}).get('addressMatches', [])
            
            if matches:
                coords = matches[0].get('coordinates', {})
                latitude = coords.get('y')
                longitude = coords.get('x')
                
                # Also get matched address info
                matched_addr = matches[0].get('matchedAddress', '')
                
                if latitude and longitude:
                    print(f"✓ ({latitude:.6f}, {longitude:.6f})")
                    return {
                        'latitude': float(latitude),
                        'longitude': float(longitude),
                        'matched_address': matched_addr,
                        'source': 'census_geocoder'
                    }
            
            print("✗ No match")
            return {}
            
        except requests.exceptions.Timeout:
            print("✗ Timeout")
            logger.warning("Census geocoder timed out")
            return {}
        except requests.exceptions.RequestException as e:
            print(f"✗ Error: {e}")
            logger.warning(f"Census geocoder request failed: {e}")
            return {}
        except Exception as e:
            print(f"✗ Error: {e}")
            logger.error(f"Census geocoder unexpected error: {e}")
            return {}
    
    def geocode_with_nyc_api(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        app_id: str = None,
        app_key: str = None
    ) -> Dict[str, Optional[str]]:
        """
        Geocode address using NYC Geoclient API (if credentials provided).
        
        Args:
            street: Street address
            city: City name
            state: State abbreviation
            zip_code: ZIP code
            app_id: NYC Geoclient app ID
            app_key: NYC Geoclient app key
            
        Returns:
            Dict with latitude, longitude, NTA info, or empty dict if failed.
        """
        if not app_id or not app_key:
            return {}
        
        try:
            street = (street or '').strip()
            if not street:
                return {}
            
            url = f"{self.base_url.rstrip('/')}/search.json"
            input_str = f"{street}, {city}, {state} {zip_code}".strip()
            
            params = {
                'input': input_str,
                'app_id': app_id,
                'app_key': app_key
            }
            
            print(f"  🏙️ NYC API geocoding: {input_str[:60]}...", end=" ")
            
            response = self._session.get(url, params=params, timeout=self.timeout)
            
            # Try header auth if query param auth fails
            if response.status_code in (401, 403):
                headers = {'x-app-id': app_id, 'x-app-key': app_key}
                response = self._session.get(
                    url,
                    params={'input': input_str},
                    headers=headers,
                    timeout=self.timeout
                )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('results'):
                resp = data['results'][0].get('response', {}) or {}
                
                nta_code = resp.get('nta')
                if isinstance(nta_code, str):
                    nta_code = nta_code.strip().upper()
                
                lat = resp.get('latitude')
                lon = resp.get('longitude')
                
                if lat and lon:
                    print(f"✓ ({lat:.6f}, {lon:.6f}) NTA: {nta_code}")
                else:
                    print("✗ No coordinates")
                
                return {
                    'latitude': lat,
                    'longitude': lon,
                    'nta_code': nta_code,
                    'nta_name': resp.get('ntaName'),
                    'borough': resp.get('firstBoroughName') or resp.get('boroname'),
                    'source': 'nyc_geoclient_api'
                }
            
            print("✗ No match")
            return {}
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error: {e}")
            return {}
        except Exception as e:
            print(f"✗ Error: {e}")
            return {}
    
    def assign_nta(
        self,
        address_line_1: str,
        city: str,
        state: str,
        zip_code: str,
        app_id: str = None,
        app_key: str = None,
        latitude: float = None,
        longitude: float = None,
        use_census_geocoder: bool = True
    ) -> Dict[str, Optional[str]]:
        """
        Assign NTA to an address using geocoding and spatial matching.
        
        Priority:
        1. If latitude/longitude provided → Spatial matching
        2. NYC Geoclient API (if credentials) → Get NTA directly or coords for spatial
        3. Census Geocoder (if enabled) → Get coords → Spatial matching
        4. ZIP code mapping (fallback, less accurate)
        
        Args:
            address_line_1: Street address
            city: City name
            state: State abbreviation
            zip_code: ZIP code
            app_id: NYC Geoclient app ID (optional)
            app_key: NYC Geoclient app key (optional)
            latitude: Pre-existing latitude from source data (optional)
            longitude: Pre-existing longitude from source data (optional)
            use_census_geocoder: Whether to use Census geocoder (default True)
            
        Returns:
            Dict with nta_code, nta_name, latitude, longitude, borough, source.
        """
        result = {
            'nta_code': 'Unknown',
            'nta_name': 'Unknown',
            'latitude': latitude,
            'longitude': longitude,
            'borough': None,
            'source': 'not_found'
        }
        
        lat = latitude
        lon = longitude
        
        print(f"\n{'='*60}")
        print(f"Processing: {address_line_1}, {city}, {state} {zip_code}")
        print(f"{'='*60}")
        
        # ===== Method 1: If coordinates already provided =====
        if lat is not None and lon is not None:
            print(f"  Using provided coordinates: ({lat}, {lon})")
            
            if self.nta_points:
                nta_match = self.find_nearest_nta(lat, lon)
                
                if nta_match and nta_match.get('nta_code'):
                    distance = nta_match.get('distance_meters', 0)
                    source = f"spatial_matching ({distance:.0f}m)"
                    
                    if nta_match.get('warning'):
                        source += " ⚠️"
                    
                    result.update({
                        'nta_code': nta_match.get('nta_code'),
                        'nta_name': nta_match.get('nta_name') or self.nta_name_dict.get(nta_match.get('nta_code'), 'Unknown'),
                        'latitude': lat,
                        'longitude': lon,
                        'borough': nta_match.get('borough'),
                        'source': source
                    })
                    print(f"  ✅ RESULT: {result['nta_code']} - {result['nta_name']} ({distance:.0f}m)")
                    return result
        
        # ===== Method 2: NYC Geoclient API =====
        if app_id and app_key:
            api_result = self.geocode_with_nyc_api(
                address_line_1, city, state, zip_code, app_id, app_key
            )
            
            if api_result:
                lat = api_result.get('latitude')
                lon = api_result.get('longitude')
                
                # If API returns NTA directly, use it
                if api_result.get('nta_code'):
                    result.update({
                        'nta_code': api_result.get('nta_code'),
                        'nta_name': api_result.get('nta_name') or self.nta_name_dict.get(api_result.get('nta_code'), 'Unknown'),
                        'latitude': lat,
                        'longitude': lon,
                        'borough': api_result.get('borough'),
                        'source': 'nyc_geoclient_api'
                    })
                    print(f"  ✅ RESULT: {result['nta_code']} - {result['nta_name']} (NYC API)")
                    return result
                
                # If API gave coordinates but no NTA, use spatial matching
                if lat is not None and lon is not None and self.nta_points:
                    print(f"  🔍 Spatial matching with NYC API coords...")
                    nta_match = self.find_nearest_nta(lat, lon)
                    
                    if nta_match and nta_match.get('nta_code'):
                        distance = nta_match.get('distance_meters', 0)
                        
                        result.update({
                            'nta_code': nta_match.get('nta_code'),
                            'nta_name': nta_match.get('nta_name') or self.nta_name_dict.get(nta_match.get('nta_code'), 'Unknown'),
                            'latitude': lat,
                            'longitude': lon,
                            'borough': nta_match.get('borough') or api_result.get('borough'),
                            'source': f"spatial_matching ({distance:.0f}m) via NYC API"
                        })
                        print(f"  ✅ RESULT: {result['nta_code']} - {result['nta_name']} ({distance:.0f}m)")
                        return result
        
        # ===== Method 3: Census Geocoder + Spatial Matching =====
        if use_census_geocoder and self.nta_points:
            census_result = self.geocode_with_census(address_line_1, city, state, zip_code)
            
            if census_result:
                lat = census_result.get('latitude')
                lon = census_result.get('longitude')
                
                if lat is not None and lon is not None:
                    print(f"  🔍 Spatial matching with Census coords...")
                    nta_match = self.find_nearest_nta(lat, lon)
                    
                    if nta_match and nta_match.get('nta_code'):
                        distance = nta_match.get('distance_meters', 0)
                        source = f"spatial_matching ({distance:.0f}m) via Census"
                        
                        if nta_match.get('warning'):
                            source += " ⚠️"
                        
                        result.update({
                            'nta_code': nta_match.get('nta_code'),
                            'nta_name': nta_match.get('nta_name') or self.nta_name_dict.get(nta_match.get('nta_code'), 'Unknown'),
                            'latitude': lat,
                            'longitude': lon,
                            'borough': nta_match.get('borough'),
                            'source': source
                        })
                        print(f"  ✅ RESULT: {result['nta_code']} - {result['nta_name']} ({distance:.0f}m)")
                        return result
        
        # ===== Method 4: ZIP Code Fallback =====
        print(f"  ⚠️ Using ZIP fallback for: {zip_code}")
        
        if self.nta_mapping_loaded:
            nta_code, nta_name = self.get_nta_from_zip(zip_code)
            
            if nta_code:
                result.update({
                    'nta_code': nta_code,
                    'nta_name': nta_name or 'Unknown',
                    'latitude': lat,
                    'longitude': lon,
                    'source': 'zip_fallback (⚠️ may not be accurate)'
                })
                print(f"  ⚠️ RESULT (ZIP fallback): {nta_code} - {nta_name}")
                return result
        
        print(f"  ❌ Could not assign NTA")
        return result
    
    def close(self) -> None:
        """Close the requests session."""
        if self._session:
            self._session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ==================== Factory Functions ====================

def create_geocoding_service(
    base_url: Optional[str] = None,
    nta_mapping_filepath: Optional[str] = None
) -> GeocodingService:
    """Create and initialize a GeocodingService instance."""
    service = GeocodingService(base_url=base_url)
    if nta_mapping_filepath:
        service.load_nta_mapping(nta_mapping_filepath)
    return service


# Global instance
geocoding_service: Optional[GeocodingService] = None


def initialize_geocoding_service(
    base_url: Optional[str] = None,
    nta_mapping_filepath: Optional[str] = None
) -> GeocodingService:
    """Initialize the global geocoding service instance."""
    global geocoding_service
    geocoding_service = create_geocoding_service(base_url, nta_mapping_filepath)
    return geocoding_service