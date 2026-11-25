"""Classify and select EU publications relevant to smart-device exports.

The catalogue deliberately distinguishes binding law from preparatory and
non-binding material. Classification from CELEX is indicative metadata;
the legal effect of an individual document must be checked against its basis.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from urllib.parse import quote

CELEX_ACT_CODE = re.compile(r"^3\d{4}[A-Z]{1,3}\d{4,6}$")
CELEX_PARTS = re.compile(r"^(?P<sector>[0-9CE])(?P<year>\d{4})(?P<descriptor>[A-Z]{1,3})(?P<number>\d{4,6})")
CELEX_C_SERIES = re.compile(r"^C(?P<year>\d{4})(?P<number>\d{5})$")
CITATION = re.compile(
    r"\b(?P<kind>regulation|directive|decision)\s*"
    r"(?:\((?:EU|EC|EEC|Euratom|CFSP)\)\s*)?"
    r"(?P<legacy>no\.?\s*)?(?P<first>\d{1,4})\s*/\s*(?P<second>\d{1,5})"
    r"(?:\s*/\s*(?P<suffix>EU|EC|EEC|Euratom|CFSP))?(?![\d/])",
    re.IGNORECASE,
)
KINDS = {"regulation": "R", "directive": "L", "decision": "D"}

SECTOR3 = {
    "R": ("Regulation", "binding"), "L": ("Directive", "binding"),
    "D": ("Decision", "binding"), "H": ("Recommendation", "non-binding"),
    "A": ("Opinion", "non-binding"), "O": ("ECB Guideline", "binding"),
    "G": ("Resolution", "uncertain"), "C": ("Declaration", "uncertain"),
    "B": ("Budget act", "uncertain"), "E": ("Pre-Lisbon CFSP act", "uncertain"),
    "F": ("Pre-Lisbon police and judicial cooperation act", "uncertain"),
    "J": ("Merger-control decision", "binding"), "M": ("Concentration decision", "binding"),
    "K": ("ECSC Recommendation", "non-binding"), "Q": ("Institutional arrangement", "uncertain"),
    "S": ("ECSC Decision", "binding"), "X": ("Other OJ L legal document", "uncertain"),
    "Y": ("Other OJ C legal document", "uncertain"),
}
SECTOR4 = {
    "A": ("Agreement between Member States", "binding"),
    "D": ("Decision of Member State representatives", "uncertain"),
    "X": ("Other OJ L complementary act", "uncertain"),
    "Y": ("Other OJ C complementary act", "uncertain"),
    "Z": ("Complementary legislation", "uncertain"),
}
SECTOR5 = {
    "PC": ("Commission legislative proposal", "preparatory"),
    "DC": ("Commission communication / report / policy paper", "preparatory"),
    "SC": ("Commission staff working document / impact assessment", "preparatory"),
    "JC": ("Joint communication", "preparatory"),
    "XC": ("Other Commission document", "preparatory"),
    "AP": ("European Parliament legislative resolution", "preparatory"),
    "IP": ("European Parliament resolution / declaration", "preparatory"),
    "DP": ("European Parliament internal decision", "uncertain"),
    "XP": ("Other European Parliament document", "preparatory"),
    "AA": ("European Court of Auditors opinion", "preparatory"),
    "TA": ("European Court of Auditors report", "informational"),
    "SA": ("European Court of Auditors special report", "informational"),
    "XA": ("Other Court of Auditors document", "informational"),
    "AB": ("European Central Bank opinion", "non-binding"),
    "HB": ("European Central Bank recommendation", "non-binding"),
    "XB": ("Other European Central Bank document", "informational"),
    "AE": ("European Economic and Social Committee opinion", "non-binding"),
    "IE": ("European Economic and Social Committee own-initiative opinion", "non-binding"),
    "AC": ("European Economic and Social Committee opinion", "non-binding"),
    "XE": ("Other European Economic and Social Committee document", "informational"),
    "AR": ("Committee of the Regions opinion", "non-binding"),
    "IR": ("Committee of the Regions own-initiative opinion", "non-binding"),
    "XR": ("Other Committee of the Regions document", "informational"),
}
SECTOR6 = {
    "CJ": ("Court of Justice judgment", "judicial"),
    "CC": ("Opinion of the Advocate General", "judicial"),
    "CO": ("Court of Justice order", "judicial"),
}
SECTOR2 = {
    "A": ("International agreement", "binding"),
    "D": ("Act of a body created by an international agreement", "uncertain"),
    "P": ("Act of an international parliamentary body", "uncertain"),
    "X": ("Other international-agreement document", "uncertain"),
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w]+|_", " ", text).split())


def phrase_pattern(phrases):
    terms = {normalize(phrase) for phrase in phrases}
    terms.discard("")
    return re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(terms))) + r")\b") if terms else None


def references(title):
    for match in CITATION.finditer(title or ""):
        kind = KINDS[match["kind"].casefold()]
        first, second = int(match["first"]), int(match["second"])
        if match["legacy"] or (not match["suffix"] and not 1950 <= first <= 2099):
            year, number = second, first
        else:
            year, number = first, second
        if year < 100:
            year += 1900 if year >= 50 else 2000
        yield kind, year, number


def classify_celex(identifier: str, title: str = "") -> dict:
    identifier = str(identifier or "")
    sector = identifier[:1]
    descriptor = ""
    if sector == "C" and CELEX_C_SERIES.fullmatch(identifier):
        label, effect = "Official Journal C-series document", "informational"
        return {"sector": sector, "documentTypeCode": "C", "documentTypeLabel": label,
                "legalEffect": effect, "legalNature": "information"}
    match = CELEX_PARTS.match(identifier)
    if match:
        sector, descriptor = match.group("sector"), match.group("descriptor")
    table = {"2": SECTOR2, "3": SECTOR3, "4": SECTOR4, "5": SECTOR5, "6": SECTOR6}
    if sector == "0":
        label, effect, nature = "Consolidated text", "informational", "consolidated"
    elif sector == "1":
        label, effect, nature = "EU Treaty / primary law", "binding", "primary-law"
    elif sector == "7":
        label, effect, nature = "National transposition measure", "uncertain", "national-measure"
    elif sector == "9":
        label, effect, nature = "Parliamentary question", "informational", "institutional-information"
    elif sector == "E":
        label, effect, nature = "EFTA document", "uncertain", "external"
    else:
        label, effect = table.get(sector, {}).get(descriptor, ("Other EU document", "uncertain"))
        nature = {
            "2": "international-agreement", "3": "secondary-law",
            "4": "complementary-law", "5": "preparatory",
            "6": "judicial", "C": "official-journal-information",
        }.get(sector, "other")
    title_lower = (title or "").casefold()
    if sector == "3" and descriptor in {"R", "L", "D"}:
        if "delegated" in title_lower:
            label = "Delegated " + label
        elif "implementing" in title_lower:
            label = "Implementing " + label
    return {
        "sector": sector, "documentTypeCode": descriptor or "OTHER",
        "documentTypeLabel": label, "legalEffect": effect, "legalNature": nature,
    }


def eli_uri(identifier: str, title: str):
    match = re.search(
        r"\b(Regulation|Directive|Decision)\s+\((?:EU|EC)\)\s+(\d{4})/(\d{1,5})",
        title or "", re.IGNORECASE,
    )
    if not match:
        return None
    kind = {"regulation": "reg", "directive": "dir", "decision": "dec"}[match.group(1).casefold()]
    return f"https://data.europa.eu/eli/{kind}/{match.group(2)}/{match.group(3)}/oj"


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
        if any(not CELEX_ACT_CODE.fullmatch(code) for code in acts):
            raise ValueError(f"Invalid CELEX act number in topic {row['id']}")
        cited = set()
        for code in follow:
            match = re.fullmatch(r"3\d{4}([A-Z]{1,3})(\d{4,6})", code)
            if match:
                cited.add((match.group(1), int(code[1:5]), int(match.group(2))))
        return cls(
            id=row["id"], label=row["label"], acts=acts, follow=cited,
            concepts=set(row.get("concepts", [])),
            labels={normalize(label) for label in row.get("labels", [])},
            phrases=phrase_pattern(row.get("phrases", [])),
            context=phrase_pattern(row.get("context", [])),
            product_title=row.get("product_title", False),
        )

    def matches(self, identifier, cited, concepts, labels, text, product, product_title):
        return (
            identifier in self.acts or not self.follow.isdisjoint(cited)
            or not self.concepts.isdisjoint(concepts) or not self.labels.isdisjoint(labels)
            or (self.phrases is not None and self.phrases.search(text))
            or (product and self.context is not None and self.context.search(text))
            or (self.product_title and product_title)
        )


def filter_catalog(catalog, config_path):
    with config_path.open(encoding="utf-8") as source:
        profile = json.load(source)
    topics = [Topic.from_config(row) for row in profile["topics"]]
    if not topics or len({topic.id for topic in topics}) != len(topics):
        raise ValueError("The business profile must contain distinct topic IDs")
    products = phrase_pattern(profile["products"])
    if products is None:
        raise ValueError("The business profile must define product terms")

    documents = []
    for original in catalog["documents"]:
        record = dict(original)
        record["titleEn"] = record.get("titleEn") or record.get("title") or ""
        record.setdefault("titleZh", "")
        record.setdefault("eurlexUrl", "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A" + quote(record["id"]))
        record.setdefault("eliUrl", eli_uri(record["id"], record.get("titleEn", "")))
        record.update(classify_celex(record["id"], record.get("titleEn", "")))
        title = normalize(record["titleEn"])
        cited = set(references(record["titleEn"]))
        labels = {normalize(item) for item in (*record.get("subjects", []), *record.get("keywords", []))}
        concepts = set(record.get("concepts", ()))
        text = " | ".join((title, *labels, record["documentTypeLabel"].casefold()))
        product_title = products.search(title) is not None
        product = product_title or products.search(text) is not None
        matches = [
            topic.id for topic in topics
            if topic.matches(record["id"], cited, concepts, labels, text, product, product_title)
        ]
        if matches:
            record["businessTopics"] = matches
            documents.append(record)

    return {
        **catalog,
        "profile": {
            "id": profile["id"], "label": profile["label"],
            "topics": [{"id": topic.id, "label": topic.label} for topic in topics],
        },
        "documents": documents,
    }
