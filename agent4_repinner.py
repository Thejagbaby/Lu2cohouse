#!/usr/bin/env python3
"""
agent4_repinner.py — LU2COHOUSE Pinterest Repin Agent
Searches Pinterest for high-quality sewing pins and repins them to our boards.
Adds human-like curation behaviour — signals active account to Pinterest algorithm.
Run: python3 agent4_repinner.py          → posts 1 repin
Run: python3 agent4_repinner.py --refresh → rebuilds the repin pool from search
"""

import json, os, sys, random, requests
from datetime import datetime

try:
    from config import PINTEREST_ACCESS_TOKEN, PINTEREST_API
except ImportError:
    print("ERROR: config.py not found.")
    sys.exit(1)

DIR = os.path.dirname(os.path.abspath(__file__))
POOL_FILE    = os.path.join(DIR, "repin_pool.json")
HISTORY_FILE = os.path.join(DIR, "repin_history.json")
LOG_FILE     = os.path.join(DIR, "repinner.log")

# Our boards to repin INTO
BOARD_QUILTED_JACKET = "1007399079088276466"
BOARD_QUILT_COAT     = "1007399079088276465"
BOARD_INSPIRATION    = "1007399079088276470"
BOARD_BEGINNER       = "1007399079088276474"
BOARD_BEHIND         = "1007399079088276472"
BOARD_PDF            = "1007399079088276467"

# Search queries + which board each repin lands on
SEARCH_TARGETS = [
    {"query": "quilted jacket sewing pattern",       "board": BOARD_QUILTED_JACKET},
    {"query": "hooded quilted jacket pattern",       "board": BOARD_QUILTED_JACKET},
    {"query": "womens jacket sewing pattern",        "board": BOARD_QUILTED_JACKET},
    {"query": "quilted coat sewing pattern",         "board": BOARD_QUILT_COAT},
    {"query": "coat sewing pattern beginner",        "board": BOARD_QUILT_COAT},
    {"query": "coat patterns for women",             "board": BOARD_QUILT_COAT},
    {"query": "beginner sewing patterns women",      "board": BOARD_BEGINNER},
    {"query": "easy sewing patterns beginners",      "board": BOARD_BEGINNER},
    {"query": "PDF sewing patterns instant download","board": BOARD_PDF},
    {"query": "sewing patterns for women PDF",       "board": BOARD_INSPIRATION},
    {"query": "sewing inspiration women fashion",    "board": BOARD_INSPIRATION},
    {"query": "sewing process behind the scenes",    "board": BOARD_BEHIND},
]

# Pool refreshes automatically when fewer than this many pins remain
MIN_POOL_SIZE = 15


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_pool():
    if not os.path.exists(POOL_FILE):
        return []
    with open(POOL_FILE) as f:
        return json.load(f)


def save_pool(pool):
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, indent=2)


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE) as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def auth_headers():
    return {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def search_pins(query, page_size=25):
    url = f"{PINTEREST_API}/search/pins"
    params = {"query": query, "page_size": page_size}
    r = requests.get(url, headers=auth_headers(), params=params, timeout=30)
    if r.status_code == 200:
        return r.json().get("items", [])
    log(f"  Search failed ({r.status_code}) for '{query}' — {r.text[:100]}")
    return []


def refresh_pool():
    log("Refreshing repin pool via Pinterest search...")
    history_set = set(load_history())
    pool = []
    seen_ids = set()

    for target in SEARCH_TARGETS:
        pins = search_pins(target["query"])
        for pin in pins:
            pin_id = pin.get("id")
            if not pin_id:
                continue
            if pin_id in history_set:
                continue  # already reposted
            if pin_id in seen_ids:
                continue  # duplicate across queries
            seen_ids.add(pin_id)
            pool.append({
                "pin_id":  pin_id,
                "board_id": target["board"],
                "query":   target["query"],
            })

    save_pool(pool)
    log(f"Pool refreshed: {len(pool)} candidate pins ready")
    return pool


def do_repin(pin_id, board_id):
    payload = {"board_id": board_id, "source_pin_id": pin_id}
    r = requests.post(f"{PINTEREST_API}/pins", headers=auth_headers(), json=payload, timeout=30)
    return r.status_code, r.json()


def post_daily_repin():
    pool = load_pool()

    if len(pool) < MIN_POOL_SIZE:
        pool = refresh_pool()

    if not pool:
        log("No pins in pool and search returned nothing. Check API access.")
        sys.exit(0)

    history = load_history()
    history_set = set(history)
    attempts = 0

    while pool and attempts < 15:
        idx = random.randint(0, len(pool) - 1)
        candidate = pool.pop(idx)
        attempts += 1

        pin_id  = candidate["pin_id"]
        board_id = candidate["board_id"]

        if pin_id in history_set:
            continue

        log(f"Repinning pin {pin_id} → board {board_id}  [{candidate['query']}]")
        status, response = do_repin(pin_id, board_id)

        if status in (200, 201):
            log(f"  SUCCESS — new pin ID: {response.get('id', 'unknown')}")
            history.append(pin_id)
            save_pool(pool)
            save_history(history)
            return
        else:
            log(f"  FAILED — status {status}: {str(response)[:120]}")
            if status == 401:
                log("  Token expired. Run oauth_demo.py on Mac to refresh.")
                save_pool(pool)
                save_history(history)
                sys.exit(1)

    log("Could not post a repin after multiple attempts.")
    save_pool(pool)
    save_history(history)


def main():
    if "--refresh" in sys.argv:
        refresh_pool()
    else:
        post_daily_repin()


if __name__ == "__main__":
    main()
