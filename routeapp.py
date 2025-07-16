import streamlit as st
from fitparse import FitFile
import folium
from streamlit_folium import st_folium
import pandas as pd
import math
import re
from collections import Counter

def draw_route_map(route_points, start_coords, route_latlon=None):
    m = folium.Map(location=start_coords, zoom_start=7)
    if route_latlon:
        folium.PolyLine(route_latlon, color="blue", weight=4, opacity=0.7).add_to(m)
    else:
        folium.PolyLine([p["loc"] for p in route_points], color="blue", weight=4, opacity=0.7).add_to(m)
    folium.Marker(route_points[0]["loc"], tooltip="Start", icon=folium.Icon(color="green")).add_to(m)
    for p in route_points[1:-1]:
        folium.Marker(p["loc"], tooltip=p["naam"], icon=folium.Icon(color="red", icon="flag")).add_to(m)
    folium.Marker(route_points[-1]["loc"], tooltip="Finish", icon=folium.Icon(color="blue")).add_to(m)
    m.add_child(folium.LatLngPopup())
    return m

def has_duplicate_segments(route_geom):
    # Maak segmenten als (min(p1,p2), max(p1,p2)) zodat richting niet uitmaakt
    segments = [tuple(sorted([tuple(route_geom[i]), tuple(route_geom[i+1])])) for i in range(len(route_geom)-1)]
    counts = Counter(segments)
    return any(v > 1 for v in counts.values())

def show_route_summary(route_points, total_dist, min_afstand, max_afstand, afstand_tolerantie):
    st.write(f"Routeafstand: {round(total_dist,1)} km (min: {min_afstand}, max: {max_afstand}, tolerantie: {afstand_tolerantie})")

def show_workout_steps(steps, adviezen, start_coords):
    st.write("Workout stappen en adviezen worden hier getoond.")

st.title(".fit Training naar Route Planner")

uploaded_file = st.file_uploader("Upload je .fit bestand", type=["fit"])

route_points = []
start_coords = [52.3702, 4.8952]  # Dummy startlocatie zodat start_coords altijd bestaat

if uploaded_file:
    fitfile = FitFile(uploaded_file)
    steps = list(fitfile.get_messages('workout_step'))
    st.session_state['steps'] = steps
    st.session_state['fitfile_uploaded'] = True
elif 'steps' in st.session_state and st.session_state.get('fitfile_uploaded', False):
    steps = st.session_state['steps']
else:
    steps = []

route_points = []  # Zorg dat route_points altijd is geïnitialiseerd

