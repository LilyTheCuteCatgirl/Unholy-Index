"""Bundled English LDS text excerpts and explicitly unofficial French translations.

These excerpts are stored outside generated/ so deployments do not depend on
third-party HTML or network availability. See tools/data/README.md for sources.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data' / 'lds_passages.tsv'
BOM = 'Book Of Mormon'
DC = 'Doctrine And Covenants'


def read_lds(key, entries):
    """Validate exact reference, consecutive verse numbers and language coverage."""
    groups = defaultdict(lambda: {'en': [], 'fr': []})
    with DATA.open(encoding='utf-8', newline='') as stream:
        for ref, number, en, fr in csv.reader((line for line in stream if not line.startswith('#')), delimiter='\t', quoting=csv.QUOTE_NONE):
            if not en.strip() or not fr.strip():
                raise ValueError(f'Empty LDS text: {ref} {number}')
            for language, text in [('en', en), ('fr', fr)]:
                groups[ref][language].append({'number': number, 'text': text})
    records = {}
    for e in entries:
        if e['religion'] != 'Christianity' or e['collection'] not in {BOM, DC}:
            continue
        ref = e['reference']
        if ref not in groups:
            continue  # Newly indexed entries still use the ordinary importer.
        book, chapter, start, end = re.fullmatch(r'(.+) (\d+):(\d+)(?:-(\d+))?', ref).groups()
        expected = [f'{chapter}:{n}' for n in range(int(start), int(end or start) + 1)]
        result = groups[ref]
        for language in ('en', 'fr'):
            if [v['number'] for v in result[language]] != expected:
                raise ValueError(f'Incorrect or incomplete bundled range: {ref} ({language})')
        if e['collection'] == BOM:
            slug = book.lower().replace(' ', '-')
            source = f'https://github.com/jonnyjackson26/bom-editions/blob/main/public/data/en/1920/{slug}/{chapter}.json'
            edition = 'Book of Mormon (1920) - BYU OpenScripture / Book of Mormon Editions Project'
            fr_edition = 'Livre de Mormon - traduction française non officielle de l\'édition anglaise de 1920 (assistée par IA, non révisée)'
            version_source = 'https://github.com/BYU-ODH/OpenScripture'
        else:
            source = 'https://github.com/bcbooks/scriptures-json/blob/master/reference/doctrine-and-covenants-reference.json'
            edition = 'Doctrine and Covenants - Ben Crowder public-domain text dataset (2013 base text)'
            fr_edition = 'Doctrine et Alliances - traduction française non officielle du texte anglais de Ben Crowder (assistée par IA, non révisée)'
            version_source = 'https://bencrowder.net/scriptures-in-json/'
        # The bundled source is an excerpt, not a full chapter. Do not invent
        # neighboring verses. The full official chapter remains linked.
        records[key(e)] = {
            lang: {'language': lang, 'edition': edition if lang == 'en' else fr_edition,
                   'source': source, 'versionSource': version_source,
                   'verses': result[lang]}
            for lang in ('en', 'fr')
        }
    print(f'Loaded bundled LDS texts: {len(records)} references (EN and FR)', flush=True)
    return records
