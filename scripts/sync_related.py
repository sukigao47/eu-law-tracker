#!/usr/bin/env python3
"""Sync business-relevant EU soft-law and Official Journal C-series metadata from CELLAR."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from filter_catalog import filter_catalog
from sync import CELLAR_WORK, ROOT, details, select, write_catalog

OJ_C = "http://publications.europa.eu/resource/authority/document-collection/OJ-C"
PAGE_SIZE = 1000
BATCH_SIZE = 80
SOFT_LAW_DAYS = 5 * 366
OJ_C_DAYS = 180
SOFT_LAW_CELEX = re.compile(r"^(3[0-9]{4}[AHGC][0-9]{4,6}|5[0-9]{4}(DC|JC|SC|AA|TA|SA|AB|HB|XB|AE|IE|AC|AR|IR|XR)[0-9]{1,6})$")


def official_url(identifier: str) -> str:
    return "https://eur-lex.europa.eu/legal-content/EN/TXT/?" + urlencode({"uri": f"CELEX:{identifier}"})


def classify_soft_law(identifier: str, title: str) -> tuple[str, str]:
    """Return a source-aware document label and a cautious legal-nature label."""
    descriptor = identifier[5:6] if identifier.startswith("3") else (
        identifier[5:7] if identifier.startswith("5") else ""
    )
    lowered = title.casefold()
    if identifier.startswith("3") and descriptor == "H":
        return "Recommendation", "non_binding_instrument"
    if identifier.startswith("3") and descriptor == "A":
        return "Opinion", "non_binding_instrument"
    if identifier.startswith("3") and descriptor == "G":
        return "Resolution", "generally_non_binding_instrument"
    if identifier.startswith("3") and descriptor == "C":
        return "Declaration", "generally_non_binding_instrument"
    if identifier.startswith("5"):
        if descriptor in {"AA", "AB", "AE", "AC", "AR"}:
            return "Institutional Opinion", "non_legislative_document"
        if descriptor in {"IE", "IR"}:
            return "Own-initiative Opinion", "non_legislative_document"
        if descriptor == "HB":
            return "ECB Recommendation", "non_legislative_document"
        if descriptor in {"TA", "SA"}:
            return "Audit / Special Report", "non_legislative_document"
        if descriptor == "SC":
            return "Staff Working Document", "non_legislative_document"
        if descriptor == "JC":
            return "Joint Communication", "non_legislative_document"
        if descriptor == "DC":
            if "communication" in lowered:
                return "Commission Communication", "non_legislative_document"
            if "white paper" in lowered:
                return "White Paper", "non_legislative_document"
            if "green paper" in lowered:
                return "Green Paper", "non_legislative_document"
            if "report" in lowered:
                return "Commission Report", "non_legislative_document"
            return "Other Commission document", "non_legislative_document"
        if descriptor in {"XB", "XR"}:
            return "Institutional document", "non_legislative_document"
    return "Other non-legislative document", "not_assessed"


def _index(query_body: str, since: date, through: date, identifier_filter: str) -> dict[str, dict]:
    cursor = ""
    found: dict[str, dict] = {}
    while True:
        rows = select(f"""
          SELECT DISTINCT ?id ?work ?published WHERE {{
            {query_body}
            FILTER(?published >= "{since.isoformat()}"^^xsd:date
                   && ?published <= "{through.isoformat()}"^^xsd:date)
            FILTER({identifier_filter})
            FILTER(STR(?id) > "{cursor}")
          }} ORDER BY STR(?id) LIMIT {PAGE_SIZE}
        """)
        for row in rows:
            identifier, work = row.get("id", ""), row.get("work", "")
            if not identifier or not CELLAR_WORK.fullmatch(work):
                continue
            found[identifier] = {"id": identifier, "work": work, "published": row.get("published"), "dateType": row.get("dateType")}
        if len(rows) < PAGE_SIZE:
            return found
        cursor = rows[-1]["id"]
        if len(found) % (PAGE_SIZE * 5) == 0:
            print(f"Related-material index rows: {len(found):,}", flush=True)


def fetch_soft_law(since: date, through: date) -> dict[str, dict]:
    return _index(
        "?work cdm:resource_legal_id_celex ?id ; cdm:work_date_document ?documentDate . "
        "OPTIONAL { ?work cdm:official-journal-act_date_publication ?ojPublished . } "
        "BIND(COALESCE(?ojPublished, ?documentDate) AS ?published) "
        "BIND(IF(BOUND(?ojPublished), \"OJ publication date\", \"Document date\") AS ?dateType)",
        since,
        through,
        f'REGEX(STR(?id), "^{SOFT_LAW_CELEX.pattern[1:-1]}$")',
    )


def fetch_oj_c_series(since: date, through: date) -> dict[str, dict]:
    return _index(
        f"?work cdm:official-journal-act_part_of_collection_document <{OJ_C}> ; "
        "cdm:official-journal-act_date_publication ?published ; "
        "cdm:resource_legal_id_celex ?id . "
        'BIND("OJ publication date" AS ?dateType)',
        since,
        through,
        'STR(?id) != ""',
    )


def hydrate(index: dict[str, dict], category: str) -> list[dict]:
    pairs = [(identifier, row["work"]) for identifier, row in sorted(index.items())]
    hydrated: dict[str, dict] = {}
    batches = [pairs[offset:offset + BATCH_SIZE] for offset in range(0, len(pairs), BATCH_SIZE)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for number, batch_result in enumerate(pool.map(details, batches), start=1):
            hydrated.update(batch_result)
            if number % 10 == 0 or number == len(batches):
                print(f"{category} metadata batches: {number}/{len(batches)}", flush=True)
    records = []
    for identifier, source in index.items():
        record = hydrated.get(identifier, {})
        title = " ".join(record.get("title", "").split())
        if category == "EU_SOFT_LAW":
            label, nature = classify_soft_law(identifier, title)
        else:
            label, nature = "Official Journal C-series document", "not_determined_from_series"
        records.append({
            "id": identifier,
            "work": record.get("work") or source["work"].rsplit("/", 1)[-1],
            "title": title,
            "titleZh": "",
            "published": source.get("published") or record.get("published"),
            "dateType": source.get("dateType") or ("OJ publication date" if category == "OJ_C_SERIES" else "Document date"),
            "entry": None,
            "inForce": None,
            "subjects": record.get("subjects", []),
            "keywords": record.get("keywords", []),
            "concepts": record.get("concepts", []),
            "legalType": label,
            "instrumentClass": label,
            "bindingNature": nature,
            "sourceCategory": category,
            "officialUrl": official_url(identifier),
            "ojSeries": "C" if category == "OJ_C_SERIES" else None,
            "metadataCompleteness": "title_available" if title else "title_missing",
        })
    return records


def deduplicate_materials(*collections: list[dict]) -> list[dict]:
    """Merge records with the same CELEX while retaining every collection tag."""
    merged: dict[str, dict] = {}
    for records in collections:
        for record in records:
            identifier = record["id"]
            if identifier not in merged:
                merged[identifier] = {**record, "sourceCollections": [record["sourceCategory"]]}
                continue
            existing = merged[identifier]
            existing["sourceCollections"] = sorted(
                set(existing["sourceCollections"]) | {record["sourceCategory"]}
            )
            for field in ("title", "published", "officialUrl", "subjects", "keywords", "concepts", "ojSeries"):
                if not existing.get(field) and record.get(field):
                    existing[field] = record[field]
            if record.get("dateType") == "OJ publication date":
                existing["dateType"] = record["dateType"]
    return sorted(merged.values(), key=lambda row: (row.get("published") or "", row["id"]), reverse=True)


def sync_related(output: Path, profile: Path, today: date | None = None) -> dict:
    through = today or datetime.now(ZoneInfo("Europe/Brussels")).date()
    soft_since = through - timedelta(days=SOFT_LAW_DAYS)
    oj_since = through - timedelta(days=OJ_C_DAYS)
    soft_index = fetch_soft_law(soft_since, through)
    oj_index = fetch_oj_c_series(oj_since, through)
    if not soft_index and not oj_index:
        raise ValueError("CELLAR returned no soft-law or OJ C-series records in the configured windows")

    soft_records = hydrate(soft_index, "EU_SOFT_LAW")
    oj_records = hydrate(oj_index, "OJ_C_SERIES")
    # The existing business-profile matcher is reused, but these remain separate
    # non-legislative material categories and are never merged into the binding-act catalogue.
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    soft_catalog = filter_catalog({
        "version": 1, "checkedAt": checked_at, "documents": soft_records
    }, profile)
    oj_catalog = filter_catalog({
        "version": 1, "checkedAt": checked_at, "documents": oj_records
    }, profile)
    combined = deduplicate_materials(soft_catalog["documents"], oj_catalog["documents"])
    result = {
        "version": 1,
        "checkedAt": checked_at,
        "source": "EU Publications Office CELLAR SPARQL",
        "coverage": {
            "softLawSince": soft_since.isoformat(),
            "ojCSeriesSince": oj_since.isoformat(),
            "through": through.isoformat(),
            "softLawIndexed": len(soft_index),
            "ojCSeriesIndexed": len(oj_index),
            "softLawBusinessRelevant": len(soft_catalog["documents"]),
            "ojCSeriesBusinessRelevant": len(oj_catalog["documents"]),
            "businessRelevantUnique": len(combined),
            "softLawCelexDescriptors": ["3A", "3H", "3G", "3C", "5DC", "5JC", "5SC", "5AA", "5TA", "5SA", "5AB", "5HB", "5XB", "5AE", "5IE", "5AC", "5AR", "5IR", "5XR"],
            "ojCollection": "OJ-C",
        },
        "profile": soft_catalog.get("profile", {}),
        "documents": combined,
    }
    write_catalog(output, result)
    print(
        "Published related materials: "
        f"{len(soft_catalog['documents']):,} soft-law and "
        f"{len(oj_catalog['documents']):,} OJ C-series business-relevant records "
        f"({len(combined):,} unique CELEX records)",
        flush=True,
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site/data/related-materials.json")
    parser.add_argument("--profile", type=Path, default=ROOT / "config/terminal-lifecycle.json")
    args = parser.parse_args()
    sync_related(args.output, args.profile)
