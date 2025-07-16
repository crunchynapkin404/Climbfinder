import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time
import re

csv_path = '/home/bart/beklimmingen_details_met_coords.csv'  # Werk direct in de met_coords versie
try:
    df = pd.read_csv(csv_path)
except FileNotFoundError:
    # Eerste run: begin met originele bestand
    df = pd.read_csv('/home/bart/beklimmingen_details.csv')
    if 'latitude' not in df.columns:
        df['latitude'] = None
    if 'longitude' not in df.columns:
        df['longitude'] = None
    df.to_csv(csv_path, index=False)

geolocator = Nominatim(user_agent="klimmetjes_geocodeer")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def zoek_coords(naam):
    # Verwijder alles na het eerste voorkomen van 'vanuit', 'via' of '/' uit de naam
    naam_clean = re.split(r'vanuit|via|/', naam, maxsplit=1)[0].strip()
    queries = [
        f"{naam_clean}, Nederland",
        f"{naam_clean}",
        f"{naam_clean}, Limburg, Nederland",
        f"{naam_clean}, Europe"
    ]
    for q in queries:
        try:
            locatie = geocode(q)
            if locatie:
                print(f"Gevonden via: '{q}'")
                return locatie.latitude, locatie.longitude
        except Exception as e:
            print(f"Fout bij {naam} met query '{q}': {e}")
    return None, None

def is_valid_coord(val):
    try:
        if pd.isna(val):
            return False
        if val is None:
            return False
        if str(val).strip() == '':
            return False
        if float(val) == 0.0:
            return False
        return True
    except:
        return False

for i, row in df.iterrows():
    if is_valid_coord(row['latitude']) and is_valid_coord(row['longitude']):
        print(f"Skip: {row['name']} heeft al coördinaten ({row['latitude']}, {row['longitude']})")
        continue
    naam = row['name']
    lat, lon = zoek_coords(naam)
    if lat and lon:
        df.at[i, 'latitude'] = lat
        df.at[i, 'longitude'] = lon
        print(f"{naam}: {lat}, {lon}")
        df.to_csv(csv_path, index=False)
    else:
        print(f"Geen coördinaten gevonden voor {naam}")
    time.sleep(1)

print(f"Klaar! Opgeslagen als {csv_path}")
