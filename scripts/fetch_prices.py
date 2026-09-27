"""Retail prices for the eight modeled nuts: fetch, record and parse.

Writes
  data/prices/prices.csv         one row per product package and price channel,
                                 dated, with URL
  data/prices/prices_by_nut.csv  per nut: each retailer's primary row and the
                                 min/median/max $/kg
  data/prices/MANIFEST.json      url, sha256 and fetched_at for every raw file;
                                 column definitions; the primary-row rule;
                                 cross-checks

Sources and how each was read (all on 2026-09-23, US Eastern):

  nuts.com (specialty online seller). Fetched by this script. nuts.com is a Shopify
    store: each product's public JSON (https://nuts.com/products/<handle>.js) lists
    every package variant with its price in cents, availability and net quantity
    (unit_price_measurement). The raw JSON is saved to raw/nuts_com/<handle>.json.
    The product page HTML shows the same prices (checked on the hazelnut page on
    2026-09-23).

  Walmart (big-box). The script requests https://www.walmart.com/ip/<usItemId> and
    reads price, seller, stock and label fields from the page's own __NEXT_DATA__
    JSON, saving the HTML gzipped to raw/walmart/ip_<usItemId>.html.gz. On
    2026-09-23 Walmart served three such pages to curl (stored), then answered a
    scripted run for all 15 products with its bot challenge ("Robot or human?"). The
    script never tries to get past a challenge: a refused page falls back to a
    stored page if there is one, else to the browser record
    raw/walmart/walmart_browser_capture_2026-09-23.json (the same fields, read in a
    browser with WALMART_CAPTURE_JS below). how_read says which. Walmart prices by
    location: every read resolved ZIP 20001 / store 3035 from the visitor IP.

  Costco (warehouse club). Documented manual record
    raw/costco/costco_browser_capture_2026-09-23.json. The in-warehouse price is
    rendered client-side for the selected warehouse, so a scripted fetch cannot see
    it; it was read in a browser with COSTCO_CAPTURE_JS below (warehouse Washington
    DC, delivery ZIP 20001, both picked by costco.com from the visitor IP).

  Target (big-box). Documented manual record of one search-results listing,
    raw/target/target_search_listing_2026-09-23.json. Target's search API refused
    scripted requests (PerimeterX, HTTP 435), and a product page then showed a
    human-verification challenge in the browser, which was not attempted. Only
    walnut, almond and peanut lines were read.

Usage
  .venv/bin/python scripts/fetch_prices.py
      refetch nuts.com and Walmart, rebuild outputs
  .venv/bin/python scripts/fetch_prices.py --offline
      rebuild outputs from raw files (sha256-checked)
  .venv/bin/python scripts/fetch_prices.py --no-walmart
      refetch nuts.com only; Walmart from cache/record

Prices move: a refetch on another day writes that day's prices and retrieval dates.
The manual Costco and Target records keep their 2026-09-23 dates until someone
recaptures them.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "prices"
RAW = OUT / "raw"
MANIFEST = OUT / "MANIFEST.json"
EASTERN = ZoneInfo("America/New_York")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

OZ_G = 28.349523125
LB_G = 453.59237
MAX_PRIMARY_G = 1500.0  # largest package eligible to be a retailer's primary row

NUTS = [
    "walnut",
    "almond",
    "pistachio",
    "pecan",
    "hazelnut",
    "macadamia",
    "cashew",
    "peanut",
]
RETAILERS = {
    "nuts.com": "specialty_online",
    "Walmart": "big_box",
    "Costco": "warehouse_club",
    "Target": "big_box",
}

# Vocabulary (see MANIFEST "columns"):
#   processing: raw | dry_roasted | oil_roasted | roasted | not_stated
#   salt:       unsalted | salted | not_stated
#   shell:      shelled | in_shell
OK_PROCESSING = {"raw", "dry_roasted", "not_stated"}
OK_SALT = {"unsalted", "not_stated"}

# -------------------------------------------------------------------------------------
# Browser capture snippets (run in the page's console / devtools; they only read the
# page).

WALMART_CAPTURE_JS = (
    r"""JSON.stringify((() => { const nd = JSON.parse(document.getElementById('__NEXT"""
    r"""_DATA__').textContent); const d = nd.props.pageProps.initialData.data; const """
    r"""p = d.product; const idml = d.idml || {}; const pi = p.priceInfo || {}; """
    r"""const ad = (d.contentLayout?.modules || []).map(m => m.configs?.ad).find(a """
    r"""=> a && a.zipCode) || {}; return {page_url: location.href, captured_at_utc: """
    r"""new Date().toISOString(), usItemId: p.usItemId, name: p.name, brand: p.brand,"""
    r""" seller: p.sellerName, availability: p.availabilityStatus, currentPrice: """
    r"""{price: pi.currentPrice?.price ?? null, priceString: """
    r"""pi.currentPrice?.priceString ?? null}, wasPrice: pi.wasPrice?.priceString ?? """
    r"""null, unitPrice: pi.unitPrice?.priceString ?? null, ingredients: """
    r"""idml.ingredients?.ingredients?.value ?? null, specs: (idml.specifications || """
    r"""[]).filter(s => /weight|size|net content|flavor|nut type|food """
    r"""form|preparation|organic/i.test(s.name)).map(s => s.name + ': ' + s.value), """
    r"""location: {zipCode: ad.zipCode ?? null, storeId: ad.storeId ?? null}}; })())"""
)

COSTCO_CAPTURE_JS = (
    r"""JSON.stringify((() => { const lds=[...document.querySelectorAll('script[type="""
    r""""application/ld+json"]')].map(s=>{try{return JSON.parse(s.textContent)}"""
    r"""catch(e){return null}}).filter(x=>x&&x['@type']==='Product'); const """
    r"""p=lds[0]||{}; const o=p.offers||{}; const txt=(document.querySelector('main')"""
    r"""||document.body).innerText; const grab=(re)=>{const m=txt.match(re);return """
    r"""m?m[1].replace(/\s+/g,' ').trim():null}; const bt=document.body.textContent; """
    r"""const si=bt.indexOf('Specifications'); const spec= si>=0? bt.slice(si+14, """
    r"""bt.indexOf('Shipping & Returns', si)).slice(0,400):null; const """
    r"""pdi=txt.indexOf('Product Details\n'); const pd= pdi>=0? txt.slice(pdi+16, """
    r"""txt.indexOf('Specifications', pdi)).replace(/\s*\n\s*/g,' | ').slice(0,600)"""
    r""":null; return {page_url: location.href, captured_at_utc: new Date()"""
    r""".toISOString(), name: p.name, sku: p.sku, ld_price: o.price ?? null, """
    r"""ld_availability: o.availability ?? null, online_price: grab(/Online """
    r"""Price\s*\n?\s*(\$[\d.,]+)/), online_unit_price: grab(/(\$[\d.,]+\/per \w+)/),"""
    r""" warehouse_price: grab(/Warehouse Price\s*\n?\s*\$\s*\n?\s*([\d.,]+)/), """
    r"""my_warehouse: grab(/My Warehouse\s*\n\s*([^\n]+)/), delivery_zip: """
    r"""grab(/Delivery Location\s*\n\s*(\d{5})/), warehouse_stock: grab(/Washington """
    r"""DC\s*\n\s*(In Stock|Out of Stock|Limited Stock|Low Stock)/), description: """
    r"""p.description ?? null, product_details: pd, specifications: spec}; })())"""
)

# -------------------------------------------------------------------------------------
# Product tables. Each entry says which nut the product is, and how the page describes
# it.
# Words in `must` must appear in the retailer's product name (case-insensitive), so a
# changed
# listing fails loudly instead of silently pricing a different product.

NUTS_COM = [
    # handle, nut, processing, salt, organic, must, note
    (
        "english-walnuts-raw-no-shell",
        "walnut",
        "raw",
        "unsalted",
        False,
        ["walnut", "raw", "no shell"],
        "",
    ),
    (
        "english-walnut-halves-raw-no-shell",
        "walnut",
        "raw",
        "unsalted",
        False,
        ["walnut halves", "raw", "no shell"],
        "",
    ),
    (
        "raw-almonds-no-shell",
        "almond",
        "raw",
        "unsalted",
        False,
        ["raw almonds", "no shell"],
        "Product description says the almonds are pasteurized.",
    ),
    (
        "dry-roasted-almonds-unsalted",
        "almond",
        "dry_roasted",
        "unsalted",
        False,
        ["dry roasted almonds", "unsalted"],
        "",
    ),
    (
        "raw-pistachios-no-shell",
        "pistachio",
        "raw",
        "unsalted",
        False,
        ["raw pistachios", "no shell"],
        "",
    ),
    (
        "dry-roasted-pistachios-unsalted-no-shell",
        "pistachio",
        "dry_roasted",
        "unsalted",
        False,
        ["dry-roasted pistachios", "unsalted", "no shell"],
        "",
    ),
    (
        "georgia-pecans-raw-no-shell",
        "pecan",
        "raw",
        "unsalted",
        False,
        ["pecans", "raw", "no shell"],
        "",
    ),
    (
        "raw-macadamia-nuts",
        "macadamia",
        "raw",
        "unsalted",
        False,
        ["raw macadamia"],
        "",
    ),
    (
        "raw-hazelnuts-filberts-no-shell",
        "hazelnut",
        "raw",
        "unsalted",
        False,
        ["raw hazelnuts", "no shell"],
        "",
    ),
    ("raw-cashews", "cashew", "raw", "unsalted", False, ["raw cashews"], ""),
    (
        "dry-roasted-cashews-unsalted",
        "cashew",
        "dry_roasted",
        "unsalted",
        False,
        ["dry roasted cashews", "unsalted"],
        "",
    ),
    (
        "raw-spanish-peanuts",
        "peanut",
        "raw",
        "unsalted",
        False,
        ["raw spanish peanuts"],
        "",
    ),
    (
        "dry-roasted-peanuts-unsalted",
        "peanut",
        "dry_roasted",
        "unsalted",
        False,
        ["dry roasted peanuts", "unsalted"],
        "",
    ),
]
NUTS_COM_VARIANT = re.compile(r"^(\d+(?:\.\d+)?)\s*(oz|lb)s? (bag|case)$")

WALMART = [
    # usItemId, nut, shell, processing, salt, organic, net_oz, must, note
    (
        "5284690796",
        "almond",
        "shelled",
        "raw",
        "unsalted",
        False,
        25,
        ["natural whole almonds", "25 oz"],
        "Name and flavor say Natural; ingredients: almonds.",
    ),
    (
        "5295229969",
        "almond",
        "shelled",
        "raw",
        "unsalted",
        False,
        14,
        ["whole natural almonds", "14 oz"],
        "Name says Natural; ingredients: almonds.",
    ),
    (
        "834401337",
        "almond",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        16,
        ["whole almonds", "16 oz"],
        "Ingredients: almonds; no roasting stated.",
    ),
    (
        "939571964",
        "walnut",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        32,
        ["walnuts halves & pieces", "32 oz"],
        "Ingredients: walnuts; no roasting stated.",
    ),
    (
        "124188737",
        "walnut",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        16,
        ["walnuts halves & pieces", "16 oz"],
        "Ingredients: walnuts; no roasting stated.",
    ),
    (
        "327976708",
        "pecan",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        32,
        ["pecan halves", "32 oz"],
        "Ingredients: pecans; no roasting stated.",
    ),
    (
        "604801898",
        "pecan",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        16,
        ["pecan halves", "16 oz"],
        "Ingredients: pecans; no roasting stated.",
    ),
    (
        "18267370359",
        "pistachio",
        "shelled",
        "dry_roasted",
        "unsalted",
        False,
        12,
        ["no shells unsalted", "12 ounce"],
        (
            "Wonderful brand; ingredients: dry roasted pistachios. All Great Value "
            "shelled pistachios are salted."
        ),
    ),
    (
        "499527722",
        "macadamia",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        4,
        ["chopped macadamia", "4 oz"],
        (
            "Chopped pieces; ingredients: macadamia nuts. Only 4 oz packs of unsalted "
            "macadamia sold by Walmart.com."
        ),
    ),
    (
        "800469181",
        "macadamia",
        "shelled",
        "dry_roasted",
        "salted",
        False,
        6,
        ["dry roasted & salted macadamia", "6 oz"],
        "Salted (sea salt in ingredients).",
    ),
    (
        "748653717",
        "cashew",
        "shelled",
        "raw",
        "unsalted",
        True,
        14,
        ["organic raw whole cashews", "14 oz"],
        "USDA organic; ingredients: organic cashews.",
    ),
    (
        "45595300",
        "cashew",
        "shelled",
        "oil_roasted",
        "unsalted",
        False,
        16,
        ["whole cashews, unsalted", "16 oz"],
        "Ingredients list peanut, cottonseed, sunflower and canola oils (oil roasted).",
    ),
    (
        "364798995",
        "cashew",
        "shelled",
        "oil_roasted",
        "salted",
        False,
        30,
        ["deluxe cashews", "30 oz"],
        "Ingredients: cashews, vegetable oil, sea salt.",
    ),
    (
        "10448400",
        "peanut",
        "shelled",
        "dry_roasted",
        "unsalted",
        False,
        16,
        ["dry roasted and unsalted peanuts", "16 oz"],
        "Ingredients: peanuts.",
    ),
    (
        "333053298",
        "peanut",
        "shelled",
        "raw",
        "unsalted",
        False,
        16,
        ["raw peanuts", "16 oz"],
        "Ingredients: peanuts; shelled.",
    ),
]

COSTCO = [
    # item id (in URL), nut, shell, processing, salt, organic, package_g, units_in_pack,
    # must, note
    (
        "100119388",
        "walnut",
        "shelled",
        "not_stated",
        "not_stated",
        False,
        3 * LB_G,
        1,
        ["walnut halves", "3 lbs"],
        "Page lists no ingredients and states neither roasting nor salt.",
    ),
    (
        "100115268",
        "almond",
        "shelled",
        "raw",
        "not_stated",
        False,
        3 * LB_G,
        1,
        ["supreme whole almonds", "3 lbs"],
        "Page says steam pasteurized; no salt stated.",
    ),
    (
        "100115257",
        "pecan",
        "shelled",
        "not_stated",
        "not_stated",
        False,
        2 * LB_G,
        1,
        ["pecan halves", "2 lbs"],
        "Page states neither roasting nor salt.",
    ),
    (
        "4000043019",
        "cashew",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        40 * OZ_G,
        1,
        ["fancy whole cashews, unsalted", "2.5 lbs"],
        "Page does not say whether roasted; 40 oz pouch.",
    ),
    (
        "4000064056",
        "cashew",
        "shelled",
        "raw",
        "unsalted",
        True,
        40 * OZ_G,
        1,
        ["organic whole cashews, unsalted, unroasted", "2.5 lbs"],
        "USDA organic, unroasted.",
    ),
    (
        "100438733",
        "macadamia",
        "shelled",
        "dry_roasted",
        "salted",
        False,
        24 * OZ_G,
        1,
        ["dry roasted macadamia", "1.5 lbs"],
        "Dry roasted with sea salt (100 mg sodium per 28 g on label).",
    ),
    (
        "100350651",
        "pistachio",
        "shelled",
        "roasted",
        "salted",
        False,
        24 * OZ_G,
        1,
        ["shelled pistachios, salted", "1.5 lbs"],
        "Roasted and salted.",
    ),
    (
        "4000335971",
        "pistachio",
        "in_shell",
        "roasted",
        "unsalted",
        False,
        48 * OZ_G,
        1,
        ["in-shell pistachios, unsalted", "3 lbs"],
        "In shell: price per kg is per kg of nuts in shell, not kernels.",
    ),
    (
        "4000435237",
        "pistachio",
        "shelled",
        "raw",
        "unsalted",
        True,
        2 * 2.2 * LB_G,
        2,
        ["organic pistachio kernels", "2.2 lbs, 2-pack"],
        (
            "Page describes the kernels as raw, organic and unsalted. Online only; out "
            "of stock; two 2.2 lb bags."
        ),
    ),
    (
        "4000235904",
        "hazelnut",
        "shelled",
        "raw",
        "unsalted",
        False,
        3 * 2.2 * LB_G,
        3,
        ["raw shelled hazelnuts", "2.2 lbs, 3-pack"],
        (
            "Page describes them as untreated, with no added salt or oil. Online only; "
            "out of stock; three 2.2 lb bags."
        ),
    ),
    (
        "100115269",
        "peanut",
        "shelled",
        "roasted",
        "salted",
        False,
        40 * OZ_G,
        1,
        ["super extra-large peanuts", "2.5 lbs"],
        "Roasted and salted, Virginia variety, 40 oz can.",
    ),
]

TARGET = [
    # title (exact, from the listing), nut, shell, processing, salt, organic, net_oz,
    # note
    (
        "Good & Gather Shelled Walnuts - 16oz",
        "walnut",
        "shelled",
        "not_stated",
        "unsalted",
        False,
        16,
        (
            "Product page (read before the challenge appeared): ingredients walnuts, "
            "sodium 0 mg."
        ),
    ),
    (
        "Good & Gather Chopped Walnuts - 16oz",
        "walnut",
        "shelled",
        "not_stated",
        "not_stated",
        False,
        16,
        "Chopped.",
    ),
    (
        "Good & Gather Raw Whole Almonds - 32oz",
        "almond",
        "shelled",
        "raw",
        "unsalted",
        False,
        32,
        "Product URL not captured; url is the listing.",
    ),
    (
        "Good & Gather Raw Whole Almonds - 10.5oz",
        "almond",
        "shelled",
        "raw",
        "unsalted",
        False,
        10.5,
        "",
    ),
    (
        "Good & Gather Lightly Salted Dry Roasted Peanuts - 16oz",
        "peanut",
        "shelled",
        "dry_roasted",
        "salted",
        False,
        16,
        "Lightly salted.",
    ),
]

COLUMNS = [
    "row_id",
    "nut",
    "retailer",
    "seller_type",
    "brand",
    "product_name",
    "product_id",
    "url",
    "price_channel",
    "location",
    "retrieval_date",
    "retrieved_at_utc",
    "package_declared",
    "package_g",
    "units_in_pack",
    "pack_kind",
    "price_usd",
    "price_per_kg_usd",
    "shell",
    "processing",
    "salt",
    "organic",
    "in_stock",
    "meets_spec",
    "primary",
    "retailer_unit_price",
    "how_read",
    "source_file",
    "notes",
]


# -------------------------------------------------------------------------------------
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def eastern_date(ts: str) -> str:
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).astimezone(EASTERN).date().isoformat()


def check_name(name: str, must: list[str], where: str) -> None:
    low = name.lower()
    missing = [w for w in must if w.lower() not in low]
    if missing:
        raise SystemExit(
            f"{where}: product name {name!r} lacks {missing}; the listing changed"
        )


def money(s: str) -> float:
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", s)
    if not m:
        raise ValueError(f"no dollar amount in {s!r}")
    return float(m.group(1).replace(",", ""))


def per_kg(price: float, grams: float) -> float:
    return round(price / (grams / 1000.0), 2)


def unit_check(price: float, grams: float, text: str | None, where: str) -> None:
    """Compare the retailer's own unit price text with price/grams; fail on a >2%
    gap."""
    if not text:
        return
    t = text.replace(" ", "")
    m = re.match(
        r"^\$?([\d.]+)(¢)?/(oz|ounce|pound|lb)$",
        t.replace("per", "").replace("/per", "/"),
    )
    if not m:
        m = re.match(r"^\$?([\d.]+)(¢)?/(\w+)$", t)
    if not m:
        raise SystemExit(f"{where}: cannot parse unit price {text!r}")
    val = float(m.group(1)) / (100.0 if m.group(2) else 1.0)
    unit = m.group(3)
    unit_g = (
        OZ_G if unit in ("oz", "ounce") else LB_G if unit in ("pound", "lb") else None
    )
    if unit_g is None:
        raise SystemExit(f"{where}: unknown unit in {text!r}")
    implied = price / grams * unit_g
    if abs(implied - val) / val > 0.02:
        raise SystemExit(
            f"{where}: unit price {text!r} disagrees with {price} for {grams:.1f} g "
            f"(implies {implied:.4f} per {unit})"
        )


def get(url: str, **kw) -> requests.Response:
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    headers.update(kw.pop("headers", {}))
    return requests.get(url, headers=headers, timeout=60, **kw)


# -------------------------------------------------------------------------------------
# nuts.com
def nuts_com_rows(files: dict, offline: bool) -> list[dict]:
    rows = []
    for handle, nut, processing, salt, organic, must, note in NUTS_COM:
        rel = f"raw/nuts_com/{handle}.json"
        path = OUT / rel
        url = f"https://nuts.com/products/{handle}.js"
        if offline:
            data = path.read_bytes()
            if files.get(rel, {}).get("sha256") != sha256(data):
                raise SystemExit(f"sha256 mismatch for {rel}")
        else:
            r = get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.content
            json.loads(data)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            files[rel] = {
                "url": url,
                "sha256": sha256(data),
                "bytes": len(data),
                "fetched_at": now_utc(),
                "method": "HTTP GET (Shopify product JSON)",
            }
            time.sleep(0.5)
        fetched_at = files[rel]["fetched_at"]
        prod = json.loads(data)
        check_name(prod["title"], must, rel)
        for v in prod["variants"]:
            m = NUTS_COM_VARIANT.match(v["title"].strip().lower())
            if not m:
                # skips "mix 1oz", "tray section ...", "12 single serves": not
                # standalone packages
                continue
            upm = v.get("unit_price_measurement") or {}
            qty, qunit = float(upm["quantity_value"]), upm["quantity_unit"]
            grams = qty * (
                OZ_G if qunit == "oz" else LB_G if qunit == "lb" else float("nan")
            )
            declared = float(m.group(1)) * (OZ_G if m.group(2) == "oz" else LB_G)
            if abs(grams - declared) > 1.0:
                raise SystemExit(
                    f"{rel} {v['title']}: net quantity {qty} {qunit} disagrees with "
                    "title"
                )
            price = v["price"] / 100.0
            if (
                v.get("unit_price") is not None
                and upm.get("reference_unit") == "oz"
                and upm.get("reference_value") == 1
            ):
                unit_check(
                    price, grams, f"{v['unit_price']}¢/oz", f"{rel} {v['title']}"
                )
            kind = m.group(3)
            rows.append(
                {
                    "row_id": f"nuts_com:{handle}:{v['id']}",
                    "nut": nut,
                    "retailer": "nuts.com",
                    "brand": prod.get("vendor") or "Nuts.com",
                    "product_name": f"{prod['title']} - {v['title']}",
                    "product_id": f"{handle}?variant={v['id']}",
                    "url": f"https://nuts.com/products/{handle}?variant={v['id']}",
                    "price_channel": "online (ships)",
                    "location": "online, US",
                    "retrieved_at_utc": fetched_at,
                    "package_declared": v["title"],
                    "package_g": grams,
                    "units_in_pack": 1,
                    "price_usd": price,
                    "shell": "shelled",
                    "processing": processing,
                    "salt": salt,
                    "organic": organic,
                    "in_stock": bool(v["available"]),
                    "pack_kind": kind,
                    "retailer_unit_price": f"{v['unit_price']}¢/oz"
                    if v.get("unit_price") is not None
                    else "",
                    "how_read": (
                        "Shopify product JSON (price in cents, net quantity, "
                        "availability) fetched by scripts/fetch_prices.py"
                    ),
                    "source_file": rel,
                    "notes": " ".join(
                        x
                        for x in [
                            note,
                            ""
                            if v["available"]
                            else (
                                "Listed as unavailable (out of stock) on the retrieval "
                                "date."
                            ),
                        ]
                        if x
                    ),
                }
            )
    return rows


# -------------------------------------------------------------------------------------
# Walmart
def parse_walmart_html(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("no __NEXT_DATA__")
    nd = json.loads(m.group(1))
    d = nd["props"]["pageProps"]["initialData"]["data"]
    p = d["product"]
    idml = d.get("idml") or {}
    pi = p.get("priceInfo") or {}
    ads = [
        (mm.get("configs") or {}).get("ad")
        for mm in (d.get("contentLayout") or {}).get("modules") or []
    ]
    ad = next((a for a in ads if a and a.get("zipCode")), {}) or {}
    return {
        "usItemId": p.get("usItemId"),
        "name": p.get("name"),
        "brand": p.get("brand"),
        "seller": p.get("sellerName"),
        "availability": p.get("availabilityStatus"),
        "currentPrice": {
            "price": (pi.get("currentPrice") or {}).get("price"),
            "priceString": (pi.get("currentPrice") or {}).get("priceString"),
        },
        "unitPrice": (pi.get("unitPrice") or {}).get("priceString"),
        "ingredients": (((idml.get("ingredients") or {}).get("ingredients")) or {}).get(
            "value"
        ),
        "specs": [
            f"{s['name']}: {s['value']}"
            for s in (idml.get("specifications") or [])
            if re.search(
                (
                    r"weight|size|net content|flavor|nut type|food "
                    r"form|preparation|organic"
                ),
                s["name"],
                re.I,
            )
        ],
        "location": {"zipCode": ad.get("zipCode"), "storeId": ad.get("storeId")},
    }


def walmart_rows(
    files: dict, offline: bool, refetch: bool
) -> tuple[list[dict], list[dict]]:
    rec_rel = "raw/walmart/walmart_browser_capture_2026-09-23.json"
    rec_data = (OUT / rec_rel).read_bytes()
    record = {p["usItemId"]: p for p in json.loads(rec_data)["products"]}
    rows, cross = [], []
    for item, nut, shell, processing, salt, organic, net_oz, must, note in WALMART:
        rel = f"raw/walmart/ip_{item}.html.gz"
        path = OUT / rel
        url = f"https://www.walmart.com/ip/{item}"
        got = None
        if refetch and not offline:
            try:
                r = get(url, headers={"Accept": "text/html"})
                html = r.text
                if (
                    r.status_code == 200
                    and "Robot or human" not in html
                    and "__NEXT_DATA__" in html
                ):
                    gz = gzip.compress(r.content, mtime=0)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(gz)
                    files[rel] = {
                        "url": url,
                        "sha256": sha256(gz),
                        "bytes": len(gz),
                        "fetched_at": now_utc(),
                        "html_sha256": sha256(r.content),
                        "html_bytes": len(r.content),
                        "method": (
                            "HTTP GET, page HTML stored gzipped; fields from "
                            "__NEXT_DATA__"
                        ),
                    }
                else:
                    print(
                        f"walmart {item}: refused (HTTP {r.status_code}); not retried",
                        file=sys.stderr,
                    )
            except requests.RequestException as e:
                print(f"walmart {item}: {e}", file=sys.stderr)
            time.sleep(3)
        if path.exists() and rel in files:
            gz = path.read_bytes()
            if files[rel]["sha256"] != sha256(gz):
                raise SystemExit(f"sha256 mismatch for {rel}")
            got = parse_walmart_html(gzip.decompress(gz).decode("utf-8"))
            retrieved = files[rel]["fetched_at"]
            how = (
                "Page __NEXT_DATA__ JSON from a scripted fetch (raw HTML stored "
                "gzipped)"
            )
            src = rel
        if got is None:
            got = record[item]
            retrieved = got["captured_at_utc"]
            how = (
                "Browser capture with WALMART_CAPTURE_JS (scripted fetch refused or "
                "not run)"
            )
            src = rec_rel
        check_name(got["name"], must, f"walmart {item}")
        if got["seller"] != "Walmart.com":
            raise SystemExit(
                f"walmart {item}: seller {got['seller']!r} is not Walmart.com"
            )
        price = float(got["currentPrice"]["price"])
        grams = net_oz * OZ_G
        unit_check(price, grams, got.get("unitPrice"), f"walmart {item}")
        loc = got.get("location") or {}
        if item in record and src != rec_rel:
            b = record[item]
            cross.append(
                {
                    "usItemId": item,
                    "fetch_price": price,
                    "browser_price": b["currentPrice"]["price"],
                    "browser_captured_at_utc": b["captured_at_utc"],
                    "fetched_at": retrieved,
                    "match": abs(price - float(b["currentPrice"]["price"])) < 0.005,
                }
            )
        rows.append(
            {
                "row_id": f"walmart:{item}",
                "nut": nut,
                "retailer": "Walmart",
                "brand": got.get("brand") or "",
                "product_name": got["name"],
                "product_id": item,
                "url": url,
                "price_channel": "walmart.com (online; ship or pickup)",
                "location": (
                    f"ZIP {loc.get('zipCode')}, store {loc.get('storeId')} (picked by "
                    "walmart.com from visitor IP)"
                ),
                "retrieved_at_utc": retrieved,
                "package_declared": f"{net_oz:g} oz",
                "package_g": grams,
                "units_in_pack": 1,
                "price_usd": price,
                "shell": shell,
                "processing": processing,
                "salt": salt,
                "organic": organic,
                "in_stock": got["availability"] == "IN_STOCK",
                "pack_kind": "bag",
                "retailer_unit_price": got.get("unitPrice") or "",
                "how_read": how,
                "source_file": src,
                "notes": note,
            }
        )
    return rows, cross


# -------------------------------------------------------------------------------------
# Costco
def costco_rows(files: dict) -> list[dict]:
    rel = "raw/costco/costco_browser_capture_2026-09-23.json"
    doc = json.loads((OUT / rel).read_bytes())
    by_id = {}
    for p in doc["products"]:
        m = re.search(r"/(\d+)(?:\?|$)", p["page_url"])
        by_id[m.group(1)] = p
    rows = []
    for item, nut, shell, processing, salt, organic, grams, units, must, note in COSTCO:
        p = by_id[item]
        check_name(p["name"], must, f"costco {item}")
        url = p["page_url"].split("?")[0]
        online = float(p["ld_price"])
        if p.get("online_price") and abs(money(p["online_price"]) - online) > 0.005:
            raise SystemExit(
                f"costco {item}: JSON-LD price {online} != shown online price "
                f"{p['online_price']}"
            )
        unit_check(
            online,
            grams,
            (p.get("online_unit_price") or "").replace("/per ", "/"),
            f"costco {item}",
        )
        base = {
            "nut": nut,
            "retailer": "Costco",
            "brand": p["name"].split(" ")[0]
            if not p["name"].startswith("Kirkland")
            else "Kirkland Signature",
            "product_name": p["name"],
            "product_id": f"{item} (item {p['sku']})",
            "url": url,
            "retrieved_at_utc": p["captured_at_utc"],
            "package_declared": (
                re.search(r"\d+(?:\.\d+)?\s*lbs?(?:, \d+-pack)?", p["name"]) or [""]
            )[0],
            "package_g": grams,
            "units_in_pack": units,
            "shell": shell,
            "processing": processing,
            "salt": salt,
            "organic": organic,
            "pack_kind": "multipack" if units > 1 else "bag",
            "how_read": (
                "Browser capture with COSTCO_CAPTURE_JS (warehouse price is rendered "
                "client-side)"
            ),
            "source_file": rel,
        }
        if p.get("warehouse_price"):
            rows.append(
                {
                    **base,
                    "row_id": f"costco:{item}:warehouse",
                    "price_channel": "in-warehouse",
                    "location": f"{p['my_warehouse']} warehouse",
                    "price_usd": float(p["warehouse_price"]),
                    "in_stock": p.get("warehouse_stock") == "In Stock",
                    "retailer_unit_price": "",
                    "notes": " ".join(
                        x
                        for x in [
                            note,
                            f"Stock at warehouse: {p.get('warehouse_stock')}.",
                        ]
                        if x
                    ),
                }
            )
        rows.append(
            {
                **base,
                "row_id": f"costco:{item}:online",
                "price_channel": "costco.com 2-Day Delivery",
                "location": f"delivery ZIP {p['delivery_zip']}",
                "price_usd": online,
                "in_stock": str(p.get("ld_availability", "")).endswith("InStock"),
                "retailer_unit_price": p.get("online_unit_price") or "",
                "notes": " ".join(
                    x
                    for x in [
                        note,
                        (
                            "Online price; a $3.00 delivery fee applies to 2-Day "
                            "orders under $75 (not included)."
                        ),
                    ]
                    if x
                ),
            }
        )
    return rows


# -------------------------------------------------------------------------------------
# Target
def target_rows(files: dict) -> list[dict]:
    rel = "raw/target/target_search_listing_2026-09-23.json"
    doc = json.loads((OUT / rel).read_bytes())
    items = {i["title"]: i for i in doc["items"]}
    ts = "2026-09-24T02:58:00Z"  # approximate; see read_at_utc in the record
    rows = []
    for title, nut, shell, processing, salt, organic, net_oz, note in TARGET:
        it = items[title]
        price = money(it["price_text"])
        grams = net_oz * OZ_G
        unit_check(price, grams, it.get("unit_price_text"), f"target {title}")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        rows.append(
            {
                "row_id": f"target:{it['tcin'] or slug}",
                "nut": nut,
                "retailer": "Target",
                "brand": "Good & Gather",
                "product_name": title,
                "product_id": it["tcin"] or "",
                "url": it["url"] or doc["listing_url"],
                "price_channel": "target.com listing"
                + (" (online price)" if "online" in it["price_text"] else ""),
                "location": (
                    f"store {doc['store']['store_id']} {doc['store']['name']}, "
                    "Washington DC"
                ),
                "retrieved_at_utc": ts,
                "package_declared": f"{net_oz:g} oz",
                "package_g": grams,
                "units_in_pack": 1,
                "price_usd": price,
                "shell": shell,
                "processing": processing,
                "salt": salt,
                "organic": organic,
                "in_stock": bool(it.get("stock_text")),
                "pack_kind": "bag",
                "retailer_unit_price": it.get("unit_price_text") or "",
                "how_read": (
                    "Search-results listing text read in a browser; product pages "
                    "blocked by a human-verification challenge (not attempted)"
                ),
                "source_file": rel,
                "notes": note,
            }
        )
    return rows


# -------------------------------------------------------------------------------------
def finalize(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["seller_type"] = RETAILERS[r["retailer"]]
        r["retrieval_date"] = eastern_date(r["retrieved_at_utc"])
        r["price_per_kg_usd"] = per_kg(r["price_usd"], r["package_g"])
        r["meets_spec"] = (
            r["shell"] == "shelled"
            and r["salt"] in OK_SALT
            and r["processing"] in OK_PROCESSING
        )
        r["primary"] = False
    # Primary row per (nut, retailer): among in-stock rows that meet the spec, in a
    # single
    # package of at most MAX_PRIMARY_G (no cases, no multipacks), prefer non-organic if
    # any,
    # then the lowest price per kg; ties go to a stated "unsalted", then a stated
    # processing.
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        if (
            r["meets_spec"]
            and r["in_stock"]
            and r["package_g"] <= MAX_PRIMARY_G
            and r["pack_kind"] == "bag"
        ):
            groups.setdefault((r["nut"], r["retailer"]), []).append(r)
    for cands in groups.values():
        conv = [r for r in cands if not r["organic"]] or cands
        best = min(
            conv,
            key=lambda r: (
                r["price_per_kg_usd"],
                r["salt"] != "unsalted",
                r["processing"] == "not_stated",
                -r["package_g"],
                r["row_id"],
            ),
        )
        best["primary"] = True
    order = {n: i for i, n in enumerate(NUTS)}
    rorder = {k: i for i, k in enumerate(RETAILERS)}
    rows.sort(
        key=lambda r: (
            order[r["nut"]],
            rorder[r["retailer"]],
            not r["primary"],
            r["price_per_kg_usd"],
            r["row_id"],
        )
    )
    return rows


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.2f}" if abs(v) < 1e6 else repr(v)
    return v


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=cols, lineterminator="\n", extrasaction="ignore"
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k)) for k in cols})


