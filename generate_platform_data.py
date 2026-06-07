"""Scal dane Maps + GUS + wspólnoty → data.json dla platformy."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dane-gus"))
sys.path.insert(0, str(ROOT))
GITHUB_PAGES = Path(__file__).resolve().parent
DATA_WROCLAW = ROOT / "dane" / "wroclaw"
DATA_GUS = ROOT / "dane" / "gus"
DANE_GUS_CSV = ROOT / "dane-gus"

import gus_io  # noqa: E402
from maps_api_gaps import build_gap_entry, missing_fields, write_gaps_report  # noqa: E402

NAME_MATCH_THRESHOLD = 0.85


def clean_maps_place(p: dict) -> dict:
    reviews = []
    for r in p.get("reviews", []):
        ts = r.get("time", 0) or r.get("timestamp", 0)
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d.%m.%Y") if ts else r.get("date", "")
        reviews.append({
            "author": r.get("author_name", r.get("author", "")),
            "rating": r.get("rating", ""),
            "timestamp": ts,
            "date": date_str,
            "text": (r.get("text", "") or "")[:600],
        })

    oh = p.get("opening_hours", {})
    hours = oh.get("weekday_text", []) if oh else p.get("hours", [])
    loc = p.get("geometry", {}).get("location", {})
    if not loc.get("lat") and p.get("lat"):
        loc = {"lat": p["lat"], "lng": p["lng"]}
    latest_ts = max((r["timestamp"] for r in reviews if r.get("timestamp")), default=p.get("latest_review_ts", 0))

    return {
        "place_id": p.get("place_id", ""),
        "name": p.get("name", ""),
        "address": p.get("address", p.get("formatted_address", "")),
        "phone": p.get("phone", "") or p.get("formatted_phone_number", "") or p.get("international_phone_number", ""),
        "website": p.get("website", ""),
        "rating": p.get("rating", 0) or 0,
        "reviews_count": p.get("reviews_count", p.get("user_ratings_total", 0)) or 0,
        "maps_url": p.get("maps_url", p.get("url", "")),
        "status": p.get("business_status", p.get("status", "")),
        "hours": hours,
        "lat": loc.get("lat"),
        "lng": loc.get("lng"),
        "reviews": reviews,
        "latest_review_ts": latest_ts,
    }


def gus_block(company: dict, wspolnoty_count: int = 0) -> dict:
    return {
        "phones": company.get("phones", []),
        "emails": company.get("emails", []),
        "website": company.get("website", ""),
        "confidence": company.get("confidence", "niska"),
        "wspolnoty_count": wspolnoty_count,
    }


def merge_gus_into_record(record: dict, company: dict, wspolnoty_count: int) -> dict:
    record = dict(record)
    record["id"] = company.get("id") or record.get("id") or gus_io.slugify(record.get("name", ""))
    if company.get("name") and not str(company.get("key", "")).startswith("phone:"):
        record["name"] = company["name"]
    record["gus"] = gus_block(company, wspolnoty_count)
    sources = set(record.get("sources", ["maps"]))
    sources.add("gus")
    record["sources"] = sorted(sources)
    if not record.get("id"):
        record["id"] = company.get("id") or gus_io.slugify(record.get("name", ""))
    return record


def new_gus_only_record(company: dict, maps: dict | None, wspolnoty_count: int) -> dict:
    m = maps or {}
    rec = {
        "id": company["id"],
        "place_id": m.get("place_id", ""),
        "name": m.get("name") or company["name"],
        "address": m.get("address", ""),
        "phone": m.get("phone") or (company["phones"][0] if company.get("phones") else ""),
        "website": m.get("website") or company.get("website", ""),
        "rating": m.get("rating", 0) or 0,
        "reviews_count": m.get("reviews_count", 0) or 0,
        "maps_url": m.get("maps_url", ""),
        "status": m.get("status", ""),
        "hours": m.get("hours", []),
        "lat": m.get("lat"),
        "lng": m.get("lng"),
        "reviews": m.get("reviews", []),
        "latest_review_ts": m.get("latest_review_ts", 0),
        "gus": gus_block(company, wspolnoty_count),
        "sources": ["gus"] if not m.get("place_id") else ["gus", "maps"],
    }
    if m.get("place_id"):
        rec["sources"] = sorted(set(rec["sources"]))
    return rec


class ManagerIndex:
    def __init__(self, records: list[dict]):
        self.records = records
        self.by_place_id: dict[str, int] = {}
        self.by_phone: dict[str, int] = {}
        self.by_domain: dict[str, int] = {}
        self.by_name: dict[str, int] = {}
        for i, r in enumerate(records):
            pid = r.get("place_id")
            if pid:
                self.by_place_id[pid] = i
            for ph in self._phones(r):
                self.by_phone[ph] = i
            dom = gus_io.norm_domain(r.get("website"))
            if dom:
                self.by_domain[dom] = i
            nn = gus_io.norm_company_name(r.get("name", ""))
            if nn:
                self.by_name[nn] = i

    @staticmethod
    def _phones(r: dict) -> set[str]:
        phones = {gus_io.norm_phone(r.get("phone"))}
        for p in r.get("gus", {}).get("phones", []):
            phones.add(gus_io.norm_phone(p))
        return {p for p in phones if p}

    def find_match(self, company: dict, gus_maps: dict | None) -> int | None:
        m = gus_maps or {}
        pid = m.get("place_id")
        if pid and pid in self.by_place_id:
            return self.by_place_id[pid]

        for ph in company.get("phones", []):
            if ph in self.by_phone:
                return self.by_phone[ph]

        dom = gus_io.norm_domain(company.get("website"))
        if dom and dom in self.by_domain:
            return self.by_domain[dom]

        cn = gus_io.norm_company_name(company.get("name", ""))
        if cn and cn in self.by_name:
            return self.by_name[cn]

        for i, r in enumerate(self.records):
            sim = gus_io.name_similarity(company["name"], r.get("name", ""))
            if sim >= NAME_MATCH_THRESHOLD:
                return i
        return None


def load_wspolnoty_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: len(v) for k, v in data.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="Użyj plików sample")
    parser.add_argument("--full", action="store_true", help="Pełny run GUS CSV")
    parser.add_argument(
        "--gus-maps",
        default="",
        help="Ścieżka do zarzadcy_gus_maps.json",
    )
    parser.add_argument(
        "--zarzadcy-csv",
        default="",
    )
    args = parser.parse_args()

    if args.sample or (not args.full and not args.gus_maps):
        zarzadcy_csv = args.zarzadcy_csv or str(DANE_GUS_CSV / "zarzadcy-gus-wroclaw-sample.csv")
        gus_maps_path = args.gus_maps or str(DATA_GUS / "zarzadcy_gus_maps.json")
    else:
        zarzadcy_csv = args.zarzadcy_csv or str(DANE_GUS_CSV / "zarzadcy-gus-wroclaw.csv")
        gus_maps_path = args.gus_maps or str(DATA_GUS / "zarzadcy_gus_maps.json")

    maps_full_path = DATA_WROCLAW / "zarzadcy_wroclaw_full_details.json"
    wspolnoty_path = GITHUB_PAGES / "wspolnoty-by-manager.json"
    output_path = GITHUB_PAGES / "data.json"

    # UTF-8 wspólnoty
    wspolnoty_csv = DANE_GUS_CSV / "wspolnoty-gus.csv"
    if wspolnoty_csv.exists():
        src_enc = gus_io.convert_csv_to_utf8(wspolnoty_csv)
        print(f"wspolnoty-gus.csv: kodowanie źródłowe {src_enc}, zapis UTF-8")

    # link wspólnot (regeneruj index)
    import subprocess
    overrides_path = DATA_GUS / "wspolnoty_phone_manager.csv"
    link_cmd = [
        sys.executable,
        str(ROOT / "link_wspolnoty.py"),
        "--zarzadcy", zarzadcy_csv,
        "--wspolnoty", str(wspolnoty_csv),
        "--output", str(wspolnoty_path),
    ]
    if overrides_path.exists():
        link_cmd.extend(["--overrides", str(overrides_path)])
    subprocess.run(link_cmd, check=True)

    wsp_counts = load_wspolnoty_counts(wspolnoty_path)

    # Istniejące Maps
    with open(maps_full_path, encoding="utf-8") as f:
        maps_full = json.load(f)
    existing = [clean_maps_place(p) for p in maps_full.get("results", [])]
    for r in existing:
        r["id"] = gus_io.slugify(r["name"])
        r["sources"] = ["maps"]

    # GUS companies + API results
    z_rows, _ = gus_io.read_csv(zarzadcy_csv)
    companies = gus_io.aggregate_zarzadcy_rows(z_rows)

    gus_results: list[dict] = []
    if Path(gus_maps_path).exists():
        with open(gus_maps_path, encoding="utf-8") as f:
            gus_payload = json.load(f)
        gus_results = gus_payload.get("results", [])
    else:
        print(f"Brak {gus_maps_path} — tylko merge GUS metadata bez nowych danych Maps")

    company_by_key = {c["key"]: c for c in companies}
    gus_lookup = {}
    for gr in gus_results:
        comp = gr.get("company", {})
        gus_lookup[comp.get("key", comp.get("id", ""))] = gr

    index = ManagerIndex(existing)
    merged_gus_keys: set[str] = set()
    gap_entries: list[dict] = []

    for company in companies:
        gr = gus_lookup.get(company["key"], {})
        maps_data = gr.get("maps")
        match_status = gr.get("match_status", "no_match")
        match_score = gr.get("match_score", 0)
        wsp_count = wsp_counts.get(company["id"], 0)

        idx = index.find_match(company, maps_data)
        if idx is not None:
            existing[idx] = merge_gus_into_record(existing[idx], company, wsp_count)
            merged_gus_keys.add(company["key"])
            gap_entries.append(build_gap_entry(
                company, "merged_existing", match_score, existing[idx],
                merge_note=f"Scalono z istniejącym rekordem Maps",
            ))
            continue

        if maps_data and match_status in ("ok", "partial_data", "low_confidence", "manual"):
            rec = new_gus_only_record(company, maps_data, wsp_count)
            existing.append(rec)
            index = ManagerIndex(existing)
            merged_gus_keys.add(company["key"])
            if match_status == "manual":
                status = "full_match"
            else:
                status = "partial_data" if missing_fields(rec) else (
                    "low_confidence" if match_status == "low_confidence" else "full_match"
                )
            gap_entries.append(build_gap_entry(
                company, status, match_score, rec,
                merge_note="Reczne dopasowanie (share.google)" if match_status == "manual" else "",
            ))
        elif match_status == "api_error":
            rec = new_gus_only_record(company, None, wsp_count)
            existing.append(rec)
            index = ManagerIndex(existing)
            merged_gus_keys.add(company["key"])
            gap_entries.append(build_gap_entry(
                company, "api_error", match_score, rec, merge_note=gr.get("error", ""),
            ))
        else:
            rec = new_gus_only_record(company, None, wsp_count)
            existing.append(rec)
            index = ManagerIndex(existing)
            merged_gus_keys.add(company["key"])
            gap_entries.append(build_gap_entry(company, "no_match", match_score, rec))

    # Dedup by place_id and by id (keep enriched record)
    seen_pid: set[str] = set()
    seen_id: set[str] = set()
    deduped = []
    for r in existing:
        pid = r.get("place_id")
        rid = r.get("id", "")
        if pid and pid in seen_pid:
            continue
        if rid and rid in seen_id and r.get("gus"):
            continue
        if pid:
            seen_pid.add(pid)
        if rid:
            seen_id.add(rid)
        deduped.append(r)

    # Remove maps-only duplicates when a gus-enriched record shares place_id or similar name
    enriched_pids = {r["place_id"] for r in deduped if r.get("gus") and r.get("place_id")}
    enriched_ids = {r["id"] for r in deduped if r.get("gus")}
    final = []
    for r in deduped:
        if not r.get("gus") and r.get("place_id") in enriched_pids:
            continue
        if not r.get("gus") and r.get("id") in enriched_ids:
            continue
        final.append(r)
    deduped = final

    for r in deduped:
        cnt = wsp_counts.get(r["id"], 0)
        r["wspolnoty_count"] = cnt
        if r.get("gus"):
            r["gus"]["wspolnoty_count"] = cnt

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(deduped),
        "sources": {"maps_full": str(maps_full_path), "gus_csv": zarzadcy_csv, "gus_maps": gus_maps_path},
        "results": deduped,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    write_gaps_report(gap_entries, len(companies), DATA_GUS)
    print(f"\nZapisano {len(deduped)} zarządców -> {output_path}")


if __name__ == "__main__":
    main()
