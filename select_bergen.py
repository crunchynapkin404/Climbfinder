import csv
import re
from itertools import combinations

def duration_to_seconds(duration_str, tempo):
    # Zoek de juiste tijd bij het gewenste tempo
    # tempo: "langzaam", "normaal", "snel"
    if tempo == "langzaam":
        match = re.search(r'langzaam.*?(\d{2}:\d{2}:\d{2})', duration_str)
    elif tempo == "normaal":
        match = re.search(r'11 km/u.*?(\d{2}:\d{2}:\d{2})', duration_str)
    elif tempo == "snel":
        match = re.search(r'15 km/u.*?(\d{2}:\d{2}:\d{2})', duration_str)
        if not match:
            match = re.search(r'snelste.*?(\d{2}:\d{2}:\d{2})', duration_str)
    else:
        match = re.search(r'(\d{2}):(\d{2}):(\d{2})', duration_str)
    if match:
        tijd = match.group(1)
        h, m, s = map(int, tijd.split(":"))
        return h * 3600 + m * 60 + s
    return 0

def main():
    aantal_bergen = int(input("Hoeveel bergen wil je doen? "))
    minuten_per_berg = int(input("Hoeveel minuten per berg? "))
    tempo = input("Wil je de bergen langzaam, normaal of snel op? ").strip().lower()
    gewenste_totaal = aantal_bergen * minuten_per_berg * 60

    with open("beklimmingen_details.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        climbs = [row for row in reader if row["duration"] != "Onbekend"]

    # Zet duur om naar seconden en filter op voldoende lange beklimmingen
    climbs = [
        {**c, "duration_sec": duration_to_seconds(c["duration"], tempo)}
        for c in climbs if duration_to_seconds(c["duration"], tempo) >= minuten_per_berg * 60
    ]

    # Vind alle combinaties van het juiste aantal bergen
    opties = []
    for combo in combinations(climbs, aantal_bergen):
        totaal = sum(c["duration_sec"] for c in combo)
        verschil = abs(totaal - gewenste_totaal)
        opties.append((combo, totaal, verschil))

    # Sorteer op verschil met gewenste totaal
    opties = sorted(opties, key=lambda x: x[2])[:3]

    print(f"\nBeste {len(opties)} opties voor {aantal_bergen} bergen van ~{minuten_per_berg} minuten ({tempo}):")
    for i, (combo, totaal, verschil) in enumerate(opties, 1):
        print(f"\nOptie {i}: totaal {totaal//60} min {totaal%60} sec (verschil {verschil//60} min {verschil%60} sec)")
        for climb in combo:
            print(f'  {climb["name"]}: {climb["duration"]} ({climb["url"]})')

if __name__ == "__main__":
    main()