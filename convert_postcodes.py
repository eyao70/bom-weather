
import json
import urllib.request
from collections import defaultdict
from statistics import mean
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "schappim/australian-postcodes/master/"
    "australian-postcodes.json"
)

OUTPUT_FILE = Path("app/postcodes.json")

print("Downloading Australian postcode database...")

with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
    records = json.loads(response.read().decode("utf-8"))

grouped = defaultdict(list)

for record in records:
    postcode = str(record.get("postcode", "")).strip()
    lat = record.get("lat")
    lon = record.get("lon")

    # Exclude PO boxes and records without coordinates
    if (
        not postcode
        or record.get("category") != "Delivery Area"
        or not lat
        or not lon
    ):
        continue

    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        continue

    grouped[postcode].append({
        "suburb": record.get("suburb", "").title(),
        "state": record.get("state", ""),
        "lat": lat,
        "lon": lon
    })

postcodes = {}

for postcode, locations in grouped.items():
    postcodes[postcode] = {
        "lat": round(mean(x["lat"] for x in locations), 5),
        "lon": round(mean(x["lon"] for x in locations), 5),
        "state": sorted(set(x["state"] for x in locations)),
        "suburbs": sorted(set(x["suburb"] for x in locations))
    }

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(postcodes, file, indent=2, ensure_ascii=False)

print(f"Original records: {len(records):,}")
print(f"Unique postcodes: {len(postcodes):,}")
print(f"Saved to: {OUTPUT_FILE}")

print("3021 lookup:", postcodes.get("3021", "Not found"))
