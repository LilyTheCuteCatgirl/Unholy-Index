"""Build the site's JSON database from books/<religion>/**/*.md."""
import collections
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent
BOOKS = ROOT / 'books'
OUTPUT = ROOT / 'generated' / 'entries.json'
ALIASES = {
    'Children and marriage': ["Children's rights", 'Sexual slavery, forced marriage and sexual violence'],
    'Slavery and sexual slavery': ['Slavery', 'Sexual slavery, forced marriage and sexual violence'],
    'Sexual slavery and forced marriage': ['Sexual slavery, forced marriage and sexual violence'],
    'Genocide and mass killing': ['Warfare and mass killing'],
    'Warfare': ['Warfare and mass killing'],
    'Other restrictions and unequal privileges': ['Other discriminatory rules'],
}
SUNNI = {'Sahih al-Bukhari':'bukhari', 'Sahih Muslim':'muslim', 'Sunan Abi Dawud':'abudawud', "Sunan an-Nasa'i":'nasai', 'Jami at-Tirmidhi':'tirmidhi', 'Sunan Ibn Majah':'ibnmajah'}
SHIA = {
    'Chapter on the Punishment for Apostasy':'https://shialibrary.com/book/kafi/chapter/528556',
    'Chapter on the Punishment for Sodomy':'https://shialibrary.com/book/kafi/chapter/528516',
    'Chapter on the Punishment for Lesbianism':'https://shialibrary.com/book/kafi/chapter/528518',
    'chapter 96, hadith 2':'https://thaqalayn.com/hadith/5/2/96/2',
    "A Woman's Marriage with Her Slave":'https://shialibrary.com/book/kafi/chapter/626307',
    'Al-Khisal 10-27':'https://thaqalayn.net/chapter/10/11/20',
}

def display_name(name):
    return re.sub(r'[-_]+', ' ', name).title()

def enrich(entry, kind):
    """Known reference formats get automatic source links. Others stay generic."""
    ref = entry['reference']
    if kind == 'bible':
        match = re.fullmatch(r'(.+?) (\d+):(\d+)(?:-(\d+))?', ref)
        if not match:
            return
        book, chapter, start, end = match.groups()
        entry.update(kind=kind, book=book, ranges=[[int(chapter), int(start), int(end or start)]])
        entry['sources'] = [
            ['Bible Gateway · NRSVUE', 'https://www.biblegateway.com/passage/?search='+quote(ref)+'&version=NRSVUE'],
            ['Bible Gateway · WEB', 'https://www.biblegateway.com/passage/?search='+quote(ref)+'&version=WEB'],
            ['Bible API · WEB', 'https://bible-api.com/'+quote(ref)+'?translation=web'],
        ]
    elif kind == 'quran':
        match = re.fullmatch(r'(.+) \(([^()]+)\)', ref)
        if not match:
            return
        name, raw = match.groups()
        ranges = []
        for segment in raw.split(','):
            m = re.fullmatch(r'(\d+):(\d+)(?:-(\d+))?', segment.strip())
            if not m:
                return
            c, a, b = m.groups()
            ranges.append([int(c), int(a), int(b or a)])
        entry.update(kind=kind, book=name, ranges=ranges)
        for c,a,b in ranges:
            entry['sources'].extend([
                [f'Quran.com · {c}:{a}'+(f'–{b}' if a!=b else ''),f'https://quran.com/{c}/{a}'+(f'-{b}' if a!=b else '')],
                [f'Arabic Corpus · {c}:{a} (compare translations)',f'https://corpus.quran.com/translation.jsp?chapter={c}&verse={a}'],
            ])
    elif kind == 'hadith':
        entry['kind'] = kind
        for book, slug in SUNNI.items():
            m = re.match(re.escape(book)+r' (\d+[a-z]?)\b', ref)
            if not m:
                continue
            num = m.group(1)
            entry.update(book=book, hadithNumber=num, slug=slug)
            entry['sources'] = [['Sunnah.com · full narration', f'https://sunnah.com/{slug}:{num}']]
            # Preserve the previous loader's supported editions; other editions use direct links.
            if slug in {'bukhari','abudawud','nasai'} and num.isdigit():
                entry['hadithAPI'] = f'https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/eng-{slug}/{num}.json'
                entry['sources'].append(['Hadith API · alternate edition',entry['hadithAPI']])
            return
        if ref.startswith(('Al-Kafi','Al-Khisal')):
            entry['book'] = 'Al-Kafi' if ref.startswith('Al-Kafi') else 'Al-Khisal'
            for key,url in SHIA.items():
                if key in ref:
                    entry['sources'] = [['Shia Library · chapter' if 'shialibrary' in url else 'Thaqalayn · reference',url]]
                    break

