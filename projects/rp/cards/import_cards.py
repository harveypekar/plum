#!/usr/bin/env python3
"""Import character cards from characters.json into the RP database via API."""
import json
import sys
import urllib.request

API = "http://localhost:8080"

def main():
    with open("characters.json") as f:
        chars = json.load(f)

    print(f"Importing {len(chars)} characters...")
    for c in chars:
        name = c["name"]
        data = json.dumps(c).encode()
        req = urllib.request.Request(
            f"{API}/rp/cards",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req)
            result = json.loads(resp.read())
            print(f"  OK: {name} (id={result['id']})")
        except Exception as e:
            print(f"  FAIL: {name}: {e}", file=sys.stderr)

    print("Done.")

if __name__ == "__main__":
    main()
