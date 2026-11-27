"""Generate a local full-text database for indexed Bible and Quran passages."""

import io
import json
import re
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from build import build

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "texts.json"
BIBLE_BOOKS = dict(zip(
    "Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|"
    "1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalms|Proverbs|"
    "Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|"
    "Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    "Matthew|Mark|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|"
    "Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|"
    "Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation".split("|"),
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO "
    "ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL "
    "MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM "
    "HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV".split(),
    strict=True,
))
BIBLE_BOOKS["Psalm"] = "PSA"

# Public-domain Bible editions; Quran provider permits republication with translator credit.
# Hadith editions are deliberately excluded until redistribution rights are established.
EDITIONS = {
    ("bible", "en"): ("engwebp", "World English Bible - eBible.org", "https://ebible.org/engwebp/"),
    ("bible", "fr"): ("fraLSG", "Louis Segond (1910) - eBible.org", "https://ebible.org/fraLSG/"),
    ("quran", "en"): ("en.pickthall", "Marmaduke Pickthall - Al Quran Cloud", "https://alquran.cloud/quran/en.pickthall"),
    ("quran", "fr"): ("fr.hamidullah", "Muhammad Hamidullah - Al Quran Cloud", "https://alquran.cloud/quran/fr.hamidullah"),
}


def download(url):
    """Fetch a complete edition with bounded retries and response size."""
    for attempt in range(2):
        try:
            request = Request(url, headers={"User-Agent": "Unholy-Index/1.0 (text import)"})
            with urlopen(request, timeout=30) as response:
                data = response.read(40_000_001)
            if len(data) > 40_000_000:
                raise ValueError("Edition exceeds download limit")
            return data
        except (OSError, ValueError):
            if attempt:
                raise
            time.sleep(2)


def parse_bible(raw):
    """Read eBible's verse-per-line archive, using explicit USFM verse IDs."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        candidates = [name for name in archive.namelist() if name.lower().endswith((".txt", ".vpl"))]
        for name in sorted(candidates, key=lambda n: ("vpl" not in n.lower(), n)):
            if archive.getinfo(name).file_size > 30_000_000:
                continue
            lines = archive.read(name).decode("utf-8-sig").splitlines()
            index = {}
            for line in lines:
                match = re.fullmatch(r"([A-Za-z0-9]{3})\s+(\d+):(\d+)\s+(.+)", line)
                if match:
                    book, chapter, verse, text = match.groups()
                    key = (book.upper(), int(chapter), int(verse))
                    if key in index:
                        raise ValueError(f"Duplicate Bible verse: {key}")
                    index[key] = text
            if len(index) > 25_000 and ("GEN", 1, 1) in index:
                return index
    raise ValueError("No recognized complete verse-per-line Bible file")


def parse_quran(raw, edition):
    """Validate the edition and explicit surah/ayah identifiers."""
    data = json.loads(raw)["data"]
    if data["edition"]["identifier"] != edition or len(data["surahs"]) != 114:
        raise ValueError("Unexpected Quran edition")
    index = {}
    for surah in data["surahs"]:
        chapter = surah["number"]
        for ayah in surah["ayahs"]:
            key = (chapter, ayah["numberInSurah"])
            text = ayah["text"]
            if key in index or not isinstance(text, str) or not text.strip():
                raise ValueError(f"Invalid Quran verse: {key}")
            index[key] = text
    if len(index) != 6236:
        raise ValueError("Incomplete Quran edition")
    return index


def passage_key(entry):
    return json.dumps(
        [entry["religion"], entry["collection"], entry["reference"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def select_verses(entry, index):
    """Return a complete range only; never display partial or fabricated verses."""
    verses = []
    book = BIBLE_BOOKS.get(entry["book"])
    if entry["kind"] == "bible" and not book:
        return None
    for chapter, start, end in entry["ranges"]:
        for verse in range(start, end + 1):
            key = (book, chapter, verse) if entry["kind"] == "bible" else (chapter, verse)
            text = index.get(key)
            if not isinstance(text, str) or not text.strip():
                return None
            verses.append({"number": f"{chapter}:{verse}", "text": text})
    return verses or None


def generate(entries):
    """Import available licensed editions and retain only indexed passages."""
    records = {}
    for (kind, language), (edition, title, source) in EDITIONS.items():
        relevant = [entry for entry in entries if entry["kind"] == kind and entry.get("ranges")]
        if not relevant:
            continue
        try:
            if kind == "bible":
                raw = download(f"https://ebible.org/Scriptures/{edition}_vpl.zip")
                index = parse_bible(raw)
            else:
                raw = download(f"https://api.alquran.cloud/v1/quran/{edition}")
                index = parse_quran(raw, edition)
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
            print(f"Warning: {edition} unavailable: {exc}", flush=True)
            continue
        count = 0
        for entry in relevant:
            verses = select_verses(entry, index)
            if verses is None:
                print(f"Warning: {edition} missing {entry['reference']}", flush=True)
                continue
            records.setdefault(passage_key(entry), {})[language] = {
                "edition": title,
                "language": language,
                "source": source,
                "verses": verses,
            }
            count += 1
        print(f"Imported {count}/{len(relevant)} entries from {edition}", flush=True)
    return records


def main():
    entries = build()
    records = generate(entries)
    # Preserve previously imported records if a provider is temporarily unavailable.
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
            valid = {passage_key(entry) for entry in entries if entry["kind"] in ("bible", "quran")}
            for key in valid:
                for language, result in previous.get(key, {}).items():
                    if language in ("en", "fr") and isinstance(result, dict):
                        records.setdefault(key, {}).setdefault(language, result)
        except (OSError, ValueError, AttributeError, TypeError):
            print("Warning: previous text cache could not be read", flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(records, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Saved local texts for {len(records)} distinct references to {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
