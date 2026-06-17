import requests
import pandas as pd
from pathlib import Path

CENSUS_API_KEY = "d2d41b6f350967df55f4ec16a272b5033a680bfb"  # Your key
YEAR = "2020"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# NYC county FIPS codes (must query each county separately for block groups)
NYC_COUNTIES = {
    "005": "Bronx",
    "047": "Kings",       # Brooklyn
    "061": "New York",    # Manhattan
    "081": "Queens",
    "085": "Richmond"     # Staten Island
}

def fetch_blockgroup_population_by_county(state_fips="36", county_fips="005"):
    """
    Fetch ACS 5-year B01003 (Total population) at block group level 
    for a single county.
    
    Census API requires county to be specified for block group queries.
    """
    base_url = f"https://api.census.gov/data/{YEAR}/acs/acs5"
    
    params = {
        "get": "B01003_001E,NAME",
        "for": "block group:*",
        "in": f"state:{state_fips} county:{county_fips}",
        "key": CENSUS_API_KEY
    }
    
    print(f"Fetching block groups for county {county_fips}...")
    r = requests.get(base_url, params=params)
    
    # Debug: print URL and status if error
    if r.status_code != 200:
        print(f"Error URL: {r.url}")
        print(f"Response: {r.text[:500]}")
        r.raise_for_status()
    
    data = r.json()
    cols = data[0]
    rows = data[1:]
    
    df = pd.DataFrame(rows, columns=cols)
    return df


def fetch_all_nyc_blockgroups():
    """
    Loop through all NYC counties and combine results.
    """
    all_dfs = []
    
    for county_fips, county_name in NYC_COUNTIES.items():
        try:
            df = fetch_blockgroup_population_by_county(
                state_fips="36", 
                county_fips=county_fips
            )
            print(f"  → {county_name}: {len(df)} block groups")
            all_dfs.append(df)
        except Exception as e:
            print(f"  → Error fetching {county_name}: {e}")
    
    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"Total NYC block groups: {len(combined)}")
    return combined


def build_bg_population_csv():
    """
    Build the bg_population.csv file from Census API data.
    """
    df = fetch_all_nyc_blockgroups()
    
    # Build 12-digit block group GEOID from the returned columns
    # Census API returns: state, county, tract, block group as separate columns
    df["GEOID"] = (
        df["state"].str.zfill(2)
        + df["county"].str.zfill(3)
        + df["tract"].str.zfill(6)
        + df["block group"].str.zfill(1)
    )
    
    # Rename population column
    df["population"] = pd.to_numeric(df["B01003_001E"], errors="coerce")
    
    # Keep only GEOID + population
    out = df[["GEOID", "population"]].copy()
    
    # Drop any rows with missing population
    out = out.dropna(subset=["population"])
    out["population"] = out["population"].astype(int)
    
    # Save to CSV
    out_path = DATA_DIR / "bg_population.csv"
    out.to_csv(out_path, index=False)
    
    print(f"\nSaved {len(out)} rows to {out_path}")
    print(out.head(10))


if __name__ == "__main__":
    build_bg_population_csv()