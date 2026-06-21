#!/usr/bin/env python3
"""
agent3_analytics.py — LU2COHOUSE Pinterest Intelligence Agent

Every morning at 08:00 this agent:
  1. Reads analytics for every pin posted so far
  2. Scores each pin (saves + clicks × weight)
  3. Finds the single best top performer that hasn't been scaled yet
  4. Creates ONE variation of it (different image + tweaked title)
  5. Quietly inserts it at the front of the queue — posts next slot
  6. Writes a daily summary report

Scaling is intentionally understated:
  - Maximum 1 variation added per day
  - Minimum 14 days between scaling the same product
  - Maximum 4 total variations per product (after that, it's proven — let organic run)
  - Only scales if pin has been live 7+ days AND has real engagement
"""

import json, os, sys, requests, random
from datetime import datetime, date, timedelta

try:
    from config import PINTEREST_ACCESS_TOKEN, PINTEREST_API
except ImportError:
    print("ERROR: config.py not found.")
    sys.exit(1)

DIR             = os.path.dirname(os.path.abspath(__file__))
POSTED_FILE     = os.path.join(DIR, "posted_pins.json")
QUEUE_FILE      = os.path.join(DIR, "pins_queue.json")
OPT_HIST_FILE   = os.path.join(DIR, "optimization_history.json")
LEARNINGS_FILE  = os.path.join(DIR, "learnings.json")
LOG_FILE        = os.path.join(DIR, "analytics.log")

# ── Scoring weights ────────────────────────────────────────────────────────────
# Outbound clicks (to Etsy) = revenue intent — worth 5× a save
# Pin clicks (opening pin) = interest — worth 2× a save
WEIGHT_SAVE     = 1
WEIGHT_OUTBOUND = 5
WEIGHT_CLICK    = 2

# ── Top-performer thresholds ───────────────────────────────────────────────────
MIN_AGE_DAYS       = 7      # pin must be at least 7 days old to have real data
MIN_IMPRESSIONS    = 80     # ignore pins with tiny reach (not enough data)
MIN_SAVE_RATE      = 0.02   # 2% of impressions saved — proven quality
MIN_OUTBOUND_RATE  = 0.005  # 0.5% of impressions clicked to Etsy

# ── Scaling limits ─────────────────────────────────────────────────────────────
MAX_VARIATIONS_PER_PRODUCT = 4    # after 4 variations, stop — let it run organically
MIN_DAYS_BETWEEN_VARIATIONS = 14  # never scale same product twice within 14 days

# ── Image data ─────────────────────────────────────────────────────────────────
USABLE_IMAGES = {
    1:[1,2,3,4,7], 2:[1,2,3,4,5,6,7], 3:[1,2,3,4,5,8], 4:[1,2,3,4,5,8],
    5:[1,2,3,4,5,8], 6:[1,2,3,4,5,6], 7:[1,2,3,4,5,6,7], 8:[1,2,3,4,5,6],
    9:[1,2,3,4,5,6,9], 10:[1,2,3,4,5,6,9], 11:[1,2,3,4,5,6,9], 12:[1,2,3,4,5,8],
    13:[1,2,3,4,5,6,9], 14:[1,2,3,4,5,8], 15:[1,2,3,4,5,6,9], 16:[1,2,3,4,5,8],
    17:[1,2,3,4,5,6,9], 18:[1,2,3,4,5,8], 19:[1,2,3,4,5], 20:[1,2,3,4,5,8],
    21:[1,2,3,4,5,8], 22:[1,2,3,4,5,6,9], 23:[1,2,3,4,5,8], 24:[1,2,3,4,5,6,7,10],
    25:[1,2,3,4,5,6,9], 26:[1,2,3,4,5,6,9], 27:[1,2,3,4,5,8], 28:[1,2,3,4,5,6,7],
    29:[1,2,3,4,5,6,8], 30:[1,2,3,4,5,8], 31:[1,2,3,4,5,8], 32:[1,2,3,4,5,6,9],
    33:[1,2,3,4,5,8], 34:[1,2,3,4,5,8], 35:[1,2,3,4,5,6,9], 36:[1,2,3,4,5,8],
    37:[1,2,3,4,5,8], 38:[1,2,3,4,5,6,9], 39:[1,2,3,4,5,6,9],
}