if steps:
    st.write(f"Aantal gevonden workout_steps: {len(steps)}")
    if not steps:
        st.error("Geen workout_steps gevonden in het .fit-bestand.")
    else:
        st.write("Kies je startlocatie op de kaart:")
        # Dummy startlocatie (Amsterdam)
        start_coords = [52.3702, 4.8952]
        m = folium.Map(location=start_coords, zoom_start=7)
        # Laad klimmetjes uit CSV
        df_klim = pd.read_csv('/home/bart/beklimmingen_details_met_coords.csv')
        # Probeer latitude/longitude te vullen indien aanwezig, anders overslaan
        def parse_lat_lon(row):
            try:
                lat = float(str(row['latitude']).replace(',', '.')) if not pd.isna(row['latitude']) and str(row['latitude']).strip() != '' else None
                lon = float(str(row['longitude']).replace(',', '.')) if not pd.isna(row['longitude']) and str(row['longitude']).strip() != '' else None
                if lat is not None and lon is not None:
                    return [lat, lon]
                else:
                    return None
            except Exception as e:
                print(f"Parse fout: {row['name']} {row['latitude']} {row['longitude']} {e}")
                return None
        df_klim['loc'] = df_klim.apply(parse_lat_lon, axis=1)
        # Filter alleen klimmetjes met locatie
        klimmetjes = [
            {"naam": row['name'], "loc": row['loc'], "url": row['url']} 
            for _, row in df_klim.iterrows() if row['loc'] is not None
        ]
        st.write(f"Aantal klimmetjes met locatie: {len(klimmetjes)}")
        # Verwijder voorbeeld coördinaten
        # Bepaal geadviseerde klimmetjes
        gebruikte_klims = set()
        adviezen = []
        for i, step in enumerate(steps):
            data = {d.name: d.value for d in step}
            perc = None
            if 'wkt_step_name' in data and '@' in data['wkt_step_name']:
                try:
                    perc = int(data['wkt_step_name'].split('@')[1].replace('%',''))
                except:
                    perc = None
            duur = data.get('duration_time', 0)
            if perc is not None and perc >= 75:
                adv_klim = next((k for k in klimmetjes if duur >= k.get('min_dur', 0) and k['naam'] not in gebruikte_klims), None)
                if adv_klim:
                    gebruikte_klims.add(adv_klim['naam'])
                    adviezen.append(adv_klim)
        # Voeg markers toe voor alleen geadviseerde klimmetjes
        for klim in adviezen:
            folium.Marker(klim["loc"], tooltip=klim["naam"]).add_to(m)
        # Voeg Click-for-marker toe zodat gebruiker kan klikken
        m.add_child(folium.LatLngPopup())
        # Laat gebruiker startpunt kiezen
        map_data = st_folium(m, width=700, height=500)
        # Gebruik session_state om startpunt te onthouden
        if 'start_coords' not in st.session_state:
            st.session_state['start_coords'] = start_coords
        if map_data and map_data.get("last_clicked"):
            st.session_state['start_coords'] = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
        start_coords = st.session_state['start_coords']
        st.success(f"Gekozen startpunt: {start_coords}")
        # Extra: invoerveld voor maximale en minimale routeafstand
        gewenste_afstand = st.number_input("Gewenste routeafstand (km)", min_value=10, max_value=300, value=80)
        afstand_tolerantie = 5  # km
        min_afstand = gewenste_afstand - afstand_tolerantie
        max_afstand = gewenste_afstand + afstand_tolerantie
        # Kies tempo
        tempo_opties = {'Laag (7 km/u)': 7, 'Middel (11 km/u)': 11, 'Hoog (15 km/u)': 15}
        tempo_keuze = st.selectbox('Kies je klimtempo', list(tempo_opties.keys()), index=1)
        tempo_kmh = tempo_opties[tempo_keuze]
        def extract_time(duration_str, kmh):
            # Zoek de tijd bij de juiste snelheid
            if not isinstance(duration_str, str):
                return None
            match = re.search(rf'{kmh} km/u.*?(\d\d:\d\d:\d\d)', duration_str)
            if match:
                t = match.group(1)
                h, m, s = map(int, t.split(':'))
                return h*3600 + m*60 + s
            return None
        for klim in klimmetjes:
            row = df_klim[df_klim['name'] == klim['naam']].iloc[0]
            klim['min_dur'] = extract_time(row['duration'], tempo_kmh) or 0
        # Validatie: check of startpunt in Nederland ligt (simpele bounding box)
        nl_bbox = {
            'lat_min': 50.75,
            'lat_max': 53.55,
            'lon_min': 3.35,
            'lon_max': 7.22
        }
        if not (nl_bbox['lat_min'] <= start_coords[0] <= nl_bbox['lat_max'] and nl_bbox['lon_min'] <= start_coords[1] <= nl_bbox['lon_max']):
            st.warning("Let op: je gekozen startpunt ligt buiten Nederland. Kies een locatie binnen Nederland voor een geldige route.")
        st.markdown("---")
        # Filter klimmetjes in de buurt (binnen 20 km van startlocatie)
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
            return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))
        klim_buurt = []
        for klim in klimmetjes:
            lat, lon = klim['loc']
            dist = haversine(start_coords[0], start_coords[1], lat, lon)
            if dist <= 20:
                klim_buurt.append({"naam": klim['naam'], "loc": klim['loc'], "url": klim['url']})
        # Gebruik deze klimmetjes als kandidaten voor de route
        klim_candidates = klim_buurt
        st.write(f"Aantal klimmetjes in de buurt (binnen 20 km): {len(klim_candidates)}")
        # Alleen na klik: adviezen, route en workout-stappen
        if map_data and map_data.get("last_clicked"):
            # Adviesketen opbouwen: steeds dichtstbijzijnde klim ≤ 30 km van vorige
            gebruikte_klims = set()
            adviezen = []
            min_tussenafstand = 0.5  # minder streng, mag dichterbij
            max_tussenafstand = 100  # minder streng, mag verder weg
            stap = 2
            tussenafstand = min_tussenafstand
            route_ok = False
            best_route_points = None
            best_total_dist = 0
            while not route_ok and tussenafstand <= max_tussenafstand:
                gebruikte_klims.clear()
                adviezen.clear()
                last_point = start_coords
                for i, step in enumerate(steps):
                    data = {d.name: d.value for d in step}
                    perc = None
                    if 'wkt_step_name' in data and '@' in data['wkt_step_name']:
                        try:
                            perc = int(data['wkt_step_name'].split('@')[1].replace('%',''))
                        except:
                            perc = None
                    duur = data.get('duration_time', 0)
                    if perc is not None and perc >= 75:
                        candidates = []
                        for k in klim_candidates:
                            reden = []
                            if k['naam'] in gebruikte_klims:
                                reden.append('al gebruikt')
                            dist = haversine(last_point[0], last_point[1], k['loc'][0], k['loc'][1])
                            if dist < tussenafstand or dist > max_tussenafstand:
                                reden.append(f"afstand {round(dist,1)} buiten range [{tussenafstand}, {max_tussenafstand}]")
                            if duur < k.get('min_dur', 0):
                                reden.append(f"duur {duur}s < min_dur {k.get('min_dur', 0)}s")
                            if not reden:
                                candidates.append(k)
                        # Kies nu de dichtstbijzijnde klim in plaats van de verste
                        next_klim = min(
                            candidates,
                            key=lambda k: haversine(last_point[0], last_point[1], k['loc'][0], k['loc'][1]),
                            default=None
                        )
                        if next_klim:
                            gebruikte_klims.add(next_klim['naam'])
                            adviezen.append(next_klim)
                            last_point = next_klim['loc']
                # Routeplanning: start → adviezen → start
                route_points = [
                    {"naam": "Start", "loc": start_coords, "type": "start"}
                ] + [
                    {"naam": k["naam"], "loc": k["loc"], "type": "klim"} for k in adviezen
                ] + [
                    {"naam": "Finish", "loc": start_coords, "type": "finish"}
                ]
                def point_dist(a, b):
                    return haversine(a[0], a[1], b[0], b[1])
                total_dist = 0
                for i in range(len(route_points)-1):
                    total_dist += point_dist(route_points[i]["loc"], route_points[i+1]["loc"])
                # Sla de beste (kortste binnen tolerantie) route op
                if min_afstand <= total_dist <= max_afstand and total_dist > best_total_dist:
                    best_route_points = list(route_points)
                    best_total_dist = total_dist
                if total_dist >= min_afstand or tussenafstand == max_tussenafstand or total_dist > max_afstand:
                    route_ok = True
                else:
                    tussenafstand += stap
            # Gebruik de beste gevonden route binnen max_afstand
            if best_route_points is not None:
                route_points = best_route_points
                total_dist = best_total_dist
                # Toon debug info alleen voor de beste route
            m = folium.Map(location=start_coords, zoom_start=7)
            folium.PolyLine([p["loc"] for p in route_points], color="blue", weight=4, opacity=0.7).add_to(m)
            folium.Marker(route_points[0]["loc"], tooltip="Start", icon=folium.Icon(color="green")).add_to(m)
            for p in route_points[1:-1]:
                folium.Marker(p["loc"], tooltip=p["naam"], icon=folium.Icon(color="red", icon="flag")).add_to(m)
            folium.Marker(route_points[-1]["loc"], tooltip="Finish", icon=folium.Icon(color="blue")).add_to(m)
            # OpenRouteService route ophalen
            import openrouteservice
            ors_api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMxNmFmNjM2YzdiODQwMDc4NGI3MDIyNGM2NzA3MWYzIiwiaCI6Im11cm11cjY0In0="
            client = openrouteservice.Client(key=ors_api_key)
            coords = [p["loc"][::-1] for p in route_points]  # ORS verwacht [lon, lat]
            route_geom = None  # Add this before the try block

            try:
                ors_route = client.directions(coords, profile='cycling-regular', format='geojson')
                route_geom = ors_route['features'][0]['geometry']['coordinates']
                route_latlon = [[lat, lon] for lon, lat in route_geom]
                m = folium.Map(location=start_coords, zoom_start=7)
                folium.PolyLine(route_latlon, color="blue", weight=4, opacity=0.7).add_to(m)
            except Exception as e:
                st.warning(f"ORS route ophalen mislukt: {e}. Er wordt een rechte lijn getoond.")
                m = folium.Map(location=start_coords, zoom_start=7)
                folium.PolyLine([p["loc"] for p in route_points], color="blue", weight=4, opacity=0.7).add_to(m)
            # Check direct na try/except
            if route_geom is not None and has_duplicate_segments(route_geom):
                st.warning("Let op: deze route bevat stukken weg die meer dan 1x worden gebruikt. Dit is soms niet te voorkomen met de huidige klimvolgorde.")
            # Markers alleen voor workout-adviezen
            for p in route_points[1:-1]:
                folium.Marker(p["loc"], tooltip=p["naam"], icon=folium.Icon(color="red", icon="flag")).add_to(m)
            m.add_child(folium.LatLngPopup())
            map_data = st_folium(m, width=700, height=500)
            show_route_summary(route_points, total_dist, min_afstand, max_afstand, afstand_tolerantie)
            st.write("**Workout stappen en routewens:**")
            show_workout_steps(steps, adviezen, start_coords)
