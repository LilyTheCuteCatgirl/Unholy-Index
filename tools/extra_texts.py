"""Import explicitly numbered passages from additional collections.

Only known source editions are fetched. Ambiguous or incomplete references are
not cached. Sources/edition labels remain visible in the interface.
"""

import json
import re
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import quote, urlencode


class Blocks(HTMLParser):
    """Extract text paragraphs and headings, omitting footnote markup."""
    tags = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'td', 'li'}

    def __init__(self, html, keep_sup=False):
        super().__init__(convert_charrefs=True)
        self.keep_sup = keep_sup
        self.blocks = []
        self.active = None
        self.parts = []
        self.skip = []
        self.feed(html)
        self.finish()

    def finish(self):
        if self.active:
            text = '\n'.join(' '.join(line.split()) for line in ''.join(self.parts).split('\n') if line.strip())
            if text:
                self.blocks.append((self.active, text))
        self.active = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.append(tag)
            return
        if tag in {'script', 'style', 'nav'} or (tag == 'sup' and not self.keep_sup) or (
            tag in {'span', 'a'} and any(x in attrs.get('class', '').lower()
            for x in ('footnote', 'reference', 'mw-editsection', 'pagenum'))
        ):
            self.skip.append(tag)
            return
        if tag in self.tags:
            self.finish()
            self.active = tag
        elif tag == 'br':
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag == 'sup' and self.keep_sup and self.active:
            self.parts.append(' ')
        if tag == self.active:
            self.finish()

    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(re.sub(r'\s+', ' ', data))


