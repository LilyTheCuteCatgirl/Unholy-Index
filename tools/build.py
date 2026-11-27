"""Build the site's JSON database from books/<religion>/**/*.md."""

import collections
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "books"
OUTPUT = ROOT / "generated" / "entries.json"

ALIASES = {
    "Children and marriage": [
        "Children's rights",
        "Sexual slavery, forced marriage and sexual violence",
    ],
    "Slavery and sexual slavery": [
        "Slavery",
        "Sexual slavery, forced marriage and sexual violence",
    ],
    "Sexual slavery and forced marriage": [
        "Sexual slavery, forced marriage and sexual violence",
    ],
    "Genocide and mass killing": ["Warfare and mass killing"],
    "Warfare": ["Warfare and mass killing"],
    "Other restrictions and unequal privileges": ["Other discriminatory rules"],
}
SUNNI = {
    "Sahih al-Bukhari": "bukhari",
    "Sahih Muslim": "muslim",
    "Sunan Abi Dawud": "abudawud",
    "Sunan an-Nasa'i": "nasai",
    "Jami at-Tirmidhi": "tirmidhi",
    "Sunan Ibn Majah": "ibnmajah",
}
SHIA = {
    "Chapter on the Punishment for Apostasy": "https://shialibrary.com/book/kafi/chapter/528556",
    "Chapter on the Punishment for Sodomy": "https://shialibrary.com/book/kafi/chapter/528516",
    "Chapter on the Punishment for Lesbianism": "https://shialibrary.com/book/kafi/chapter/528518",
    "chapter 96, hadith 2": "https://thaqalayn.com/hadith/5/2/96/2",
    "A Woman's Marriage with Her Slave": "https://shialibrary.com/book/kafi/chapter/626307",
    "Al-Khisal 10-27": "https://thaqalayn.net/chapter/10/11/20",
}


def display_name(name):
    return re.sub(r"[-_]+", " ", name).title()


def enrich_bible(entry):
    ref = entry["reference"]
    match = re.fullmatch(r"(.+?) (\d+:\d+(?:-\d+)?(?:,\s*\d+:\d+(?:-\d+)?)*)", ref)
    if not match:
        return
    book, raw = match.groups()
    ranges = []
    for segment in raw.split(","):
        chapter, start, end = re.fullmatch(r"(\d+):(\d+)(?:-(\d+))?", segment.strip()).groups()
        ranges.append([int(chapter), int(start), int(end or start)])
    entry.update(kind="bible", book=book, ranges=ranges)
    base = "https://www.biblegateway.com/passage/?search=" + quote(ref)
    entry["sources"] = [
        ["Bible Gateway - NRSVUE", base + "&version=NRSVUE"],
        ["Bible Gateway - WEB", base + "&version=WEB"],
    ]
    for chapter, start, end in ranges:
        span = f"{chapter}:{start}" + (f"-{end}" if start != end else "")
        url = "https://bible-api.com/" + quote(f"{book} {span}") + "?translation=web"
        label = "Bible API - WEB" if len(ranges) == 1 else f"Bible API - WEB ({span})"
        entry["sources"].append([label, url])


def enrich_quran(entry):
    match = re.fullmatch(r"(.+) \(([^()]+)\)", entry["reference"])
    if not match:
        return
    name, raw = match.groups()
    ranges = []
    for segment in raw.split(","):
        match = re.fullmatch(r"(\d+):(\d+)(?:-(\d+))?", segment.strip())
        if not match:
            return
        chapter, start, end = match.groups()
        ranges.append([int(chapter), int(start), int(end or start)])
    entry.update(kind="quran", book=name, ranges=ranges)
    for chapter, start, end in ranges:
        label_suffix = f"–{end}" if start != end else ""
        url_suffix = f"-{end}" if start != end else ""
        entry["sources"].extend(
            [
                [
                    f"Quran.com - {chapter}:{start}{label_suffix}",
                    f"https://quran.com/{chapter}/{start}{url_suffix}",
                ],
                [
                    f"Arabic Corpus - {chapter}:{start} (compare translations)",
                    f"https://corpus.quran.com/translation.jsp?chapter={chapter}&verse={start}",
                ],
            ]
        )


