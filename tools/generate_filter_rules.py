import json
import os
import pathlib
import requests
from collections import Counter
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")


def fetch_all_records():
    records = []
    offset = None
    while True:
        params = {"maxRecords": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(
            f"https://api.airtable.com/v0/{BASE_ID}/Crawl_Training_Set",
            headers={"Authorization": f"Bearer {API_KEY}"},
            params=params,
            timeout=15,
        )
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def extract_keywords(texts: list[str], top_n: int = 30) -> list[str]:
    words = []
    for text in texts:
        for w in text.lower().split():
            w = w.strip('.,!?[](){}"\'#@')
            if len(w) >= 3:
                words.append(w)
    return [w for w, _ in Counter(words).most_common(top_n)]


def main():
    records = fetch_all_records()
    good, bad = [], []
    block_reasons, pass_reasons = [], []

    for rec in records:
        f = rec.get("fields", {})
        label = f.get("label", "")
        text = f.get("post_text", "")
        if label == "GOOD":
            good.append(text)
            for r in (f.get("pass_reason") or []):
                pass_reasons.append(r)
        elif label == "BAD":
            bad.append(text)
            for r in (f.get("block_reason") or []):
                block_reasons.append(r)

    rules = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "training_count": {"GOOD": len(good), "BAD": len(bad), "TOTAL": len(records)},
        "block_reasons": dict(Counter(block_reasons).most_common()),
        "pass_reasons": dict(Counter(pass_reasons).most_common()),
        "block_keywords": extract_keywords(bad),
        "pass_keywords": extract_keywords(good),
    }

    out = pathlib.Path(r"configs/filter_rules.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료 | {out} | GOOD={len(good)} BAD={len(bad)}")


if __name__ == "__main__":
    main()
