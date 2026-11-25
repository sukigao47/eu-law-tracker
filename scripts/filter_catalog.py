"""Select public catalogue records using a configurable business profile."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata


ACT_CODE = re.compile(r"3\d{4}[RLD]\d{4,6}")
CITATION = re.compile(
    r"\b(?P<kind>regulation|directive|decision)\s*"
    r"(?:\((?:EU|EC|EEC|Euratom|CFSP)\)\s*)?"
    r"(?P<legacy>no\.?\s*)?(?P<first>\d{1,4})\s*/\s*(?P<second>\d{1,4})"
    r"(?:\s*/\s*(?P<suffix>EU|EC|EEC|Euratom|CFSP))?(?![\d/])",
    re.IGNORECASE,
)
KINDS = {"regulation": "R", "directive": "L", "decision": "D"}


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w]+|_", " ", text).split())


def phrase_pattern(phrases):
    terms = {normalize(phrase) for phrase in phrases}
    terms.discard("")
    return re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(terms))) + r")\b") if terms else None


def references(title):
    """Recognize both numbered legacy citations and year-first EU citations."""
    for match in CITATION.finditer(title):
        kind = KINDS[match["kind"].casefold()]
        first, second = int(match["first"]), int(match["second"])
        if match["legacy"] or (not match["suffix"] and not 1950 <= first <= 2099):
            year, number = second, first
        else:
            year, number = first, second
        if year < 100:
            year += 1900 if year >= 50 else 2000
        yield kind, year, number


@dataclass
class Topic:
    id: str
    label: str
    acts: set
    follow: set
    concepts: set
    labels: set
    phrases: re.Pattern | None
    context: re.Pattern | None
    product_title: bool

    @classmethod
    def from_config(cls, row):
        follow = set(row.get("follow", []))
        acts = set(row.get("acts", [])) | follow
        if any(not ACT_CODE.fullmatch(code) for code in acts):
            raise ValueError(f"Invalid CELEX act number in topic {row['id']}")
        return cls(
            id=row["id"],
            label=row["label"],
            acts=acts,
            follow={(code[5], int(code[1:5]), int(code[6:])) for code in follow},
            concepts=set(row.get("concepts", [])),
            labels={normalize(label) for label in row.get("labels", [])},
            phrases=phrase_pattern(row.get("phrases", [])),
            context=phrase_pattern(row.get("context", [])),
            product_title=row.get("product_title", False),
        )

    def matches(self, identifier, cited, concepts, labels, text, product, product_title):
        return (
            identifier in self.acts
            or not self.follow.isdisjoint(cited)
            or not self.concepts.isdisjoint(concepts)
            or not self.labels.isdisjoint(labels)
            or (self.phrases is not None and self.phrases.search(text))
            or (product and self.context is not None and self.context.search(text))
            or (self.product_title and product_title)
        )


def classify_instrument(title, kind_code):
    normalized = title.casefold()
    for marker, label in (
        ("commission delegated regulation", "Delegated Regulation"),
        ("delegated regulation", "Delegated Regulation"),
        ("commission delegated directive", "Delegated Directive"),
        ("delegated directive", "Delegated Directive"),
        ("commission delegated decision", "Delegated Decision"),
        ("delegated decision", "Delegated Decision"),
        ("commission implementing regulation", "Implementing Regulation"),
        ("implementing regulation", "Implementing Regulation"),
        ("commission implementing directive", "Implementing Directive"),
        ("implementing directive", "Implementing Directive"),
        ("commission implementing decision", "Implementing Decision"),
        ("implementing decision", "Implementing Decision"),
    ):
        if normalized.startswith(marker):
            return label
    return {"R": "Regulation", "L": "Directive", "D": "Decision"}.get(kind_code, "Other")


def filter_catalog(catalog, config_path):
    with config_path.open(encoding="utf-8") as source:
        profile = json.load(source)
    topics = [Topic.from_config(row) for row in profile["topics"]]
    if not topics or len({topic.id for topic in topics}) != len(topics):
        raise ValueError("The business profile must contain distinct topic IDs")
    products = phrase_pattern(profile["products"])
    if products is None:
        raise ValueError("The business profile must define product terms")

    taxonomy_path = config_path.with_name("business-taxonomy.json")
    titles_path = config_path.with_name("titles-zh.json")
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8")) if taxonomy_path.is_file() else {"departments": [], "crossCutting": []}
    chinese_titles = json.loads(titles_path.read_text(encoding="utf-8")) if titles_path.is_file() else {}
    department_map = {}
    for department in taxonomy.get("departments", []):
        for topic_id in department.get("topics", []):
            department_map.setdefault(topic_id, set()).add(department["id"])
    cross_map = {}
    for topic in taxonomy.get("crossCutting", []):
        for topic_id in topic.get("topics", []):
            cross_map.setdefault(topic_id, set()).add(topic["id"])

    documents = []
    for record in catalog["documents"]:
        title = normalize(record["title"])
        cited = set(references(record["title"]))
        labels = {normalize(item) for item in (*record["subjects"], *record["keywords"])}
        concepts = set(record.get("concepts", ()))
        text = " | ".join((title, *labels))
        product_title = products.search(title) is not None
        product = product_title or products.search(text) is not None
        matches = [
            topic.id for topic in topics
            if topic.matches(record["id"], cited, concepts, labels, text, product, product_title)
        ]
        if matches:
            department_ids = sorted({department_id for topic_id in matches for department_id in department_map.get(topic_id, set())})
            cross_cutting_ids = sorted({topic_id for matched_topic in matches for topic_id in cross_map.get(matched_topic, set())})
            kind_code = record["id"][5] if len(record["id"]) > 5 else ""
            legal_type = {"R": "Regulation", "L": "Directive", "D": "Decision"}.get(kind_code, "Other")
            instrument_class = classify_instrument(record["title"], kind_code)
            documents.append({
                **record,
                "titleZh": chinese_titles.get(record["id"], ""),
                "legalType": legal_type,
                "instrumentClass": instrument_class,
                "sourceCategory": "EU_LEGISLATION",
                "officialUrl": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{record['id']}",
                "businessTopics": matches,
                "departments": department_ids,
                "crossCuttingTopics": cross_cutting_ids,
            })

    return {
        **catalog,
        "profile": {
            "id": profile["id"],
            "label": profile["label"],
            "topics": [{"id": topic.id, "label": topic.label} for topic in topics],
            "departments": taxonomy.get("departments", []),
            "crossCutting": taxonomy.get("crossCutting", []),
        },
        "documents": documents,
    }