def enrich_hadith(entry):
    entry["kind"] = "hadith"
    ref = entry["reference"]
    for book, slug in SUNNI.items():
        match = re.match(re.escape(book) + r" (\d+[a-z]?)\b", ref)
        if not match:
            continue
        number = match.group(1)
        entry.update(book=book, hadithNumber=number, slug=slug)
        entry["sources"] = [["Sunnah.com - full narration", f"https://sunnah.com/{slug}:{number}"]]
        # Other editions use direct source links to avoid numbering mismatches.
        if slug in {"bukhari", "abudawud", "nasai"} and number.isdigit():
            entry["hadithAPI"] = (
                "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/"
                f"eng-{slug}/{number}.json"
            )
            entry["sources"].append(["Hadith API - alternate edition", entry["hadithAPI"]])
        return
    if ref.startswith(("Al-Kafi", "Al-Khisal")):
        entry["book"] = "Al-Kafi" if ref.startswith("Al-Kafi") else "Al-Khisal"
        for key, url in SHIA.items():
            if key in ref:
                label = "Shia Library - chapter" if "shialibrary" in url else "Thaqalayn - reference"
                entry["sources"] = [[label, url]]
                break


PROVIDERS = {"bible": enrich_bible, "quran": enrich_quran, "hadith": enrich_hadith}


def translations_for(rel, warnings):
    """Match translations by original heading and reference, never line number."""
    result = {}
    explanations = {}
    for directory in sorted((ROOT / "translations").glob("*")):
        path = directory / rel
        if not path.is_file():
            continue
        language = directory.name
        theme = "Uncategorized"
        for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = raw.strip()
            heading = re.fullmatch(r"#{1,6}\s+(.+)", line)
            if heading:
                theme = heading.group(1).strip()
            elif line.startswith("- ") and " - " in line[2:]:
                ref, summary = line[2:].split(" - ", 1)
                key = (theme, ref.strip())
                if key in result and language in result[key]:
                    warnings.append(f"{path}:{lineno}: duplicate translation for {key!r}")
                if rel.parts[0] in {"contradictions", "absurdities"}:
                    summary, explanation, _ = split_description(summary)
                    if explanation:
                        explanations.setdefault(key, {})[language] = explanation
                if summary.strip():
                    result.setdefault(key, {})[language] = summary.strip()
    return result, explanations


def split_description(description):
    """Separate the preview, optional explanation and manual source links."""
    summary, *fields = (part.strip() for part in description.split(" | "))
    explanation = ""
    sources = []
    for field in fields:
        if field.startswith("Explanation: "):
            if explanation:
                raise ValueError("Duplicate Explanation field")
            explanation = field.removeprefix("Explanation: ").strip()
            if not explanation:
                raise ValueError("Empty Explanation field")
        else:
            sources.append(field)
    return summary, explanation, sources


def add_manual_sources(entry, manual, location, warnings):
    """Validate manually supplied link syntax, without contacting external sites."""
    for url in manual:
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ("https", "http") or not parsed.hostname:
                raise ValueError("not an HTTP(S) URL")
        except ValueError:
            warnings.append(f"{location}: invalid source URL {url!r}")
            continue
        if url not in [source[1] for source in entry["sources"]]:
            entry["sources"].append([parsed.hostname, url])


