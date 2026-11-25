#!/usr/bin/env python3
"""Update the public catalogue from the EU Publications Office's Cellar."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from filter_catalog import filter_catalog


ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
PREFIXES = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX cellar: <http://publications.europa.eu/resource/cellar/>
"""
CELEX = r"^3[0-9]{4}[RLD][0-9]+(P|[(][0-9]+[)])?$"
CELLAR_WORK = re.compile(r"https?://publications[.]europa[.]eu/resource/cellar/[0-9a-f-]+")
RECENT_DAYS = 90
PAGE_SIZE = 5000
RANGE_BATCH_SIZE = 450
VALUES_BATCH_SIZE = 80
DETAIL_LIMIT = 9500
ROOT = Path(__file__).resolve().parent.parent


def select(query):
    request = Request(
        ENDPOINT,
        data=urlencode({"query": PREFIXES + query}).encode(),
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "EU-Law-Tracker/1.0 (public legal metadata catalogue)",
        },
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.load(response)
                if response.status != 200 or response.headers.get("X-SQL-State"):
                    raise ValueError("Cellar returned an incomplete query result")
            rows = payload["results"]["bindings"]
            return [{key: term["value"] for key, term in row.items()} for row in rows]
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            retry_after = error.headers.get("Retry-After", "")
            time.sleep(min(120, int(retry_after)) if retry_after.isdigit() else 3 ** (attempt + 1))
        except (URLError, TimeoutError, ValueError):
            if attempt == 3:
                raise
            time.sleep(3 ** (attempt + 1))


def in_force_index():
    cursor = ""
    found = {}
    while True:
        rows = select(f"""
          SELECT DISTINCT ?id ?work WHERE {{
            ?work cdm:resource_legal_in-force true ;
                  cdm:resource_legal_id_celex ?id .
            FILTER(REGEX(STR(?id), "{CELEX}"))
            FILTER(STR(?id) > "{cursor}")
          }} ORDER BY STR(?id) STR(?work) LIMIT {PAGE_SIZE}
        """)
        for row in rows:
            found.setdefault(row["id"], row["work"])
        print(f"Current acts identified: {len(found):,}", flush=True)
        if len(rows) < PAGE_SIZE:
            return found
        cursor = rows[-1]["id"]


def recent_index(since, through):
    rows = select(f"""
      SELECT DISTINCT ?id ?work ?published WHERE {{
        ?work cdm:official-journal-act_date_publication ?published ;
              cdm:official-journal-act_part_of_collection_document
                <http://publications.europa.eu/resource/authority/document-collection/OJ-L> ;
              cdm:resource_legal_id_celex ?id .
        FILTER(?published >= "{since}"^^xsd:date && ?published <= "{through}"^^xsd:date)
        FILTER(REGEX(STR(?id), "{CELEX}"))
      }} ORDER BY ?published STR(?work) LIMIT 8000
    """)
    if len(rows) >= 8000:
        raise ValueError("Recent-publication query reached its result limit")
    return {row["id"]: row for row in rows}


