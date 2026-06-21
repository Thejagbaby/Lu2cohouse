#!/usr/bin/env python3
"""
agent2_poster.py — LU2COHOUSE Pinterest Pin Poster
Reads the next pin from pins_queue.json, posts it to Pinterest, removes it from queue.
Also writes every successfully posted pin to posted_pins.json so Agent 3 can
pull analytics on it and decide whether to create a variation.
"""

import json, os, sys, requests
from datetime import datetime

try:
    from config import PINTEREST_ACCESS_TOKEN, PINTEREST_API
except ImportError:
    print("ERROR: config.py not found. Cannot post without API credentials.")
    sys.exit(1)

DIR          = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE   = os.path.join(DIR, "pins_queue.json")
POSTED_FILE  = os.path.join(DIR, "posted_pins.json")
LOG_FILE     = os.path.join(DIR, "poster.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE) as f:
        return json.load(f)


def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)


def load_posted():
    if not os.path.exists(POSTED_FILE):
        return []
    with open(POSTED_FILE) as f:
        return json.load(f)


def save_posted(posted):
    with open(POSTED_FILE, "w") as f:
        json.dump(posted, f, indent=2)


def post_pin(pin):
    headers = {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "board_id":    pin["board_id"],
        "title":       pin["title"][:100],   # Pinterest maxLength=100
        "description": pin["description"],
        "link":        pin["link"],
        "media_source": {
            "source_type": "image_url",
            "url":         pin["image_url"],
        },
    }
    r = requests.post(f"{PINTEREST_API}/pins", headers=headers, json=payload, timeout=30)
    return r.status_code, r.json()


def track_pin(pin, pinterest_pin_id):
    """Save posted pin data so Agent 3 can read analytics on it later."""
    posted = load_posted()
    posted.append({
        "pinterest_pin_id": pinterest_pin_id,
        "product_id":       pin.get("product_id"),
        "image_num":        pin.get("image_num"),
        "board_id":         pin["board_id"],
        "title":            pin["title"],
        "description":      pin["description"],
        "link":             pin["link"],
        "image_url":        pin["image_url"],
        "posted_at":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_variation":     pin.get("is_variation", False),
        "variation_of":     pin.get("variation_of"),      # original pin ID if this is a variation
    })
    save_posted(posted)


def post_daily_pin():
    queue = load_queue()

    if not queue:
        log("Queue is empty. Run: python3 agent1_formatter.py --reset")
        sys.exit(0)

    pin = queue[0]
    log(f"Posting: Product {pin.get('product_id','?')} image {pin.get('image_num','?')} → board {pin['board_id']}")
    log(f"  Title: {pin['title']}")
    log(f"  Image: {pin['image_url']}")
    if pin.get("is_variation"):
        log(f"  [VARIATION] — scaling top performer product {pin.get('product_id')}")

    status, response = post_pin(pin)

    if status in (200, 201):
        pinterest_pin_id = response.get("id", "unknown")
        log(f"  SUCCESS — pin ID: {pinterest_pin_id}")
        track_pin(pin, pinterest_pin_id)
        queue.pop(0)
        save_queue(queue)
        log(f"  {len(queue)} pins remaining in queue")
    else:
        log(f"  FAILED — status {status}: {response}")
        if status == 401:
            log("  Token expired. Run oauth_demo.py on Mac to refresh.")
        sys.exit(1)


def main():
    post_daily_pin()

if __name__ == "__main__":
    main()