def read_collection(path, warnings, base=BOOKS, section="ethical"):
    rel = path.relative_to(base)
    religion = display_name(rel.parts[0])
    translation_path = rel if section == "ethical" else Path(section) / rel
    translations, explanation_translations = translations_for(translation_path, warnings)
    kind = path.stem.lower()
    collection = {"bible": "Bible", "quran": "Quran", "hadith": "Hadith"}.get(
        kind, display_name(path.stem)
    )
    theme = "Uncategorized"
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        heading = re.fullmatch(r"#{1,6}\s+(.+)", line)
        if heading:
            theme = heading.group(1).strip()
            continue
        if not line.startswith("- "):
            continue
        location = f"{rel}:{lineno}"
        if " - " not in line[2:]:
            warnings.append(f"{location}: skipped bullet without reference - summary")
            continue
        ref, description = line[2:].split(" - ", 1)
        ref = ref.strip()
        explanation = ""
        if section == "ethical":
            summary, *manual = (part.strip() for part in description.split(" | "))
        else:
            summary, explanation, manual = split_description(description)
        if not ref or not summary:
            warnings.append(f"{location}: skipped empty reference or summary")
            continue
        tradition, category = "", theme
        if kind == "hadith" and " - " in theme:
            tradition, category = theme.split(" - ", 1)
        entry = {
            "id": f"{rel.as_posix()}:{lineno}" if section == "ethical" else f"{section}/{rel.as_posix()}:{lineno}",
            "section": section,
            "kind": "generic",
            "religion": religion,
            "collection": collection,
            "book": collection,
            "reference": ref,
            "summary": summary,
            "themes": ALIASES.get(category, [category]) if section == "ethical" else [category],
            "originalTheme": theme,
            "tradition": tradition,
            "sources": [],
        }
        if section == "contradictions":
            references = ref.split(" + ")
            if len(references) < 2 or len(set(references)) != len(references) or kind not in PROVIDERS:
                raise ValueError(f"{location}: comparisons require two or more distinct supported references separated by ' + '")
            passages = []
            for reference in references:
                passage = {**entry, "reference": reference, "kind": "generic", "summary": "", "sources": []}
                PROVIDERS[kind](passage)
                if not passage.get("ranges") or not passage["sources"]:
                    raise ValueError(f"{location}: invalid comparison reference {reference!r}")
                passages.append(passage)
            entry.update(kind="comparison", book="Passage comparisons", passages=passages)
        elif kind in PROVIDERS:
            PROVIDERS[kind](entry)
            if section != "ethical" and not entry.get("ranges"):
                raise ValueError(f"{location}: invalid reference {ref!r}")
        if (theme, ref) in translations:
            entry["translations"] = translations[(theme, ref)]
        if explanation:
            entry["explanation"] = explanation
        if (theme, ref) in explanation_translations:
            entry["explanationTranslations"] = explanation_translations[(theme, ref)]
        add_manual_sources(entry, manual, location, warnings)
        if not entry["sources"] and kind in PROVIDERS and section != "contradictions":
            warnings.append(f"{location}: no automatic source for {ref!r}; add an explicit URL")
        yield entry


def collection_order(path, base=BOOKS):
    """Keep Bible/Quran before Hadith; discover all other collections automatically."""
    return (
        path.relative_to(base).parts[0],
        {"bible": 0, "quran": 0, "hadith": 1}.get(path.stem.lower(), 2),
        path.as_posix(),
    )


def build():
    warnings = []
    paths = sorted(BOOKS.glob("*/**/*.md"), key=collection_order)
    entries = [entry for path in paths for entry in read_collection(path, warnings)]
    for section in ("contradictions", "absurdities"):
        base = ROOT / section
        extra_paths = sorted(base.glob("*/**/*.md"), key=lambda path: collection_order(path, base))
        entries.extend(entry for path in extra_paths for entry in read_collection(path, warnings, base, section))
        paths.extend(extra_paths)
    if not entries:
        raise SystemExit("No entries found. Add Markdown files inside books/<religion>/.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    counts = dict(collections.Counter(entry["religion"] for entry in entries))
    print(f"Built {len(entries)} entries from {len(paths)} Markdown files: {counts}", flush=True)
    print("Sections:", dict(collections.Counter(entry["section"] for entry in entries)), flush=True)
    for warning in warnings:
        print("Warning:", warning, flush=True)
    return entries


if __name__ == "__main__":
    build()