def details(ids_and_works, in_force_range=False):
    works = {}
    for identifier, work in ids_and_works:
        if not CELLAR_WORK.fullmatch(work):
            raise ValueError(f"Unexpected Cellar work identifier for {identifier}")
        works.setdefault(work, []).append(identifier)

    if in_force_range:
        first = ids_and_works[0][0]
        last = ids_and_works[-1][0]
        scope = f"""
          {{ SELECT DISTINCT ?work WHERE {{
            ?work cdm:resource_legal_in-force true ; cdm:resource_legal_id_celex ?id .
            FILTER(STR(?id) >= "{first}" && STR(?id) <= "{last}")
            FILTER(REGEX(STR(?id), "{CELEX}"))
          }} }}
        """
    else:
        values = " ".join(f"cellar:{work.rsplit('/', 1)[1]}" for work in works)
        scope = f"VALUES ?work {{ {values} }}"
    rows = select(f"""
      SELECT DISTINCT ?work ?field ?value WHERE {{
        {scope}
        {{
          ?expression cdm:expression_belongs_to_work ?work ;
            cdm:expression_uses_language
              <http://publications.europa.eu/resource/authority/language/ENG> ;
            cdm:expression_title ?value .
          BIND("title" AS ?field)
        }}
        UNION {{
          ?work cdm:official-journal-act_date_publication ?value .
          BIND("published" AS ?field)
        }}
        UNION {{
          ?work cdm:resource_legal_published_in_official-journal/cdm:work_date_document ?value .
          BIND("oldPublished" AS ?field)
        }}
        UNION {{
          ?work cdm:resource_legal_in-force ?value .
          BIND("inForce" AS ?field)
        }}
        UNION {{
          ?work cdm:resource_legal_date_entry-into-force ?value .
          BIND("entry" AS ?field)
        }}
        UNION {{
          ?work cdm:resource_legal_date_applicability ?value .
          BIND("application" AS ?field)
        }}
        UNION {{
          ?work cdm:resource_legal_is_about_subject-matter/skos:prefLabel ?value .
          FILTER(LANG(?value) = "en")
          BIND("subject" AS ?field)
        }}
        UNION {{
          ?work cdm:work_is_about_concept_eurovoc/skos:prefLabel ?value .
          FILTER(LANG(?value) = "en")
          BIND("keyword" AS ?field)
        }}
        UNION {{
          ?work cdm:work_is_about_concept_eurovoc ?concept .
          BIND(STR(?concept) AS ?value)
          BIND("concept" AS ?field)
        }}
      }} LIMIT {DETAIL_LIMIT}
    """)
    if len(rows) >= DETAIL_LIMIT:
        middle = len(ids_and_works) // 2
        if middle == 0:
            raise ValueError("One Cellar work exceeded the metadata query limit")
        return (details(ids_and_works[:middle], in_force_range)
                | details(ids_and_works[middle:], in_force_range))

    by_work = {work: {} for work in works}
    for row in rows:
        if row["work"] in by_work:
            by_work[row["work"]].setdefault(row["field"], set()).add(row["value"])

    result = {}
    for work, identifiers in works.items():
        record = by_work[work]
        dates = sorted(record.get("published") or record.get("oldPublished", ()))
        titles = record.get("title", ())
        title = max(titles, key=lambda value: (len(value), value), default="")
        in_force = record.get("inForce", set())
        for identifier in identifiers:
            result[identifier] = {
                "id": identifier,
                "work": work.rsplit("/", 1)[1],
                "title": " ".join(title.split()),
                "published": dates[0] if dates else None,
                "entry": min(record.get("entry", ()), default=None),
                "applicationDates": sorted(record.get("application", ())),
                "inForce": True if in_force & {"true", "1"} else
                False if in_force & {"false", "0"} else None,
                "subjects": sorted(record.get("subject", ()), key=str.casefold),
                "keywords": sorted(record.get("keyword", ()), key=str.casefold),
                "concepts": sorted(record.get("concept", ())),
            }
    if ids_and_works and not any(record["title"] for record in result.values()):
        raise ValueError("Cellar returned no English titles for an entire batch")
    return result


def read_previous(paths):
    previous = None
    for path in paths:
        if path is not None and path.is_file():
            with path.open(encoding="utf-8") as source:
                candidate = json.load(source)
            if candidate.get("version") == 1 and "profile" not in candidate and (
                previous is None or candidate["checkedAt"] > previous["checkedAt"]
            ):
                previous = candidate
    return previous