def summary(rows: list[dict]) -> list[dict]:
    out = []
    for nut in NUTS:
        prim = [r for r in rows if r["nut"] == nut and r["primary"]]
        vals = [r["price_per_kg_usd"] for r in prim]
        row = {
            "nut": nut,
            "n_retailers": len(prim),
            "retailers": ";".join(r["retailer"] for r in prim),
            "min_usd_per_kg": min(vals) if vals else None,
            "median_usd_per_kg": round(statistics.median(vals), 2) if vals else None,
            "max_usd_per_kg": max(vals) if vals else None,
        }
        for ret in RETAILERS:
            hit = [r for r in prim if r["retailer"] == ret]
            key = ret.lower().replace(".", "_")
            row[f"{key}_usd_per_kg"] = hit[0]["price_per_kg_usd"] if hit else None
            row[f"{key}_row_id"] = hit[0]["row_id"] if hit else ""
        out.append(row)
    return out


def old_repo_comparison() -> list[dict]:
    """Compare with the April 2026 nuts.com prices in the old repo (fallback reference
    only)."""
    import subprocess

    try:
        txt = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "show",
                "origin/master:src/whatnut/data/raw/retail_prices/retail_prices.csv",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return []
    return [
        {
            "nut": r["nut"],
            "product_name": r["product_name"],
            "retrieval_date": r["retrieval_date"],
            "package_size_g": r["package_size_g"],
            "package_price_usd": r["package_price_usd"],
            "price_per_kg_usd": r["price_per_kg_usd"],
        }
        for r in csv.DictReader(txt.splitlines())
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--offline", action="store_true", help="rebuild from raw files; verify sha256"
    )
    ap.add_argument(
        "--no-walmart", action="store_true", help="do not refetch Walmart pages"
    )
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    files = manifest.get("files", {})
    for rel in [
        "raw/walmart/walmart_browser_capture_2026-09-23.json",
        "raw/costco/costco_browser_capture_2026-09-23.json",
        "raw/target/target_search_listing_2026-09-23.json",
    ]:
        data = (OUT / rel).read_bytes()
        prev = files.get(rel, {})
        if args.offline and prev.get("sha256") != sha256(data):
            raise SystemExit(f"sha256 mismatch for {rel}")
        files[rel] = {
            "url": {
                "walmart": (
                    "https://www.walmart.com/ip/<usItemId> (see page_url per product)"
                ),
                "costco": (
                    "https://www.costco.com/p/-/<slug>/<item> (see page_url per "
                    "product)"
                ),
                "target": "https://www.target.com/s?searchTerm=good+and+gather+walnuts",
            }[rel.split("/")[1]],
            "sha256": sha256(data),
            "bytes": len(data),
            "fetched_at": {
                "walmart": "2026-09-24T02:50:32Z/2026-09-24T02:52:42Z",
                "costco": "2026-09-24T02:53:51Z/2026-09-24T02:56:41Z",
                "target": "2026-09-24T02:58Z (approximate)",
            }[rel.split("/")[1]],
            "method": (
                "documented manual record: fields read in a browser session and "
                "transcribed (see 'what' in the file)"
            ),
        }

    rows = nuts_com_rows(files, args.offline)
    wrows, cross = walmart_rows(files, args.offline, refetch=not args.no_walmart)
    rows += wrows + costco_rows(files) + target_rows(files)
    rows = finalize(rows)

    write_csv(OUT / "prices.csv", COLUMNS, rows)
    summ = summary(rows)
    scols = [
        "nut",
        "n_retailers",
        "retailers",
        "min_usd_per_kg",
        "median_usd_per_kg",
        "max_usd_per_kg",
    ]
    for ret in RETAILERS:
        key = ret.lower().replace(".", "_")
        scols += [f"{key}_usd_per_kg", f"{key}_row_id"]
    write_csv(OUT / "prices_by_nut.csv", scols, summ)

    legacy = "raw/walmart/walmart_search_raw_almonds_curl.html.gz"
    unused = {}
    if (OUT / legacy).exists():
        d = (OUT / legacy).read_bytes()
        unused[legacy] = {
            "sha256": sha256(d),
            "bytes": len(d),
            "note": (
                "Left by an earlier cut-off run of this builder (Walmart search page "
                "for almonds, "
                "fetched by curl on 2026-09-23). Not used for any price."
            ),
        }
    derived = {}
    for name in ["prices.csv", "prices_by_nut.csv"]:
        d = (OUT / name).read_bytes()
        derived[name] = {
            "sha256": sha256(d),
            "bytes": len(d),
            "generated_by": "scripts/fetch_prices.py",
        }

    manifest = {
        "generated_by": "scripts/fetch_prices.py",
        "retrieval_date_note": (
            "retrieval_date is the US Eastern calendar date of retrieved_at_utc."
        ),
        "sources": {
            "nuts.com": (
                "Specialty online seller. Shopify product JSON per product (price, net "
                "quantity, availability)."
            ),
            "Walmart": (
                "Big-box. walmart.com product pages, first-party seller Walmart.com "
                "only; location ZIP 20001, store 3035. "
                "Stored page (raw/walmart/ip_*.html.gz) where Walmart served one to a "
                "script, else the browser record."
            ),
            "Costco": (
                "Warehouse club. costco.com product pages read in a browser; "
                "in-warehouse price at the Washington DC warehouse and the 2-Day "
                "Delivery online price."
            ),
            "Target": (
                "Big-box. One search-results listing (store 2259 Columbia Heights, DC);"
                " product pages blocked by a human-verification challenge."
            ),
        },
        "spec": (
            "Target product: shelled, unsalted, raw or dry-roasted. meets_spec is true "
            "when shell=shelled, "
            "salt in {unsalted, not_stated} and processing in {raw, dry_roasted, "
            "not_stated}."
        ),
        "primary_rule": (
            "One primary row per (nut, retailer): among rows with meets_spec, in_stock,"
            " a single package "
            f"(no case or multipack) of at most {MAX_PRIMARY_G:.0f} g, prefer "
            "non-organic when any "
            "qualifies, then the lowest price_per_kg_usd; ties go to a stated unsalted,"
            " then a stated processing, then the larger package."
        ),
        "columns": {
            "row_id": "unique id: retailer:product[:variant or channel]",
            "nut": "one of " + ", ".join(NUTS),
            "retailer": "nuts.com | Walmart | Costco | Target",
            "seller_type": "specialty_online | big_box | warehouse_club",
            "brand": "brand shown by the retailer",
            "product_name": "retailer's product name (nuts.com: product - variant)",
            "product_id": (
                "retailer's id (nuts.com handle and variant id; Walmart usItemId; "
                "Costco item id and item number; Target TCIN)"
            ),
            "url": "product page (Target 32 oz almonds: the listing URL)",
            "price_channel": "how the price applies (online, in-warehouse, listing)",
            "location": "store, warehouse or ZIP the price applies to",
            "retrieval_date": "US Eastern date the price was read",
            "retrieved_at_utc": "when the price was read (Target: approximate)",
            "package_declared": "net quantity as the retailer states it",
            "package_g": (
                "net grams: declared ounces x 28.349523125 or pounds x 453.59237 "
                "(shell included for in_shell)"
            ),
            "units_in_pack": (
                "bags in the listing (multipacks > 1; package_g is the total)"
            ),
            "pack_kind": "bag | case (nuts.com bulk cases) | multipack",
            "price_usd": (
                "shelf price for the package, before tax, delivery fees, membership "
                "fees and promotions"
            ),
            "price_per_kg_usd": "price_usd / package_g x 1000",
            "shell": "shelled | in_shell",
            "processing": (
                "raw (page says raw, unroasted, natural or steam pasteurized) | "
                "dry_roasted | oil_roasted "
                "(oil in ingredients) | roasted (method not stated) | not_stated "
                "(neither raw nor roasted stated; "
                "ingredients, where shown, are only the nut)"
            ),
            "salt": (
                "unsalted (stated, or ingredients are only the nut) | salted (incl. "
                "lightly salted) | not_stated"
            ),
            "organic": "true when sold as USDA organic",
            "in_stock": (
                "retailer showed the package available on the retrieval date (Costco "
                "warehouse rows: at the Washington DC warehouse)"
            ),
            "meets_spec": "see spec",
            "primary": "see primary_rule",
            "retailer_unit_price": (
                "the retailer's own unit price text; the script checks it against "
                "price_usd/package_g (2% tolerance)"
            ),
            "how_read": "method",
            "source_file": "raw file under data/prices/ that holds the price",
            "notes": "labels, stock and caveats",
        },
        "files": dict(sorted(files.items())),
        "derived": derived,
        "unused_files": unused,
        "cross_checks": {
            "walmart_fetch_vs_browser_capture": cross,
            "old_repo_nuts_com_april_2026": {
                "source": (
                    "origin/master:src/whatnut/data/raw/retail_prices/"
                    "retail_prices.csv (fallback reference only; not used)"
                ),
                "rows": old_repo_comparison(),
            },
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    n_primary = sum(r["primary"] for r in rows)
    print(
        f"prices.csv: {len(rows)} rows, {n_primary} primary; prices_by_nut.csv: "
        f"{len(summ)} nuts"
    )
    for s in summ:
        print(
            f"  {s['nut']:9s} {s['n_retailers']} retailers  min {s['min_usd_per_kg']}  "
            f"median {s['median_usd_per_kg']}  "
            f"max {s['max_usd_per_kg']}  ({s['retailers']})"
        )
    bad = [c for c in cross if not c["match"]]
    if bad:
        print(
            f"WARNING: Walmart fetch and browser capture disagree for {bad}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