# ── Title variation formulas ────────────────────────────────────────────────────
# Agent 3 cycles through these when scaling a top performer.
# Each targets a slightly different search intent or hook.
TITLE_VARIANTS = [
    lambda name, t: f"LU2COHOUSE Sew Your Own {name} | Easy Beginner {t} | PDF Instant Download",
    lambda name, t: f"LU2COHOUSE {name} | Bestselling {t} | Instant Download PDF Pattern",
    lambda name, t: f"LU2COHOUSE {name} | Sizes XXS–4XL | Beginner {t} Instant Download",
    lambda name, t: f"Sew Your Own {name} | LU2COHOUSE {t} | PDF Beginner Friendly Download",
]


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def auth_headers():
    return {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_pin_analytics(pin_id):
    """Pull 30-day analytics for a single pin."""
    end   = date.today()
    start = end - timedelta(days=30)
    url   = f"{PINTEREST_API}/pins/{pin_id}/analytics"
    params = {
        "start_date":   start.strftime("%Y-%m-%d"),
        "end_date":     end.strftime("%Y-%m-%d"),
        "metric_types": "IMPRESSION,SAVE,OUTBOUND_CLICK,PIN_CLICK",
    }
    r = requests.get(url, headers=auth_headers(), params=params, timeout=30)
    if r.status_code == 200:
        data = r.json()
        # API returns per-day breakdown — sum everything
        daily = data.get("all", {}).get("daily_metrics", [])
        totals = {"IMPRESSION": 0, "SAVE": 0, "OUTBOUND_CLICK": 0, "PIN_CLICK": 0}
        for day in daily:
            for m in day.get("metrics", {}):
                key = m.get("metric_type")
                if key in totals:
                    totals[key] += m.get("value", 0)
        return totals
    return None


def score_pin(metrics):
    """Calculate performance score. Higher = better."""
    imp = metrics.get("IMPRESSION", 0)
    if imp < MIN_IMPRESSIONS:
        return 0, 0, 0
    saves     = metrics.get("SAVE", 0)
    outbound  = metrics.get("OUTBOUND_CLICK", 0)
    clicks    = metrics.get("PIN_CLICK", 0)
    score     = (saves * WEIGHT_SAVE) + (outbound * WEIGHT_OUTBOUND) + (clicks * WEIGHT_CLICK)
    save_rate = saves / imp
    out_rate  = outbound / imp
    return score, save_rate, out_rate


def is_top_performer(metrics):
    """Returns True if this pin qualifies for scaling."""
    imp = metrics.get("IMPRESSION", 0)
    if imp < MIN_IMPRESSIONS:
        return False
    save_rate = metrics.get("SAVE", 0) / imp
    out_rate  = metrics.get("OUTBOUND_CLICK", 0) / imp
    return save_rate >= MIN_SAVE_RATE or out_rate >= MIN_OUTBOUND_RATE


def get_next_image(product_id, already_used_images):
    """Pick the next image for this product that hasn't been used yet."""
    available = USABLE_IMAGES.get(product_id, [])
    unused = [img for img in available if img not in already_used_images]
    if not unused:
        return None
    return unused[0]


def get_variation_title(original_title, name, variant_index):
    """Generate a title variation based on which variation number this is."""
    # Infer type from original title
    for t in ["Coat Sewing Pattern", "Jacket Sewing Pattern", "Hooded Jacket Sewing Pattern",
              "Funnel Neck Jacket Sewing Pattern", "Crop Jacket Sewing Pattern",
              "Quilted Vest Sewing Pattern", "Wide Leg Pants Sewing Pattern",
              "Blouse Sewing Pattern", "Cardigan Sewing Pattern"]:
        if t.lower() in original_title.lower():
            formula = TITLE_VARIANTS[variant_index % len(TITLE_VARIANTS)]
            return formula(name, t)
    # Fallback: use variant 1 formula with what we can extract
    formula = TITLE_VARIANTS[variant_index % len(TITLE_VARIANTS)]
    return formula(name, "Sewing Pattern")


def get_different_board(original_board_id):
    """Return a different board to avoid posting variation to the same board."""
    all_boards = [
        "1007399079088276465",  # Quilt Coat Patterns
        "1007399079088276466",  # Quilted Jacket Sewing
        "1007399079088276467",  # PDF Sewing Patterns
        "1007399079088276470",  # Sewing Inspiration
        "1007399079088276471",  # LU2COHOUSE Lookbook
        "1007399079088276472",  # Behind the Pattern
        "1007399079088276474",  # Beginner Sewing Patterns
        "1007399079088284457",  # LU2COHOUSE Products
    ]
    others = [b for b in all_boards if b != original_board_id]
    return random.choice(others)


def image_url_for(product_id, image_num):
    if product_id <= 2:
        folder = f"product%20{product_id}"
    else:
        folder = f"Product%20{product_id}"
    return f"https://raw.githubusercontent.com/Thejagbaby/Lu2cohouse/main/d/assets/products/{folder}/{image_num}.webp"


def build_variation(top_pin, opt_history):
    """Build a new pin dict that is a variation of top_pin."""
    pid = top_pin.get("product_id")
    if not pid:
        return None

    # Find all images already used for this product
    used_images = set()
    for record in opt_history.get("scaled", []):
        if record["product_id"] == pid:
            used_images.add(record["image_num"])
    used_images.add(top_pin.get("image_num"))

    next_img = get_next_image(pid, used_images)
    if not next_img:
        return None  # all images already used

    variation_count = sum(1 for r in opt_history.get("scaled", []) if r["product_id"] == pid)
    new_title = get_variation_title(top_pin["title"], top_pin["title"].split("|")[0].replace("LU2COHOUSE Sew Your Own", "").replace("LU2COHOUSE", "").strip(), variation_count)
    new_board = get_different_board(top_pin["board_id"])
    new_image = image_url_for(pid, next_img)

    return {
        "product_id":   pid,
        "image_num":    next_img,
        "title":        new_title,
        "description":  top_pin["description"],
        "link":         top_pin["link"],
        "board_id":     new_board,
        "image_url":    new_image,
        "is_variation": True,
        "variation_of": top_pin["pinterest_pin_id"],
    }


def can_scale(product_id, opt_history):
    """Check scaling limits before acting."""
    scaled = opt_history.get("scaled", [])
    product_scaled = [r for r in scaled if r["product_id"] == product_id]

    if len(product_scaled) >= MAX_VARIATIONS_PER_PRODUCT:
        return False, f"already scaled {len(product_scaled)}x (limit {MAX_VARIATIONS_PER_PRODUCT})"

    if product_scaled:
        last_date = datetime.strptime(product_scaled[-1]["scaled_at"], "%Y-%m-%d").date()
        days_since = (date.today() - last_date).days
        if days_since < MIN_DAYS_BETWEEN_VARIATIONS:
            return False, f"scaled {days_since} days ago (need {MIN_DAYS_BETWEEN_VARIATIONS})"

    return True, "ok"


def run_daily_report():
    log("=" * 60)
    log("Agent 3 — Daily Intelligence Report")
    log("=" * 60)

    posted = load_json(POSTED_FILE, [])
    if not posted:
        log("No posted pins yet. Nothing to analyse.")
        return

    opt_history = load_json(OPT_HIST_FILE, {"scaled": []})
    queue       = load_json(QUEUE_FILE, [])
    learnings   = load_json(LEARNINGS_FILE, {"image_performance": {}, "board_performance": {}})

    products_in_queue = set(p.get("product_id") for p in queue)

    today     = date.today()
    scored    = []
    top_count = 0

    log(f"Analysing {len(posted)} posted pins...")

    for pin in posted:
        pin_id   = pin.get("pinterest_pin_id")
        pid      = pin.get("product_id")
        posted_at = pin.get("posted_at", "")

        if not pin_id or pin_id == "unknown":
            continue

        # Only analyse pins that have been live long enough
        try:
            posted_date = datetime.strptime(posted_at[:10], "%Y-%m-%d").date()
            age_days = (today - posted_date).days
        except Exception:
            continue

        if age_days < MIN_AGE_DAYS:
            continue

        metrics = get_pin_analytics(pin_id)
        if not metrics:
            continue

        score, save_rate, out_rate = score_pin(metrics)
        is_top = is_top_performer(metrics)
        if is_top:
            top_count += 1

        scored.append({
            "pin":       pin,
            "score":     score,
            "save_rate": save_rate,
            "out_rate":  out_rate,
            "is_top":    is_top,
            "age_days":  age_days,
            "metrics":   metrics,
        })

        # Update learnings
        img_key = str(pin.get("image_num", "?"))
        board_key = pin.get("board_id", "?")
        learnings["image_performance"].setdefault(img_key, {"total_score": 0, "count": 0})
        learnings["image_performance"][img_key]["total_score"] += score
        learnings["image_performance"][img_key]["count"] += 1
        learnings["board_performance"].setdefault(board_key, {"total_score": 0, "count": 0})
        learnings["board_performance"][board_key]["total_score"] += score
        learnings["board_performance"][board_key]["count"] += 1

    save_json(LEARNINGS_FILE, learnings)

    log(f"Pins analysed: {len(scored)} | Top performers found: {top_count}")

    # ── Find the single best candidate to scale today ──────────────────────────
    top_candidates = sorted(
        [s for s in scored if s["is_top"]],
        key=lambda x: x["score"],
        reverse=True
    )

    scaled_today = False
    for candidate in top_candidates:
        pin = candidate["pin"]
        pid = pin.get("product_id")

        if not pid:
            continue

        # Don't scale if product already in the queue (don't double up)
        if pid in products_in_queue:
            log(f"  Product {pid} already in queue — skipping")
            continue

        ok, reason = can_scale(pid, opt_history)
        if not ok:
            log(f"  Product {pid} — cannot scale: {reason}")
            continue

        variation = build_variation(pin, opt_history)
        if not variation:
            log(f"  Product {pid} — no unused images left to create variation")
            continue

        # Insert at front of queue — posts at the very next scheduled slot
        queue.insert(0, variation)
        save_json(QUEUE_FILE, queue)

        # Record in history
        opt_history["scaled"].append({
            "product_id":    pid,
            "image_num":     variation["image_num"],
            "original_pin":  pin.get("pinterest_pin_id"),
            "scaled_at":     today.strftime("%Y-%m-%d"),
            "trigger_score": candidate["score"],
            "save_rate":     round(candidate["save_rate"] * 100, 2),
            "out_rate":      round(candidate["out_rate"] * 100, 2),
        })
        save_json(OPT_HIST_FILE, opt_history)

        log(f"  ✅ SCALING — Product {pid} image {pin.get('image_num')} → variation with image {variation['image_num']}")
        log(f"     Score: {candidate['score']} | Save rate: {round(candidate['save_rate']*100,2)}% | Etsy CTR: {round(candidate['out_rate']*100,2)}%")
        log(f"     Variation queued at front — posts next slot")
        scaled_today = True
        break  # one variation per day, no more

    if not scaled_today:
        log("  No scaling today — no pin hit threshold yet or all limits reached")

    # ── Summary ────────────────────────────────────────────────────────────────
    if scored:
        best = max(scored, key=lambda x: x["score"])
        bp   = best["pin"]
        log(f"\nTop pin this period: Product {bp.get('product_id')} image {bp.get('image_num')}")
        log(f"  Impressions: {best['metrics'].get('IMPRESSION',0)}")
        log(f"  Saves: {best['metrics'].get('SAVE',0)}  ({round(best['save_rate']*100,2)}%)")
        log(f"  Etsy clicks: {best['metrics'].get('OUTBOUND_CLICK',0)}  ({round(best['out_rate']*100,2)}%)")
        log(f"  Score: {best['score']}")
        log(f"  Variations created so far: {sum(1 for r in opt_history['scaled'] if r['product_id'] == bp.get('product_id'))}")

    total_variations = len(opt_history.get("scaled", []))
    log(f"\nTotal variations created all time: {total_variations}")
    log(f"Queue size: {len(queue)} pins remaining")
    log("=" * 60)


def main():
    run_daily_report()

if __name__ == "__main__":
    main()
