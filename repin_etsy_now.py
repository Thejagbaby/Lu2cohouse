#!/usr/bin/env python3
"""
repin_etsy_now.py — Immediately repins specific Etsy-created pins to LU2COHOUSE boards.
Run once: python3 repin_etsy_now.py
"""

import json, sys, requests
from datetime import datetime

try:
    from config import PINTEREST_ACCESS_TOKEN, PINTEREST_API
except ImportError:
    print("ERROR: config.py not found.")
    sys.exit(1)

HISTORY_FILE = "repin_history.json"

BOARD_QUILTED_JACKET = "1007399079088276466"
BOARD_QUILT_COAT     = "1007399079088276465"
BOARD_INSPIRATION    = "1007399079088276470"
BOARD_BEGINNER       = "1007399079088276474"
BOARD_PDF            = "1007399079088276467"

# Etsy-created pins of LU2COHOUSE products — high value to repin
ETSY_PINS = [
    # Batch 1
    {"pin_id": "42221315255052698",   "board_id": BOARD_QUILTED_JACKET, "label": "Laurel Crop Jacket (35 saves)"},
    {"pin_id": "228839224811860099",  "board_id": BOARD_QUILTED_JACKET, "label": "Hooded Quilted Jacket (7 saves)"},
    {"pin_id": "173881235608588917",  "board_id": BOARD_QUILT_COAT,     "label": "Siena Quilt Coat (2 saves)"},
    {"pin_id": "415949715608644126",  "board_id": BOARD_QUILTED_JACKET, "label": "Rosa Quilted Jacket (1 save)"},
    {"pin_id": "195484440074722351",  "board_id": BOARD_QUILT_COAT,     "label": "Siena Quilt Coat II (1 save)"},
    {"pin_id": "393290979984694017",  "board_id": BOARD_BEGINNER,       "label": "Hooded Quilted Jacket (1 save)"},
    {"pin_id": "149182425122267677",  "board_id": BOARD_QUILT_COAT,     "label": "Blossom Quilt Coat"},
    {"pin_id": "802485227405528549",  "board_id": BOARD_INSPIRATION,    "label": "Hooded Quilted Jacket II"},
    {"pin_id": "1067282812336825300", "board_id": BOARD_QUILT_COAT,     "label": "Siena Quilt Coat III"},
    # Batch 2
    {"pin_id": "371617406776364476",  "board_id": BOARD_PDF,            "label": "Side Tie Tank Blouse"},
    {"pin_id": "311874342966880092",  "board_id": BOARD_QUILTED_JACKET, "label": "Funnel Neck Jacket"},
    {"pin_id": "834010424789638847",  "board_id": BOARD_PDF,            "label": "20 Quilted Sewing Patterns Bundle"},
    {"pin_id": "783837510187813130",  "board_id": BOARD_QUILT_COAT,     "label": "Florence Quilt Coat"},
]

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def load_history():
    try:
        with open(HISTORY_FILE) as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_history(history_set):
    with open(HISTORY_FILE) as f:
        existing = json.load(f)
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(set(existing) | history_set), f, indent=2)

def repin(pin_id, board_id):
    headers = {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"board_id": board_id, "source_pin_id": pin_id}
    r = requests.post(f"{PINTEREST_API}/pins", headers=headers, json=payload, timeout=30)
    return r.status_code, r.json()

def main():
    history = load_history()
    new_history = set()
    success = 0

    for p in ETSY_PINS:
        pin_id = p["pin_id"]
        if pin_id in history:
            log(f"  SKIP (already reposted): {p['label']}")
            continue

        log(f"Repinning: {p['label']}")
        status, response = repin(pin_id, p["board_id"])

        if status in (200, 201):
            log(f"  SUCCESS — new pin ID: {response.get('id', 'unknown')}")
            new_history.add(pin_id)
            success += 1
        else:
            log(f"  FAILED — {status}: {str(response)[:150]}")
            if status == 401:
                log("  Token expired. Refresh it first.")
                break

    if new_history:
        # Merge into history file safely
        try:
            with open(HISTORY_FILE) as f:
                existing = json.load(f)
        except FileNotFoundError:
            existing = []
        with open(HISTORY_FILE, "w") as f:
            json.dump(list(set(existing) | new_history), f, indent=2)

    log(f"\nDone — {success}/{len(ETSY_PINS)} pins repinned.")

if __name__ == "__main__":
    main()
