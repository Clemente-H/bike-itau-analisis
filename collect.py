import requests
import csv
import os
from datetime import datetime, timezone

STATION_INFO_URL = "https://santiago.publicbikesystem.net/customer/gbfs/v2/es/station_information"
STATION_STATUS_URL = "https://santiago.publicbikesystem.net/customer/gbfs/v2/es/station_status"
OUTPUT_FILE = "data/station_status.csv"

FIELDS = [
    "timestamp", "station_id", "station_name", "lat", "lon",
    "capacity", "bikes_available", "docks_available",
    "bikes_disabled", "docks_disabled", "is_renting", "is_returning",
]


def fetch_json(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    info = fetch_json(STATION_INFO_URL)
    status = fetch_json(STATION_STATUS_URL)

    info_map = {s["station_id"]: s for s in info["data"]["stations"]}

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs("data", exist_ok=True)
    file_exists = os.path.isfile(OUTPUT_FILE)

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()

        stations = status["data"]["stations"]
        for s in stations:
            sid = s["station_id"]
            info_s = info_map.get(sid, {})
            writer.writerow({
                "timestamp": timestamp,
                "station_id": sid,
                "station_name": info_s.get("name", ""),
                "lat": info_s.get("lat", ""),
                "lon": info_s.get("lon", ""),
                "capacity": info_s.get("capacity", ""),
                "bikes_available": s.get("num_bikes_available", ""),
                "docks_available": s.get("num_docks_available", ""),
                "bikes_disabled": s.get("num_bikes_disabled", ""),
                "docks_disabled": s.get("num_docks_disabled", ""),
                "is_renting": s.get("is_renting", ""),
                "is_returning": s.get("is_returning", ""),
            })

    print(f"[{timestamp}] {len(stations)} estaciones guardadas.")


if __name__ == "__main__":
    main()
