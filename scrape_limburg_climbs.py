import requests
from bs4 import BeautifulSoup
import csv
import time
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://climbfinder.com/nl/ranglijst?l=26&p={}"

def get_climb_links(page):
    url = BASE_URL.format(page)
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = []
    for a in soup.find_all("a", class_="ranking-card-title"):
        href = a.get("href")
        if href and "nl/beklimmingen/" in href:
            links.append("https://climbfinder.com/" + href.lstrip("/"))
    return links

def get_climb_details(url):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    details = {}

    # Naam uit <title>
    title_tag = soup.find("title")
    details["name"] = title_tag.get_text(strip=True).split(" - ")[0] if title_tag else "Onbekend"

    # FAQ: lengte
    faq_length = soup.find("button", string=lambda s: s and ("hoe lang is de beklimming" in s.lower() or "lengte" in s.lower()))
    if faq_length:
        answer = faq_length.find_next("div", class_="accordion-body")
        details["length"] = answer.get_text(strip=True) if answer else "Onbekend"
    else:
        details["length"] = "Onbekend"

    # FAQ: stijgingspercentage/gemiddelde stijging
    faq_gradient = soup.find("button", string=lambda s: s and ("hoe steil" in s.lower() or "stijgingspercentage" in s.lower() or "gemiddelde stijging" in s.lower()))
    if faq_gradient:
        answer = faq_gradient.find_next("div", class_="accordion-body")
        details["avg_gradient"] = answer.get_text(strip=True) if answer else "Onbekend"
    else:
        details["avg_gradient"] = "Onbekend"

    # FAQ: steilste stuk/gedeelte
    faq_steilste = soup.find("button", string=lambda s: s and ("steilste stuk" in s.lower() or "steilste gedeelte" in s.lower()))
    if faq_steilste:
        answer = faq_steilste.find_next("div", class_="accordion-body")
        details["steepest_section"] = answer.get_text(strip=True) if answer else "Onbekend"
    else:
        details["steepest_section"] = "Onbekend"

    # FAQ: hoogte/elevatie
    faq_elevation = soup.find("button", string=lambda s: s and ("hoe hoog" in s.lower() or "hoogte" in s.lower() or "elevatie" in s.lower()))
    if faq_elevation:
        answer = faq_elevation.find_next("div", class_="accordion-body")
        details["elevation_gain"] = answer.get_text(strip=True) if answer else "Onbekend"
    else:
        details["elevation_gain"] = "Onbekend"

    # FAQ: duur/tijd (#faq-duration)
    faq_duration = soup.find("button", string=lambda s: s and ("hoe lang doe je over" in s.lower() or "duur" in s.lower() or "tijd" in s.lower()))
    if faq_duration:
        answer = faq_duration.find_next("div", class_="accordion-body")
        details["duration"] = answer.get_text(strip=True) if answer else "Onbekend"
    else:
        details["duration"] = "Onbekend"

    # Coordinates (latitude, longitude) from meta tags if available
    lat, lon = None, None
    meta_lat = soup.find("meta", attrs={"property": "place:location:latitude"})
    meta_lon = soup.find("meta", attrs={"property": "place:location:longitude"})
    if meta_lat and meta_lon:
        lat = meta_lat.get("content")
        lon = meta_lon.get("content")
    details["latitude"] = lat if lat else ""
    details["longitude"] = lon if lon else ""

    details["url"] = url
    return details

def write_csv(climbs, filename="beklimmingen_details.csv"):
    if not climbs:
        print("Geen klimmen gevonden. CSV niet aangemaakt.")
        return
    keys = climbs[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(climbs)

def read_existing_urls(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return set(row["url"] for row in reader if "url" in row)

if __name__ == "__main__":
    all_links = []
    total_pages = 30  # Scrape alle 30 pagina's
    for page in range(1, total_pages + 1):
        print(f"Zoek beklimmingen op pagina {page}...")
        links = get_climb_links(page)
        print(f"Gevonden {len(links)} beklimmingen op pagina {page}.")
        all_links.extend(links)
        time.sleep(1)  # Respectful delay

    print(f"Totaal gevonden links: {len(all_links)}")

    # Lees bestaande URLs uit CSV
    csv_file = "beklimmingen_details.csv"
    existing_urls = read_existing_urls(csv_file)
    print(f"Aantal bestaande beklimmingen in CSV: {len(existing_urls)}")

    climbs = []
    for i, url in enumerate(all_links, 1):
        if url in existing_urls:
            print(f"[{i}/{len(all_links)}] Al gescraped, skip: {url}")
            continue
        print(f"[{i}/{len(all_links)}] Scraping: {url}")
        details = get_climb_details(url)
        climbs.append(details)
        time.sleep(1)  # Respectful delay

    # Voeg nieuwe beklimmingen toe aan bestaande CSV
    if climbs:
        # Lees bestaande rows
        if os.path.exists(csv_file):
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing_rows = list(reader)
        else:
            existing_rows = []
        # Combineer en schrijf alles weg
        all_rows = existing_rows + climbs
        keys = all_rows[0].keys()
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"{len(climbs)} nieuwe klimmen toegevoegd aan {csv_file}")
    else:
        print("Geen nieuwe klimmen gevonden.")