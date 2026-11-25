#!/usr/bin/env python3
"""Sync CJEU case-law metadata from the EU Publications Office CELLAR knowledge graph."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from filter_catalog import filter_catalog
from sync import CELLAR_WORK, ROOT, select, write_catalog

PAGE_SIZE = 1000
BATCH_SIZE = 50
DETAIL_LIMIT = 9000
CASE_LAW_DAYS = 10 * 366
CASE_CLASSES = {
    "document_cjeu": "CJEU document",
    "case-law": "Case-law document",
    "summary_case-law": "Case-law summary",
    "court-report": "Court report",
}
CASE_CLASS_URIS = " ".join(
    f"<http://publications.europa.eu/ontology/cdm#{name}>"
    for name in CASE_CLASSES
)
INFOCURIA_SEARCH = "https://infocuria.curia.europa.eu/tabs/advanced_search"


def case_url(case_number: str | None) -> str:
    """Return the official CURIA case page when a docket number is known."""
    if case_number:
        return "https://curia.europa.eu/juris/liste.jsf?" + urlencode(
            {"num": case_number, "language": "en"}
        )
    return INFOCURIA_SEARCH


def court_from_identifiers(ecli: str | None, case_number: str | None, court_id: str | None) -> str:
    value = (ecli or "").upper()
    number = (case_number or "").upper()
    if value.startswith("ECLI:EU:C:") or number.startswith("C-"):
        return "Court of Justice"
    if value.startswith("ECLI:EU:T:") or number.startswith("T-"):
        return "General Court"
    if value.startswith("ECLI:EU:F:") or number.startswith("F-"):
        return "Civil Service Tribunal (historical)"
    return court_id or "Not specified in retrieved metadata"


def classify_document_type(class_uri: str | None, title: str) -> tuple[str, str]:
    """Classify only when the source class or document title supports it."""
    source_class = (class_uri or "").rsplit("#", 1)[-1]
    lowered = title.casefold()
    if source_class == "court-report":
        return "Court report", "case_law_reference_material"
    if source_class == "summary_case-law":
        return "Case-law summary", "case_law_reference_material"
    if "opinion of the advocate general" in lowered or "opinion of advocate general" in lowered:
        return "Advocate General's Opinion", "advocate_general_opinion"
    if "opinion of the court" in lowered:
        return "Opinion of the Court", "court_opinion"
    if "judgment" in lowered:
        return "Judgment", "judicial_decision"
    if "order" in lowered:
        return "Order", "judicial_decision"
    if source_class == "document_cjeu":
        return "CJEU document (type not determined)", "judicial_document_type_unverified"
    if source_class == "case-law":
        return "Case-law document (type not determined)", "judicial_document_type_unverified"
    return "CJEU case-law material (type not determined)", "judicial_document_type_unverified"


def fetch_index(since: date, through: date) -> dict[str, dict]:
    """Page through official CELLAR case-law works by creation date."""
    cursor = ""
    found: dict[str, dict] = {}
    while True:
        rows = select(f"""
          SELECT DISTINCT ?work WHERE {{
            ?work a ?class ; cdm:date_creation_legacy ?created .
            FILTER(?class IN ({CASE_CLASS_URIS}))
            FILTER(?created >= "{since.isoformat()}"^^xsd:date
                   && ?created <= "{through.isoformat()}"^^xsd:date)
            FILTER(STR(?work) > "{cursor}")
          }} ORDER BY STR(?work) LIMIT {PAGE_SIZE}
        """)
        for row in rows:
            work = row.get("work", "")
            if CELLAR_WORK.fullmatch(work):
                found[work] = {"work": work}
        print(f"CELLAR case-law works indexed: {len(found):,}", flush=True)
        if len(rows) < PAGE_SIZE:
            return found
        cursor = rows[-1]["work"]


def _details(batch: list[str]) -> dict[str, dict]:
    values = " ".join(f"cellar:{work.rsplit('/', 1)[1]}" for work in batch)
    rows = select(f"""
      SELECT DISTINCT ?work ?class ?ecli ?created ?documentDate ?title
        ?caseNumber ?caseTitle ?courtId ?subject ?keyword ?digest WHERE {{
        VALUES ?work {{ {values} }}
        OPTIONAL {{ ?work a ?class . FILTER(?class IN ({CASE_CLASS_URIS})) }}
        OPTIONAL {{ ?work cdm:case-law_ecli ?ecli . }}
        OPTIONAL {{ ?work cdm:date_creation_legacy ?created . }}
        OPTIONAL {{ ?work cdm:work_date_document ?documentDate . }}
        OPTIONAL {{
          ?expression cdm:expression_belongs_to_work ?work ;
            cdm:expression_uses_language
              <http://publications.europa.eu/resource/authority/language/ENG> ;
            cdm:expression_title ?title .
        }}
        OPTIONAL {{
          ?case a cdm:case_court ;
            cdm:dossier_contains_work ?work ;
            cdm:dossier_identifier ?caseNumber .
          OPTIONAL {{ ?case cdm:dossier_title ?caseTitle . }}
          OPTIONAL {{ ?case cdm:case_court_identifier_court ?courtId . }}
        }}
        OPTIONAL {{
          ?work cdm:work_is_about_subject-matter ?subjectConcept .
          ?subjectConcept skos:prefLabel ?subject .
          FILTER(LANG(?subject) = "en")
        }}
        OPTIONAL {{
          ?work cdm:work_is_about_concept_eurovoc ?eurovoc .
          ?eurovoc skos:prefLabel ?keyword .
          FILTER(LANG(?keyword) = "en")
        }}
        OPTIONAL {{
          ?work cdm:case-law_is_about_concept_case-law ?digestConcept .
          ?digestConcept skos:prefLabel ?digest .
          FILTER(LANG(?digest) = "en")
        }}
      }} LIMIT {DETAIL_LIMIT}
    """)
    if len(rows) >= DETAIL_LIMIT:
        if len(batch) <= 1:
            raise ValueError("One CELLAR case-law work exceeded the metadata query limit")
        middle = len(batch) // 2
        return _details(batch[:middle]) | _details(batch[middle:])

    result: dict[str, dict] = {}
    for row in rows:
        work = row.get("work")
        if work not in batch:
            continue
        record = result.setdefault(work, {
            "classes": set(), "eclis": set(), "created": set(), "documentDates": set(),
            "titles": set(), "caseNumbers": set(), "caseTitles": set(), "courtIds": set(),
            "subjects": set(), "keywords": set(), "digest": set(),
        })
        for source, target in (
            ("class", "classes"), ("ecli", "eclis"), ("created", "created"),
            ("documentDate", "documentDates"), ("title", "titles"),
            ("caseNumber", "caseNumbers"), ("caseTitle", "caseTitles"),
            ("courtId", "courtIds"), ("subject", "subjects"),
            ("keyword", "keywords"), ("digest", "digest"),
        ):
            if row.get(source):
                record[target].add(row[source])
    return result


def hydrate(index: dict[str, dict]) -> list[dict]:
    works = sorted(index)
    batches = [works[offset:offset + BATCH_SIZE] for offset in range(0, len(works), BATCH_SIZE)]
    hydrated: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for number, batch_result in enumerate(pool.map(_details, batches), start=1):
            hydrated.update(batch_result)
            if number % 10 == 0 or number == len(batches):
                print(f"CJEU metadata batches: {number}/{len(batches)}", flush=True)

    records = []
    for work in works:
        meta = hydrated.get(work, {})
        title = max(meta.get("titles", ()), key=lambda value: (len(value), value), default="")
        case_title = max(meta.get("caseTitles", ()), key=lambda value: (len(value), value), default="")
        case_number = sorted(meta.get("caseNumbers", ()), key=str.casefold)[0] if meta.get("caseNumbers") else None
        ecli = sorted(meta.get("eclis", ()))[0] if meta.get("eclis") else None
        source_class = sorted(meta.get("classes", ()))[0] if meta.get("classes") else None
        document_type, nature = classify_document_type(source_class, title or case_title)
        document_date = min(meta.get("documentDates", ()), default=None)
        created_date = min(meta.get("created", ()), default=None)
        date_value = document_date or created_date
        date_type = "CELLAR document date" if document_date else (
            "CELLAR record creation date (verify against CURIA)" if created_date else "Date unavailable"
        )
        identifier = ecli or ("CELLAR:" + work.rsplit("/", 1)[-1])
        subjects = sorted(meta.get("subjects", ()), key=str.casefold)
        keywords = sorted(meta.get("keywords", ()), key=str.casefold)
        digest = sorted(meta.get("digest", ()), key=str.casefold)
        completeness = [
            field for field, value in (
                ("ECLI", ecli), ("case number", case_number), ("English title", title or case_title),
                ("date", date_value), ("court", court_from_identifiers(ecli, case_number, None)
                 if ecli or case_number else None),
            ) if value
        ]
        records.append({
            "id": identifier,
            "ecli": ecli,
            "caseNumber": case_number,
            "parties": case_title,
            "court": court_from_identifiers(ecli, case_number, next(iter(meta.get("courtIds", ())), None)),
            "work": work.rsplit("/", 1)[-1],
            "title": " ".join((title or case_title).split()),
            "titleZh": "",
            "published": date_value,
            "decisionDate": document_date,
            "recordCreated": created_date,
            "dateType": date_type,
            "subjects": subjects,
            "keywords": keywords,
            "caseLawDigest": digest,
            "concepts": [],
            "legalType": document_type,
            "instrumentClass": document_type,
            "bindingNature": nature,
            "sourceCategory": "CASE_LAW",
            "sourceClass": source_class.rsplit("#", 1)[-1] if source_class else None,
            "officialUrl": case_url(case_number),
            "cellarUrl": work,
            "metadataCompleteness": completeness,
            "metadataMissing": [
                field for field, value in (
                    ("ECLI", ecli), ("case number", case_number), ("title", title or case_title),
                    ("date", date_value), ("court", ecli or case_number or next(iter(meta.get("courtIds", ())), None)),
                ) if not value
            ],
        })
    return records


def deduplicate(records: list[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    for record in records:
        key = record["id"]
        if key not in unique:
            unique[key] = record
            continue
        current = unique[key]
        for field in ("subjects", "keywords", "caseLawDigest", "metadataCompleteness"):
            current[field] = sorted(set(current.get(field, [])) | set(record.get(field, [])), key=str.casefold)
        for field in ("caseNumber", "parties", "court", "title", "published", "decisionDate", "officialUrl"):
            if not current.get(field) and record.get(field):
                current[field] = record[field]
    return sorted(unique.values(), key=lambda row: (row.get("published") or "", row["id"]), reverse=True)


def sync_case_law(output: Path, profile: Path, today: date | None = None) -> dict:
    through = today or datetime.now(ZoneInfo("Europe/Brussels")).date()
    since = through - timedelta(days=CASE_LAW_DAYS)
    index = fetch_index(since, through)
    if not index:
        raise ValueError("CELLAR returned no CJEU case-law works in the configured window")
    records = hydrate(index)
    filtered = filter_catalog({
        "version": 1,
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "documents": records,
    }, profile)
    documents = deduplicate(filtered["documents"])
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {
        "version": 1,
        "checkedAt": checked_at,
        "source": "EU Publications Office CELLAR SPARQL; official CURIA case-law metadata",
        "coverage": {
            "since": since.isoformat(),
            "through": through.isoformat(),
            "indexedWorks": len(index),
            "hydratedWorks": len(records),
            "businessRelevantRecords": len(documents),
            "uniqueEcliOrCellarIds": len(documents),
            "includedClasses": sorted(CASE_CLASSES),
            "businessProfile": filtered.get("profile", {}).get("id"),
        },
        "profile": filtered.get("profile", {}),
        "documents": documents,
    }
    write_catalog(output, result)
    print(
        f"Published {len(documents):,} business-relevant CJEU case-law records "
        f"from {len(index):,} CELLAR works",
        flush=True,
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site/data/case-law.json")
    parser.add_argument("--profile", type=Path, default=ROOT / "config/terminal-lifecycle.json")
    args = parser.parse_args()
    sync_case_law(args.output, args.profile)