def write_catalog(path, catalog):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sync(output, previous_path, cache, profile, rebuild, recent_only):
    today = datetime.now(ZoneInfo("Europe/Brussels")).date()
    since = today - timedelta(days=RECENT_DAYS - 1)
    recent = recent_index(since, today)
    print(f"Recent OJ L acts identified: {len(recent):,}", flush=True)
    if not recent:
        raise ValueError("Cellar found no legislation across the recent publication window")

    current = {} if recent_only else in_force_index()
    previous = None if rebuild or recent_only else read_previous([cache, previous_path, output])
    before = {row["id"]: row for row in previous["documents"]} if previous else {}
    if not recent_only:
        old_current = sum(row["inForce"] is True for row in before.values())
        if len(current) < max(1000, old_current * 0.9):
            raise ValueError("Cellar returned an unexpectedly small current catalogue")

    wanted = dict(current)
    wanted.update({identifier: row["work"] for identifier, row in recent.items()})
    refreshed_since = (today - timedelta(days=13)).isoformat()
    to_fetch = []
    kept = {}
    for identifier, work in wanted.items():
        previous_row = before.get(identifier)
        recent_date = recent.get(identifier, {}).get("published", "")
        if (previous_row is None or previous_row["work"] != work.rsplit("/", 1)[1]
                or not previous_row["title"] or recent_date >= refreshed_since
                or (identifier in recent and not (previous_row["subjects"] or previous_row["keywords"]))
                or (previous_row["inForce"] is True) != (identifier in current)):
            to_fetch.append((identifier, work))
        else:
            kept[identifier] = previous_row

    use_ranges = len(to_fetch) > len(current) * 0.8
    range_rows = []
    value_rows = []
    for pair in to_fetch:
        if use_ranges and current.get(pair[0]) == pair[1]:
            range_rows.append(pair)
        else:
            value_rows.append(pair)
    range_rows.sort()
    batches = [
        (rows[offset:offset + size], in_force_range)
        for rows, size, in_force_range in (
            (range_rows, RANGE_BATCH_SIZE, True),
            (value_rows, VALUES_BATCH_SIZE, False),
        )
        for offset in range(0, len(rows), size)
    ]
    print(f"Fetching metadata for {len(to_fetch):,} acts in {len(batches)} batches", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = pool.map(lambda batch: details(*batch), batches)
        for number, batch in enumerate(results, start=1):
            kept.update(batch)
            if number % 5 == 0 or number == len(batches):
                print(f"Metadata batches complete: {number}/{len(batches)}", flush=True)

    for identifier, record in kept.items():
        if not recent_only:
            if identifier in current:
                record["inForce"] = True
            elif record["inForce"] is True:
                record["inForce"] = None
        if identifier in recent:
            record["published"] = recent[identifier]["published"]

    documents = sorted(kept.values(), key=lambda row: (row["published"] or "", row["id"]), reverse=True)
    catalog = {
        "version": 1,
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "through": today.isoformat(),
        "recentSince": since.isoformat(),
        "recentOnly": recent_only,
        "documents": documents,
    }
    if len(documents) != len(wanted):
        raise ValueError("The number of records changed unexpectedly while building the catalogue")
    published = filter_catalog(catalog, profile)
    # Enrich only the published business catalogue, including older cached acts.
    for offset in range(0, len(published["documents"]), 80):
        batch = published["documents"][offset:offset+80]
        works = " ".join("cellar:" + row["work"] for row in batch if CELLAR_WORK.fullmatch("http://publications.europa.eu/resource/cellar/" + row["work"]))
        if not works:
            continue
        rows = select(f"""SELECT DISTINCT ?work ?value WHERE {{
            VALUES ?work {{ {works} }}
            ?work cdm:resource_legal_date_applicability ?value .
        }}""")
        by_work = {}
        for row in rows:
            by_work.setdefault(row["work"].rsplit("/", 1)[-1], set()).add(row["value"])
        for row in batch:
            row["applicationDates"] = sorted(by_work.get(row["work"], set()))

    if not recent_only:
        write_catalog(cache, catalog)
    write_catalog(output, published)
    # The static Pages artifact contains only the site/ directory. Copy the
    # taxonomy and curated translations beside catalog.json for browser use.
    output.parent.mkdir(parents=True, exist_ok=True)
    for filename in ("business-taxonomy.json", "titles-zh.json", "source-registry.json"):
        source = profile.with_name(filename)
        if source.is_file():
            shutil.copyfile(source, output.parent / filename)
    print(f"Published profile {published['profile']['id']}: "
          f"{len(published['documents']):,} of {len(documents):,} acts", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site/data/catalog.json")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--cache", type=Path, default=ROOT / ".catalog-cache/catalog.json")
    parser.add_argument("--profile", type=Path, default=ROOT / "config/terminal-lifecycle.json")
    parser.add_argument("--rebuild", action="store_true", help="Refresh all metadata")
    parser.add_argument("--recent-only", action="store_true", help="Build a preview with recent acts")
    args = parser.parse_args()
    if args.output.resolve() == args.cache.resolve():
        parser.error("--output and --cache must point to different files")
    sync(args.output, args.previous, args.cache, args.profile, args.rebuild, args.recent_only)