else:
    st.info("Klik op de kaart om een startpunt te kiezen. Daarna verschijnen de klimadviezen.")
# Voeg mogelijkheid toe om extra waypoints te kiezen via klikken op de kaart
if 'waypoints' not in st.session_state:
    st.session_state['waypoints'] = []

st.write("Klik op de kaart om extra punten toe te voegen aan de route (waypoints). Herlaad de pagina om te resetten.")

# Dummy functies voor route samenvatting en workout stappen
def show_route_summary(route_points, total_dist, min_afstand, max_afstand, afstand_tolerantie):
    st.write(f"Routeafstand: {round(total_dist,1)} km (min: {min_afstand}, max: {max_afstand}, tolerantie: {afstand_tolerantie})")

def show_workout_steps(steps, adviezen, start_coords):
    st.write("Workout stappen en adviezen worden hier getoond.")

# Default locatie aanpassen
start_coords = [50.8608, 6.0013]  # Altijd deze default

# Voeg waypoints toe aan de route_points tussen start en finish vóór het tekenen van de kaart
if 'waypoints' not in st.session_state:
    st.session_state['waypoints'] = []
waypoints = st.session_state['waypoints']
if waypoints and len(route_points) >= 2:
    route_points = (
        [route_points[0]] +
        [{"naam": f"Waypoint {i+1}", "loc": wp, "type": "waypoint"} for i, wp in enumerate(waypoints)] +
        route_points[1:]
    )