def translations_for(rel, warnings):
    """Match translations by original heading and reference, never line number."""
    result = {}
    for directory in sorted((ROOT / 'translations').glob('*')):
        path = directory / rel
        if not path.is_file():
            continue
        language = directory.name
        theme = 'Uncategorized'
        for lineno, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            line = raw.strip()
            heading = re.fullmatch(r'#{1,6}\s+(.+)', line)
            if heading:
                theme = heading.group(1).strip()
            elif line.startswith('- ') and ' - ' in line[2:]:
                ref, summary = line[2:].split(' - ', 1)
                key = (theme, ref.strip())
                if key in result and language in result[key]:
                    warnings.append(f'{path}:{lineno}: duplicate translation for {key!r}')
                if summary.strip():
                    result.setdefault(key, {})[language] = summary.strip()
    return result

def build():
    entries = []
    warnings = []
    # A religion is simply a folder; no central registry is required.
    paths = sorted(BOOKS.glob('*/**/*.md'), key=lambda p: (p.relative_to(BOOKS).parts[0], {'bible':0,'quran':0,'hadith':1}.get(p.stem.lower(),2),p.as_posix()))
    for path in paths:
        rel = path.relative_to(BOOKS)
        religion = display_name(rel.parts[0])
        translations = translations_for(rel, warnings)
        kind = path.stem.lower()
        collection = {'bible':'Bible','quran':'Quran','hadith':'Hadith'}.get(kind,display_name(path.stem))
        theme = 'Uncategorized'
        for lineno, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
            line = raw.strip()
            heading = re.fullmatch(r'#{1,6}\s+(.+)',line)
            if heading:
                theme = heading.group(1).strip()
                continue
            if not line.startswith('- '):
                continue
            if ' - ' not in line[2:]:
                warnings.append(f'{rel}:{lineno}: skipped bullet without reference - summary')
                continue
            ref, description = line[2:].split(' - ',1)
            # Optional inline sources: summary | https://example.org/passage | https://...
            parts = [s.strip() for s in description.split(' | ')]
            summary, manual = parts[0], parts[1:]
            ref = ref.strip()
            if not ref or not summary:
                warnings.append(f'{rel}:{lineno}: skipped empty reference or summary')
                continue
            tradition, category = '', theme
            if kind=='hadith' and ' - ' in theme:
                tradition, category = theme.split(' - ',1)
            entry = dict(id=f'{rel.as_posix()}:{lineno}', kind='generic', religion=religion,
                collection=collection, book=collection, reference=ref, summary=summary,
                themes=ALIASES.get(category,[category]), originalTheme=theme, tradition=tradition, sources=[])
            enrich(entry,kind)
            if (theme, ref) in translations:
                entry['translations'] = translations[(theme, ref)]
            for url in manual:
                try:
                    parsed=urlsplit(url)
                    if parsed.scheme not in ('https','http') or not parsed.hostname:
                        raise ValueError('not an HTTP(S) URL')
                except ValueError:
                    warnings.append(f'{rel}:{lineno}: invalid source URL {url!r}')
                    continue
                if url not in [s[1] for s in entry['sources']]:
                    entry['sources'].append([parsed.hostname,url])
            if not entry['sources'] and kind in {'bible','quran','hadith'}:
                warnings.append(f'{rel}:{lineno}: no automatic source for {ref!r}; add an explicit URL')
            entries.append(entry)
    if not entries:
        raise SystemExit('No entries found. Add Markdown files inside books/<religion>/.')
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(OUTPUT)
    print(f'Built {len(entries)} entries from {len(paths)} Markdown files: {dict(collections.Counter(e["religion"] for e in entries))}',flush=True)
    for warning in warnings:
        print('Warning:',warning,flush=True)
    return entries

if __name__=='__main__':
    build()
