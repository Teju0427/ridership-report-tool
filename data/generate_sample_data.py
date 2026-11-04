"""
Generates a SYNTHETIC (made-up) ridership dataset so we can test the app.

Each row = how many passengers boarded at one station, on one line,
during one hour of one day.

Columns: date, hour, line, station, passengers

Run:  python data/generate_sample_data.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # same "random" numbers every run -> reproducible

LINES = {
    "Fujikyu Railway": {
        "Otsuki": 1.0,           # transfer from JR Chuo line -> busy
        "Shimoyoshida": 0.5,     # Chureito Pagoda tourists
        "Mt.Fuji": 0.8,
        "Fuji-Q Highland": 0.9,  # amusement park
        "Kawaguchiko": 1.2,      # lake + bus hub -> busiest
    },
    "Local Bus": {
        "Kawaguchiko Station": 1.0,
        "Lake Kawaguchiko North": 0.4,
        "Fuji Subaru Line 5th Stn": 0.7,
        "Fujiyoshida City Office": 0.3,
    },
}

# Hour profile: commuters in morning/evening, tourists midday
HOUR_WEIGHT = {
    6: 0.3, 7: 0.9, 8: 1.0, 9: 0.8, 10: 0.9, 11: 1.0, 12: 0.8,
    13: 0.8, 14: 0.9, 15: 0.9, 16: 1.0, 17: 1.0, 18: 0.8, 19: 0.5,
    20: 0.3, 21: 0.2,
}

START = date(2026, 8, 1)
DAYS = 92  # Aug, Sep, Oct


def main():
    out = Path(__file__).parent / "sample_ridership.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "hour", "line", "station", "passengers"])
        for d in range(DAYS):
            day = START + timedelta(days=d)
            weekend = day.weekday() >= 5          # Sat=5, Sun=6
            day_factor = 1.4 if weekend else 1.0
            if day.month == 8 and 10 <= day.day <= 16:
                day_factor *= 1.6                 # Obon holiday peak
            for line, stations in LINES.items():
                base = 60 if line == "Fujikyu Railway" else 25
                for station, st_weight in stations.items():
                    for hour, h_weight in HOUR_WEIGHT.items():
                        mean = base * st_weight * h_weight * day_factor
                        passengers = max(0, int(random.gauss(mean, mean * 0.15)))
                        writer.writerow([day.isoformat(), hour, line, station, passengers])
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
