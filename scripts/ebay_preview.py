"""Preview eBay listings in memory; run with `python -m scripts.ebay_preview`."""

from __future__ import annotations

import argparse
import getpass
import os

from backend.app.data.ebay_client import EbayAPIError, EbayBrowseClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only eBay Browse search preview")
    parser.add_argument("--query", default="brown leather jacket")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--environment", choices=("sandbox", "production"), default="production"
    )
    parser.add_argument(
        "--include-new",
        action="store_true",
        help="Also allow new listings (default: used only)",
    )
    args = parser.parse_args()
    client_id = os.environ.get("EBAY_CLIENT_ID") or input("eBay App ID: ").strip()
    client_secret = os.environ.get("EBAY_CLIENT_SECRET") or getpass.getpass(
        "eBay Cert ID (hidden): "
    )
    try:
        client = EbayBrowseClient(client_id, client_secret, environment=args.environment)
        listings = client.search(args.query, limit=args.limit, used_only=not args.include_new)
    except (EbayAPIError, ValueError) as exc:
        print(f"eBay search failed: {exc}")
        return 1

    print(f"Search succeeded: {len(listings)} results")
    print(f"Query: {args.query} | Used only: {not args.include_new}")
    for index, listing in enumerate(listings, 1):
        print(f"\nResult {index}")
        print("Title:", listing["title"])
        print("Price:", listing["price"], listing["currency"])
        print("Condition:", listing["condition"])
        print("Has image:", bool(listing["image_url"]))
        print("Has eBay link:", bool(listing["listing_url"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