class FirstCells(HTMLParser):
    """The Vendidad's source text is in column one; column two is commentary."""
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.col = 0
        self.active = False
        self.skip = 0
        self.parts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.col = 0
        elif tag == 'td':
            self.col += 1
            self.active = self.col == 1
            self.parts = []
        elif tag == 'sup' and self.active:
            self.skip += 1
        elif tag in ('br', 'p') and self.active:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'sup' and self.skip:
            self.skip -= 1
        elif tag == 'td' and self.active:
            self.cells.append('\n'.join(' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip()))
            self.active = False

    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(re.sub(r'\s+', ' ', data))


def contiguous(blocks, trailing=False):
    """Extract a run starting with verse 1, stopping before notes or other lists."""
    index = {}
    for text in blocks:
        if re.match(r'^(footnotes|notes|references)\b', text, re.I) and index:
            break
        if trailing:
            match = re.fullmatch(r'(.+?)\s*\((\d+)\)', text, re.S)
            if not match:
                continue
            content, number = match.groups()
        else:
            match = re.fullmatch(r'(\d+)\.\s+(.+)', text, re.S)
            if not match:
                continue
            number, content = match.groups()
        number = int(number)
        if number != len(index) + 1:
            if index:
                break
            continue
        if not content.strip():
            break
        index[number] = content.strip()
    return index


def record(index, chapter, start, end, edition, source, language='en'):
    """Store only complete ranges, and at most three neighbors on each side."""
    if not (1 <= start <= end <= start + 1000):
        return None
    if any(not isinstance(index.get(n), str) or not index[n].strip()
           for n in range(start, end + 1)):
        return None
    def verse(n):
        return {'number': f'{chapter}:{n}', 'text': index[n].strip()}
    return {'edition': edition, 'language': language, 'source': source,
            'verses': [verse(n) for n in range(start, end + 1)],
            'context': [verse(n) for n in range(max(1, start - 3), end + 4)
                        if isinstance(index.get(n), str) and index[n].strip()]}


ROMAN = {5: 'v', 8: 'viii', 9: 'ix', 10: 'x'}
GUTENBERG = 'https://www.gutenberg.org/cache/epub/17/pg17-images.html'
GUTENBERG_MIRRORS = (GUTENBERG, 'https://www.gutenberg.org/files/17/17-h/17-h.htm', 'https://www.gutenberg.org/cache/epub/17/pg17.txt')
VINAYA = 'https://obo.genaud.net/dhamma-vinaya/sbe/vp/02.mv/vp.02.mv.01.rdho.sbe.htm'
BILARA = 'https://raw.githubusercontent.com/suttacentral/bilara-data/published/translation/en/sujato/sutta/'
# Only these exact historical translations / chapter sources are enabled.
NUMBERED = {
    'Manusmriti': ('Manusmriti', 'Georg Buhler (1886) - Laws of Manu'),
    'Gautama Dharmasutra': ('Gautama Dharmasutra', 'Georg Buhler (1879) - Gautama Dharmasutra'),
    'Uttaradhyayana Sutra': ('Uttaradhyayana Sutra', 'Hermann Jacobi (1895) - Uttaradhyayana Sutra'),
    'Vendidad': ('Vendidad', 'James Darmesteter (1898 edition) - Vendidad'),
}


def chapter_source(collection, chapter):
    if collection == 'Manusmriti' and chapter in ROMAN:
        return 'https://hinduismfacts.org/hindu-scriptures-and-holy-books/manusmriti/chapter-' + ROMAN[chapter] + '/'
    if collection == 'Gautama Dharmasutra' and chapter in {4, 9, 10, 12, 18, 23}:
        return f'https://www.wisdomlib.org/hinduism/book/gautama-dharmasutra/d/doc{116300 + chapter}.html'
    if collection == 'Uttaradhyayana Sutra' and chapter in {8, 32}:
        return f'https://www.wisdomlib.org/jainism/book/uttaradhyayana-sutra/d/doc{424210 + chapter}.html'
    if collection == 'Vendidad' and chapter in {4, 7, 8, 14, 15, 16, 18}:
        return f'https://www.avesta.org/vendidad/vd{chapter}sbe.htm'
    return None


def decode_html(raw):
    """Historical pages may be Windows-1252 rather than UTF-8."""
    match = re.search(rb'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', raw[:8192], re.I)
    if match:
        encoding = match.group(1).decode('ascii')
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            pass
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252')


def parse_vendidad(html, chapter):
    # First-column cells may contain several verses, continuation paragraphs,
    # and alternate manuscript numbers (e.g. 27 (77).). Ignore note column.
    blocks = Blocks(html).blocks
    if not re.search(rf'\bFargard\s+{chapter}\b', ' '.join(t for _, t in blocks), re.I):
        return {}
    cells = FirstCells(html).cells
    index = {}
    for cell in cells:
        # Continuations must stay in the same source cell; a later cell may
        # be a navigation row or a heading, not part of the preceding verse.
        current = None
        for line in cell.splitlines():
            line = line.strip()
            if not line:
                continue
            # Some editions label an additional paragraph as n (bis). It
            # belongs to the same numbered verse, not to the next verse.
            bis = re.match(r'^(\d+)\s*\(bis\)\.\s*(.*)$', line, re.I)
            if bis and int(bis.group(1)) in index:
                current = int(bis.group(1))
                index[current] += ' (bis) ' + bis.group(2)
                continue
            match = re.match(r'^(\d+)\s*\.?\s*(?:\(\d+\))?\s*\.\s*(.*)$', line)
            if match:
                n, content = int(match.group(1)), match.group(2).strip()
                if n != len(index) + 1:
                    if index:
                        return {k: v for k, v in index.items() if v.strip()}
                    continue
                current = n
                index[n] = content
            elif current is not None:
                # Do not append titles or editorial apparatus to text.
                if re.fullmatch(r'[IVXLCDM]+[a-z]?\.?', line, re.I):
                    continue
                if re.match(r'^(?:FARGARD|NOTES?|FOOTNOTES)\b', line, re.I):
                    return {k: v for k, v in index.items() if v.strip()}
                index[current] += ' ' + line
    return {k: v.strip() for k, v in index.items() if v.strip()}


def french_manu(html, chapter):
    blocks = Blocks(html).blocks
    page = ' '.join(t for _, t in blocks)
    if not re.search(r'\bSTREHLY\b', page, re.I) or not re.search(rf'\bLIVRE\s+{ROMAN[chapter]}\b', page, re.I):
        return {}
    # Remacle reproduces Strehly's numbered 1893 translation. Notes come
    # after the numbered text; contiguous() stops at a numbering reset.
    lines = [line for tag, text in blocks if tag == 'p' for line in text.splitlines()]
    return contiguous(lines)


def parse_numbered(html, collection, chapter=None):
    if collection == 'Vendidad':
        return parse_vendidad(html, chapter)
    blocks = Blocks(html).blocks
    if chapter is not None:
        headings = ' '.join(text for tag, text in blocks if tag.startswith('h'))
        if collection == 'Gautama Dharmasutra':
            roman = {4: 'IV', 9: 'IX', 10: 'X', 12: 'XII', 18: 'XVIII', 23: 'XXIII'}[chapter]
            if not re.search(rf'\bChapter\s+{roman}\b', headings, re.I):
                return {}
        elif not re.search(rf'\bChapter\s+(?:{chapter}|{ROMAN.get(chapter, chapter)})\b', headings, re.I):
            return {}
    # Only verse paragraphs, never navigation, chapter introductions or notes.
    text = [line for tag, s in blocks if tag == 'p' or re.match(r'^footnotes\b', s, re.I) for line in s.splitlines()]
    if collection == 'Uttaradhyayana Sutra':
        # Jacobi numbers each verse at the end, sometimes several in a paragraph.
        split = []
        for paragraph in text:
            if re.match(r'^footnotes\b', paragraph, re.I):
                break
            offset = 0
            for marker in re.finditer(r'\((\d+)\)(?=\s|$)', paragraph):
                split.append(paragraph[offset:marker.end()].strip())
                offset = marker.end()
        return contiguous(split, trailing=True)
    return contiguous(text)


def parse_mormon(raw, book, chapter):
    """Read explicitly headed chapters and contiguous verses from Gutenberg #17."""
    target = f'{book} Chapter {chapter}'
    found = False
    index = {}
    for tag, text in Blocks(raw).blocks:
        if tag.startswith('h'):
            if found:
                break
            found = text.casefold() == target.casefold()
            continue
        if not found or tag != 'p':
            continue
        match = re.fullmatch(rf'(?:{re.escape(book)}\s+)?{chapter}:(\d+)\s+(.+)', text, re.S)
        if not match:
            # Gutenberg sometimes splits long verses across several paragraphs.
            if index:
                index[len(index)] += '\n' + text
            continue
        number, content = int(match.group(1)), match.group(2)
        if number != len(index) + 1:
            raise ValueError('Non-contiguous Book of Mormon verse numbering')
        index[number] = content
    return index


def parse_mormon_plain(raw, book, chapter):
    # Gutenberg's plain-text export uses the same explicit chapter headings
    # and verse IDs as the HTML edition. Never infer verse numbering.
    target = f'{book} Chapter {chapter}'
    found = False
    index = {}
    for line in raw.splitlines():
        line = line.strip()
        if line.casefold() == target.casefold():
            found = True
            continue
        if not found or not line:
            continue
        if re.fullmatch(r'(?:[1-4] )?[A-Za-z]+ Chapter \d+', line, re.I) or line.startswith('*** END OF'):
            break
        if re.match(r'^(?:THE |FIRST |SECOND |THIRD |FOURTH )?[A-Z ]*BOOK OF ', line):
            break
        match = re.match(rf'^{chapter}:(\d+)\s+(.+)', line)
        if match:
            n = int(match.group(1))
            if n != len(index) + 1:
                break
            index[n] = match.group(2)
        elif index:
            if re.match(r'^\d+:\d+\b', line):
                break
            index[len(index)] += ' ' + line
    return index


def mormon_record(fetch, book, chapter, start, end):
    for url in GUTENBERG_MIRRORS:
        try:
            raw = decode_html(fetch(url))
            index = parse_mormon_plain(raw, book, chapter) if url.endswith('.txt') else parse_mormon(raw, book, chapter)
            data = record(index, chapter, start, end, 'Book of Mormon - historical English text (Project Gutenberg #17)', 'https://www.gutenberg.org/ebooks/17')
            if data:
                return data
        except (OSError, ValueError, UnicodeError):
            continue
    return None


def sefaria(download, entry, lang):
    match = re.fullmatch(r'(Mishnah .+?|Mishneh Torah, .+?) (\d+)(?::(\d+)(?:-(\d+))?)?', entry['reference'])
    if not match:
        return None
    title, chapter, start, end = match.groups()
    tref = f'{title} {chapter}'
    versions = ['english', 'english|Sefaria Community Translation', 'english|Mishnah Yomit by Dr. Joshua Kulp', 'english|Laws of Kings and Wars. trans. Reuven Brauner, 2012'] if lang == 'en' else ['french']
    # Preserve the previously working request, then try all editions separately.
    for requested in (versions, ['all']):
        query = urlencode({'version': requested, 'fill_in_missing_segments': '0', 'return_format': 'text_only'}, doseq=True)
        url = 'https://www.sefaria.org/api/v3/texts/' + quote(tref, safe='') + '?' + query
        try:
            data = json.loads(download(url))
        except (OSError, ValueError):
            continue
        normalize = lambda s: re.sub(r'[_.:\s]+', ' ', s).strip().casefold()
        if normalize(data.get('ref', '')) != normalize(tref):
            continue
        for v in data.get('versions', []):
            license = v.get('license', '')
            # Avoid restrictive/unknown licenses and mixed translations.
            if license not in {'Public Domain', 'CC0', 'CC-BY', 'CC BY 4.0'}:
                continue
            if v.get('actualLanguage') != lang or not v.get('versionTitle'):
                continue
            text = v.get('text')
            if not isinstance(text, list) or not text or not all(isinstance(x, str) for x in text):
                continue
            source = 'https://www.sefaria.org/' + quote(tref.replace(' ', '_'), safe=',_') + '?' + urlencode({'ven' if lang == 'en' else 'vside': ('english|' if lang == 'en' else 'french|') + v['versionTitle']})
            edition = f"{v['versionTitle']} - Sefaria ({license})"
            result = record(dict(enumerate(text, 1)), int(chapter), int(start or 1),
                            int(end or start or len(text)), edition, source, lang)
            if result:
                # Preserve version and license metadata for attribution.
                result['license'] = license
                result['versionSource'] = v.get('versionSource', '')
                if license == 'CC BY 4.0':
                    result['licenseURL'] = 'https://creativecommons.org/licenses/by/4.0/'
                elif license == 'CC-BY':
                    result['licenseURL'] = 'https://help.sefaria.org/hc/en-us/articles/18490043237148-How-to-Find-and-Understand-Licensing-or-Copyright-Information'
                elif license == 'CC0':
                    result['licenseURL'] = 'https://creativecommons.org/publicdomain/zero/1.0/'
                return result
    return None


def sutta(download, reference):
    match = re.fullmatch(r'(Anguttara Nikaya|Majjhima Nikaya) (\d+)(?:\.(\d+)(?:-(\d+))?)?', reference)
    if not match:
        return None
    name, first, second, last = match.groups()
    if name == 'Anguttara Nikaya' and second:
        uids = [f'an{first}.{n}' for n in range(int(second), int(last or second)+1)]
        folder = f'an/an{first}/'
    elif name == 'Majjhima Nikaya' and not second:
        uids, folder = ['mn'+first], 'mn/'
    else:
        return None
    verses = []
    for uid in uids:
        url = BILARA + folder + uid + '_translation-en-sujato.json'
        data = json.loads(download(url))
        if not isinstance(data, dict) or not data or any(not k.startswith(uid + ':') or not isinstance(v, str) for k, v in data.items()):
            return None
        # Bilara's 0.* segments are titles; retain only the actual discourse.
        groups = {}
        for k, v in data.items():
            section = k.split(':', 1)[1].split('.', 1)[0]
            if section != '0' and v.strip():
                groups.setdefault(section, []).append(v.strip())
        if not groups:
            return None
        verses.extend({'number': f'{uid}:{section}', 'text': ' '.join(parts)} for section, parts in groups.items())
    return {'language': 'en', 'edition': 'Bhikkhu Sujato - SuttaCentral (CC0)',
            'source': f'https://suttacentral.net/{uids[0]}/en/sujato', 'verses': verses}



def vinaya(download, reference):
    """Use the Rhys Davids/Oldenberg 1881 edition with its older numbering.

    Sections 61 and 68 abbreviate repetitions in the published edition; the
    edition label explicitly notes this. Never expand an abbreviation ourselves.
    """
    match = re.fullmatch(r'Mahavagga I\.(\d+)(?:\.(\d+))?', reference)
    if not match:
        return None
    chapter, part = map(int, (match.group(1), match.group(2) or 1))
    if (chapter, part) not in {(39, 7), (46, 1), (47, 1), (61, 2), (62, 3), (68, 1)}:
        return None
    blocks = Blocks(download(VINAYA).decode('utf-8', errors='replace')).blocks
    found = False
    paragraphs = []
    for tag, value in blocks:
        if tag.startswith('h') and re.fullmatch(r'\d+\.?', value):
            if found:
                break
            found = int(value.rstrip('.')) == chapter
        elif found and tag == 'p':
            paragraphs.append(value)
    if not paragraphs:
        return None
    if chapter == 61:
        # The source combines subsections 1 and 2; cannot isolate 61.2 reliably.
        return None
    if chapter in {39, 62}:
        index = {}
        current = None
        for paragraph in paragraphs:
            numbered = re.match(r'^(\d+)\.\s+(.+)', paragraph)
            if numbered:
                current = int(numbered.group(1))
                if current in index:
                    return None
                index[current] = numbered.group(2)
            elif current:
                index[current] += '\n' + paragraph
        return record(index, chapter, part, part, 'Rhys Davids and Oldenberg (1881) - Vinaya Texts (abbreviations retained)', VINAYA)
    # These chapters are unnumbered in the historical edition. Label the whole
    # section rather than claiming that the entire section is subsection 2.
    return {'language': 'en', 'edition': 'Rhys Davids and Oldenberg (1881) - Vinaya Texts (whole section; abbreviations retained)',
            'source': VINAYA, 'verses': [{'number': f'I.{chapter}', 'text': '\n'.join(paragraphs)}]}


def doctrine(download, reference):
    """Historical text on Wikisource; its edition is explicitly unsourced."""
    match = re.fullmatch(r'Doctrine and Covenants (\d+):(\d+)(?:-(\d+))?', reference)
    if not match:
        return None
    chapter, start, end = map(int, (match.group(1), match.group(2), match.group(3) or match.group(2)))
    if chapter not in {64, 84, 132}:
        return None
    url = f'https://en.wikisource.org/wiki/The_Doctrine_and_Covenants/Section_{chapter}'
    blocks = Blocks(download(url).decode('utf-8', errors='replace'), keep_sup=True).blocks
    index = {}
    for tag, value in blocks:
        if tag != 'p':
            continue
        match = re.fullmatch(r'(\d+)\.?\s+(.+)', value, re.S)
        if not match:
            continue
        n, text = int(match.group(1)), match.group(2)
        if n != len(index) + 1:
            if index:
                break
            continue
        index[n] = text
    data = record(index, chapter, start, end, 'Doctrine and Covenants - Wikisource (edition unsourced; compare official text)', url)
    if data:
        data['licenseURL'] = 'https://creativecommons.org/licenses/by-sa/4.0/'
    return data

def import_extra(entries, download, key):
    """Best-effort imports. No network error can prevent existing texts building."""
    failed = {}

    @lru_cache(maxsize=64)
    def fetch(url):
        if url in failed:
            raise ValueError(failed[url])
        try:
            return download(url)
        except (OSError, ValueError) as exc:
            failed[url] = str(exc)
            raise

    @lru_cache(maxsize=32)
    def chapter_index(collection, chapter, url):
        return parse_numbered(decode_html(fetch(url)), collection, chapter)

    @lru_cache(maxsize=8)
    def french_index(chapter, url):
        return french_manu(decode_html(fetch(url)), chapter)

    result = {}
    counts = {}
    for entry in entries:
        if entry['kind'] != 'generic':
            continue
        collection, ref = entry['collection'], entry['reference']
        if collection not in NUMBERED and collection not in {'Mishnah', 'Mishneh Torah', 'Sutta Pitaka', 'Book Of Mormon', 'Vinaya Pitaka', 'Doctrine And Covenants'}:
            continue
        langs = ('fr', 'en') if collection in {'Mishnah', 'Mishneh Torah', 'Manusmriti'} else ('en',)
        for lang in langs:
            if (collection, lang) not in counts:
                print(f'Importing {collection} ({lang})...', flush=True)
            counts.setdefault((collection, lang), [0, 0])[1] += 1
            try:
                data = None
                if collection in NUMBERED:
                    prefix, edition = NUMBERED[collection]
                    match = re.fullmatch(re.escape(prefix) + r' (\d+)\.(\d+)(?:-(\d+))?', ref)
                    if match:
                        chapter, start, end = match.groups()
                        chapter, start, end = int(chapter), int(start), int(end or start)
                        if lang == 'fr' and collection == 'Manusmriti' and chapter in ROMAN:
                            url = f'https://remacle.org/bloodwolf/philosophes/manou/livre{chapter}.htm'
                            index = french_index(chapter, url)
                            data = record(index, chapter, start, end, 'Georges Strehly (1893) - Lois de Manou', url, 'fr')
                        else:
                            url = chapter_source(collection, chapter)
                            if url:
                                data = record(chapter_index(collection, chapter, url), chapter, start, end, edition, url)
                elif collection in {'Mishnah', 'Mishneh Torah'}:
                    data = sefaria(fetch, entry, lang)
                elif collection == 'Sutta Pitaka':
                    data = sutta(fetch, ref)
                elif collection == 'Vinaya Pitaka':
                    data = vinaya(fetch, ref)
                elif collection == 'Doctrine And Covenants':
                    data = doctrine(fetch, ref)
                elif collection == 'Book Of Mormon':
                    match = re.fullmatch(r'((?:[1-4] )?[A-Za-z]+) (\d+):(\d+)(?:-(\d+))?', ref)
                    if match:
                        book, chapter, start, end = match.groups()
                        chapter, start, end = int(chapter), int(start), int(end or start)
                        data = mormon_record(fetch, book, chapter, start, end)
                if data:
                    result.setdefault(key(entry), {})[lang] = data
                    counts[(collection, lang)][0] += 1
                else:
                    print(f'Warning: no verified {lang} text for {ref}', flush=True)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                print(f'Warning: {ref} ({lang}): {exc}', flush=True)
    for (collection, lang), (ok, total) in sorted(counts.items()):
        print(f'Imported {ok}/{total} entries from {collection} ({lang})', flush=True)
    return result