# Alleen als er een geldige route is, ORS aanroepen en kaart tekenen
if len(route_points) >= 2:
    import openrouteservice
    ors_api_key = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjMxNmFmNjM2YzdiODQwMDc4NGI3MDIyNGM2NzA3MWYzIiwiaCI6Im11cm11cjY0In0="
    client = openrouteservice.Client(key=ors_api_key)
    coords = [p["loc"][::-1] for p in route_points]  # ORS verwacht [lon, lat]
    route_geom = None
    try:
        ors_route = client.directions(coords, profile='cycling-regular', format='geojson')
        route_geom = ors_route['features'][0]['geometry']['coordinates']
        route_latlon = [[lat, lon] for lon, lat in route_geom]
    except Exception as e:
        st.warning(f"ORS route ophalen mislukt: {e}. Er wordt een rechte lijn getoond.")
        route_latlon = None
    m = draw_route_map(route_points, start_coords, route_latlon if route_geom else None)
    map_data = st_folium(m, width=700, height=500)
    if map_data and map_data.get("last_clicked"):
        clicked = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
        if clicked not in st.session_state['waypoints'] and clicked != start_coords:
            st.session_state['waypoints'].append(clicked)
    if waypoints:
        st.write(f"Extra waypoints: {waypoints}")
    if route_geom is not None and has_duplicate_segments(route_geom):
        st.warning("Let op: deze route bevat stukken weg die meer dan 1x worden gebruikt. Dit is soms niet te voorkomen met de huidige klimvolgorde.")
    # Dummy summary en workout output
    show_route_summary(route_points, 0, 0, 0, 0)
    show_workout_steps([], [], start_coords)
else:
    st.info("Er is nog geen route om te tonen. Kies eerst een startpunt en upload een .fit-bestand.")