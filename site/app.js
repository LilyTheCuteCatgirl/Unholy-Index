let DATA = [];
const $ = id => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls)
    n.className = cls;
  if (text !== undefined)
    n.textContent = text;
  return n;
};
const cache = new Map();
const sorted = values => [...new Set(values)].sort((a, b) => a.localeCompare(b));
function option(value, label) {
  const o = el('option', '', label);
  o.value = value;
  return o;
}
const religionBase = () => DATA.filter(e => !$('religion').value || e.religion === $('religion').value);
const collectionKey = e => JSON.stringify([e.religion, e.collection]);
const bookKey = e => JSON.stringify([e.religion, e.collection, e.book]);
const bookBase = () => religionBase().filter(e => !$('book').value || collectionKey(e) === $('book').value || bookKey(e) === $('book').value);
function updateBooks() {
  const previous = $('book').value, select = $('book');
  select.replaceChildren(option('', tr('All books')));
  const groups = new Map();
  for (const e of religionBase()) {
    const key = collectionKey(e);
    if (!groups.has(key))
      groups.set(key, []);
    groups.get(key).push(e);
  }
  for (const [key, entries] of groups) {
    const e = entries[0], group = el('optgroup');
    group.label = ($('religion').value ? '' : tr(e.religion) + ' - ') + tr(e.collection);
    group.append(option(key, tr('All ' + e.collection)));
    for (const b of sorted(entries.map(x => x.book)))
      group.append(option(JSON.stringify([e.religion, e.collection, b]), tr(b)));
    select.append(group);
  }
  select.value = [...select.options].some(o => o.value === previous) ? previous : '';
}
function updateThemes() {
  const previous = $('theme').value, select = $('theme');
  select.replaceChildren(option('', tr('All themes')), ...sorted(bookBase().flatMap(e => e.themes)).map(t => option(t, tr(t))));
  select.value = [...select.options].some(o => o.value === previous) ? previous : '';
}
const drawer = $('drawer');
$('menu').onclick = () => {
  if (!drawer.open) {
    drawer.showModal();
    $('menu').setAttribute('aria-expanded', 'true');
  }
};
$('close-menu').onclick = () => drawer.close();
drawer.addEventListener('close', () => {
  $('menu').setAttribute('aria-expanded', 'false');
  $('menu').focus();
});
drawer.addEventListener('click', event => {
  if (event.target !== drawer)
    return;
  const r = drawer.getBoundingClientRect();
  if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)
    drawer.close();
});
function link(label, url) {
  let a = el('a', '', label + '');
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}
async function getJSON(url) {
  if (cache.has(url))
    return cache.get(url);
  let promise = (async () => {
    let r = await fetch(url, { signal: AbortSignal.timeout(12000), credentials: 'omit' });
    if (!r.ok)
      throw Error('HTTP ' + r.status);
    return r.json();
  })();
  cache.set(url, promise);
  try {
    return await promise;
  }
  catch (e) {
    cache.delete(url);
    throw e;
  }
}
const BIBLE_BOOKS = [
  'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua',
  'Judges', 'Ruth', '1 Samuel', '2 Samuel', '1 Kings', '2 Kings',
  '1 Chronicles', '2 Chronicles', 'Ezra', 'Nehemiah', 'Esther', 'Job',
  'Psalms', 'Proverbs', 'Ecclesiastes', 'Song of Solomon', 'Isaiah',
  'Jeremiah', 'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel',
  'Amos', 'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah',
  'Haggai', 'Zechariah', 'Malachi', 'Matthew', 'Mark', 'Luke', 'John',
  'Acts', 'Romans', '1 Corinthians', '2 Corinthians', 'Galatians',
  'Ephesians', 'Philippians', 'Colossians', '1 Thessalonians',
  '2 Thessalonians', '1 Timothy', '2 Timothy', 'Titus', 'Philemon',
  'Hebrews', 'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John',
  'Jude', 'Revelation',
];

function frenchBibleURL(e, chapter = e.ranges?.[0]?.[0]) {
  const name = e.book === 'Psalm' ? 'Psalms' : e.book;
  const book = BIBLE_BOOKS.indexOf(name) + 1;
  if (!book || !e.ranges?.length)
    return null;
  return `https://api.getbible.net/v2/ls1910/${book}/${chapter}.json`;
}

function frenchHadithURL(e) {
  // Keep the existing conservative numbering restrictions from the builder.
  if (!e.hadithAPI || !['bukhari', 'abudawud', 'nasai'].includes(e.slug))
    return null;
  return e.hadithAPI.replace('/eng-', '/fra-');
}

function formatBibleVerses(verses, chapter, start, end) {
  if (!Array.isArray(verses) || verses.length !== end - start + 1 ||
      verses.some((v, i) => v.chapter !== chapter || v.verse !== start + i ||
        typeof v.text !== 'string' || !v.text.trim()))
    throw Error('Incomplete or mismatched verse range');
  return verses.map(v => ({
    number: `${v.chapter}:${v.verse}`,
    text: v.text.trim(),
  }));
}

async function readBible(e, language) {
  const verses = [];
  let edition = language === 'fr' ? 'Louis Segond (1910) - GetBible' : 'World English Bible';
  for (const [chapter, start, end] of e.ranges) {
    if (language === 'fr') {
      const url = frenchBibleURL(e, chapter);
      if (!url)
        throw Error('French Bible reference not supported');
      const data = await getJSON(url);
      const book = BIBLE_BOOKS.indexOf(e.book === 'Psalm' ? 'Psalms' : e.book) + 1;
      if (data.abbreviation !== 'ls1910' || data.lang !== 'fr' ||
          data.book_nr !== book || data.chapter !== chapter)
        throw Error('Mismatched French Bible chapter');
      const selected = data.verses?.filter(v => v.verse >= start && v.verse <= end);
      verses.push(...formatBibleVerses(selected, chapter, start, end));
    } else {
      const span = `${chapter}:${start}${start === end ? '' : `-${end}`}`;
      const url = 'https://bible-api.com/' + encodeURIComponent(`${e.book} ${span}`) + '?translation=web';
      const data = await getJSON(url);
      edition = data.translation_name || edition;
      verses.push(...formatBibleVerses(data.verses, chapter, start, end));
    }
  }
  return { edition, language, verses };
}

async function readHadith(e, url, language) {
  const data = await getJSON(url);
  const number = Number(e.hadithNumber);
  const hadith = data.hadiths?.find(h => Number(h.hadithnumber) === number && Number(h.arabicnumber) === number);
  if (typeof hadith?.text !== 'string' || !hadith.text.trim())
    throw Error('Numbering could not be matched or text missing');
  return {
    edition: tr(language === 'fr' ? 'French hadith edition' : 'English hadith edition'),
    language,
    text: hadith.text,
  };
}

async function readOnline(e, language) {
  if (e.kind === 'bible')
    return readBible(e, language);
  if (e.kind === 'quran') {
    const parts = [];
    for (const [c, a, b] of e.ranges) {
      const edition = language === 'fr' ? 'fr.hamidullah' : 'en.pickthall';
      const data = await getJSON(`https://api.alquran.cloud/v1/surah/${c}/${edition}`);
      const verses = data.data?.ayahs?.filter(v => v.numberInSurah >= a && v.numberInSurah <= b);
      if (data.data?.number !== c || data.data?.edition?.identifier !== edition ||
          !verses || verses.length !== b - a + 1 ||
          verses.some((v, i) => v.numberInSurah !== a + i || typeof v.text !== 'string' || !v.text.trim()))
        throw Error('Incomplete or mismatched verse range');
      parts.push(...verses.map(v => ({
        number: `${c}:${v.numberInSurah}`,
        text: v.text.trim(),
      })));
    }
    return {
      edition: language === 'fr' ? 'Muhammad Hamidullah - Al Quran Cloud' : 'Pickthall - Al Quran Cloud',
      language,
      verses: parts,
    };
  }
  if (e.hadithAPI) {
    if (language === 'fr') {
      const url = frenchHadithURL(e);
      if (url) {
        try {
          return await readHadith(e, url, 'fr');
        }
        catch {
          // An unavailable or mismatched French narration must never be mislabeled.
        }
      }
    }
    return readHadith(e, e.hadithAPI, 'en');
  }
  return null;
}
// Reference-based identity is independent of Markdown line numbers and theme order.
const passageKey = e => JSON.stringify([e.religion, e.collection, e.reference]);
let localTextsPromise;
let localSearchData = {};

function localTexts() {
  localTextsPromise ??= getJSON('./generated/texts.json').catch(() => ({})).then(data => {
    localSearchData = data ?? {};
    return localSearchData;
  });
  return localTextsPromise;
}

async function read(e, language = LANG) {
  if (e.kind === 'bible' || e.kind === 'quran') {
    const database = await localTexts();
    const result = database?.[passageKey(e)]?.[language];
    const expected = (e.ranges ?? []).flatMap(([c, a, b]) =>
      Array.from({ length: b - a + 1 }, (_, i) => `${c}:${a + i}`),
    );
    if (result?.language === language && typeof result.edition === 'string' &&
        /^https:\/\//.test(result.source) && expected.length &&
        Array.isArray(result.verses) && result.verses.length === expected.length &&
        result.verses.every((v, i) => v.number === expected[i] &&
          typeof v.text === 'string' && v.text.trim())) {
      return result;
    }
  }
  return readOnline(e, language);
}

function passageURL(e) {
  const url = new URL(window.location.href);
  url.search = new URLSearchParams({
    religion: e.religion,
    book: e.collection,
    ref: e.reference,
    lang: LANG,
  }).toString();
  url.hash = '';
  return url.href;
}

async function copyText(text) {
  // Clipboard API needs HTTPS; use a selection fallback on local HTTP/LAN.
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Continue with the fallback if clipboard permission was denied.
  }
  const field = el('textarea', 'clipboard-fallback');
  field.value = text;
  field.setAttribute('readonly', '');
  const previous = document.activeElement;
  document.body.append(field);
  field.select();
  field.setSelectionRange(0, text.length);
  let copied = false;
  try {
    copied = document.execCommand('copy');
  } catch {
    // A manual selection dialog remains available on restricted browsers.
  } finally {
    field.remove();
    previous?.focus();
  }
  if (!copied)
    window.prompt(tr('Copy manually:'), text);
  return copied;
}

function passageText(e, result) {
  const text = Array.isArray(result.verses)
    ? result.verses.map(verse => verse.text.trim()).join('\n')
    : result.text.trim();
  return [trRef(e), text, passageURL(e)].join('\n');
}

function displayPassage(target, result) {
  if (!Array.isArray(result.verses)) {
    target.textContent = result.text;
    return;
  }
  target.replaceChildren(...result.verses.map(verse => {
    const line = el('div', 'verse-line');
    line.append(
      el('span', 'verse-number', verse.number),
      el('span', 'verse-text', verse.text),
    );
    return line;
  }));
}

function entry(e) {
  const d = el('details', 'entry');
  d.dataset.passageKey = passageKey(e);
  const s = el('summary');
  s.append(el('strong', '', trRef(e)), el('span', 'description', LANG === 'fr' ? (e.translations?.fr || e.summary) : e.summary));
  if (LANG === 'fr' && !e.translations?.fr)
    s.append(el('span', 'muted', tr('English summary (translation pending)')));
  d.append(s);
  const panel = el('div', 'expanded');
  const edition = el('div', 'muted');
  const verse = el('div', 'verse');
  verse.setAttribute('aria-live', 'polite');
  const sources = el('ul', 'sources');
  const sourceLinks = localizedSources(e);
  for (const [name, url] of sourceLinks) {
    const li = el('li');
    li.append(link(name, url));
    sources.append(li);
  }
  if (!e.sources.length)
    sources.append(el('li', 'muted', tr('No source configured.')));
  const retry = el('button', '', tr('Retry'));
  retry.hidden = true;
  const actions = el('div', 'passage-actions');
  const shareButton = el('button', '', tr('Copy link'));
  const copyButton = el('button', '', tr('Copy passage'));
  copyButton.disabled = true;
  const status = el('span', 'muted');
  status.setAttribute('role', 'status');
  actions.append(shareButton, copyButton, status);
  let currentResult = null;
  shareButton.onclick = async () => {
    status.textContent = await copyText(passageURL(e)) ? tr('Link copied') : '';
  };
  copyButton.onclick = async () => {
    if (!currentResult)
      return;
    const copied = await copyText(passageText(e, currentResult));
    status.textContent = copied ? tr('Passage copied') : '';
  };
  panel.append(edition, verse, el('strong', '', tr('Sources')), sources, retry, actions);
  d.append(panel);
  let loaded = false;
  async function load() {
    loaded = true;
    retry.hidden = true;
    copyButton.disabled = true;
    currentResult = null;
    edition.textContent = '';
    verse.textContent = tr('Loading...');
    try {
      const result = await read(e);
      if (result) {
        currentResult = result;
        if (result.source && !sourceLinks.some(([, url]) => url === result.source)) {
          const localSource = [result.edition, result.source];
          sourceLinks.unshift(localSource);
          const li = el('li');
          li.append(link(...localSource));
          sources.prepend(li);
        }
        edition.textContent = (LANG === 'fr' && result.language === 'en' ? tr('French unavailable; English text shown') + ' - ' : '') + result.edition;
        verse.lang = result.language;
        displayPassage(verse, result);
      }
      else {
        verse.textContent = e.sources.length ? tr('Full text is available at the linked source. Inline text is not configured for this reference.') : tr('Full text and source links have not been added for this reference.');
      }
    }
    catch (err) {
      verse.textContent = tr('Full text unavailable. Use a source link below if available.');
      retry.hidden = false;
    } finally {
      copyButton.disabled = !currentResult;
    }
  }
  retry.onclick = load;
  d.addEventListener('toggle', () => {
    if (d.open && !loaded)
      load();
  });
  return d;
}
// Match both languages, ignoring case, accents and typographic punctuation.
function normalizeSearch(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/[’‘]/g, "'")
    .replace(/[‐‑‒–—−]/g, '-')
    .toLowerCase();
}

function matchesSearch(entry, terms) {
  if (!terms.length)
    return true;
  const categories = [entry.religion, entry.collection, entry.book, ...entry.themes];
  const frenchReference = entry.kind === 'bible'
    ? entry.reference.replace(/^(.+?)(?= \d+:)/, book => FR[book] ?? book)
    : entry.reference;
  const fields = [
    entry.reference,
    frenchReference,
    entry.summary,
    ...Object.values(entry.translations ?? {}),
    ...categories,
    ...categories.map(value => FR[value] ?? value),
    ...Object.values(localSearchData[passageKey(entry)] ?? {}).flatMap(result =>
      result.verses?.map(verse => verse.text) ?? [],
    ),
  ];
  const haystack = normalizeSearch(fields.join(' '));
  return terms.every(term => {
    // A single verse reference also matches a passage containing that verse.
    const match = /^(\d+):(\d+)$/.exec(term);
    if (match && entry.ranges?.length) {
      const chapter = Number(match[1]);
      const verse = Number(match[2]);
      return entry.ranges.some(([c, start, end]) => c === chapter && verse >= start && verse <= end);
    }
    return haystack.includes(term);
  });
}

function render() {
  const theme = $('theme').value;
  const terms = normalizeSearch($('search').value).trim().split(/\s+/).filter(Boolean);
  const items = bookBase().filter(e =>
    (!theme || e.themes.includes(theme)) && matchesSearch(e, terms),
  );
  $('count').textContent = items.length + ' ' + tr(items.length === 1 ? 'entry' : 'entries');
  $('active-filters').textContent = ['religion', 'book', 'theme'].filter(id => $(id).value).map(id => $(id).selectedOptions[0].textContent).join(' / ');
  const target = $('results');
  target.replaceChildren();
  if (!items.length) {
    target.append(el('p', 'muted', tr('No matching passages.')));
    return;
  }
  const religions = new Map();
  for (const e of items) {
    if (!religions.has(e.religion))
      religions.set(e.religion, new Map());
    const collections = religions.get(e.religion), name = e.collection === 'Hadith' && e.tradition ? e.tradition + ' hadith' : e.collection;
    if (!collections.has(name))
      collections.set(name, new Map());
    const books = collections.get(name);
    if (!books.has(e.book))
      books.set(e.book, []);
    books.get(e.book).push(e);
  }
  for (const [religion, collections] of religions) {
    const section = el('section', 'religion-group'), heading = el('div', 'religion-title');
    heading.append(el('h2', '', tr(religion)), el('span', 'muted', items.filter(e => e.religion === religion).length + ' ' + tr(items.filter(e => e.religion === religion).length === 1 ? 'entry' : 'entries')));
    section.append(heading);
    for (const [name, books] of collections) {
      const collection = el('section', 'collection-group');
      collection.append(el('h3', '', tr(name)));
      for (const [book, entries] of books) {
        const group = el('section', 'book-group');
        group.append(el('h4', '', tr(book)), ...entries.map(entry));
        collection.append(group);
      }
      section.append(collection);
    }
    target.append(section);
  }
}
$('religion').onchange = () => {
  updateBooks();
  updateThemes();
  render();
};
$('book').onchange = () => {
  updateThemes();
  render();
};
$('theme').onchange = render;
$('search').addEventListener('input', render);
function localize() {
  document.documentElement.lang = LANG;
  document.querySelectorAll('[data-i18n]').forEach(n => n.textContent = tr(n.dataset.i18n));
  $('menu').setAttribute('aria-label', tr('Open filters'));
  $('search').setAttribute('aria-label', tr('Search passages'));
  $('search').placeholder = tr('Search references or keywords...');
  $('close-menu').setAttribute('aria-label', tr('Close filters'));
  $('footnote').textContent = LANG === 'fr' ? footFR : footEN;
  $('language').value = LANG;
  const previous = $('religion').value;
  $('religion').replaceChildren(option('', tr('All religions')), ...sorted(DATA.map(e => e.religion)).map(r => option(r, tr(r))));
  if ([...$('religion').options].some(o => o.value === previous))
    $('religion').value = previous;
  updateBooks();
  updateThemes();
  render();
}
$('language').onchange = () => {
  LANG = $('language').value;
  try {
    localStorage.setItem('unholy-language', LANG);
  }
  catch {
  }
  localize();
};
async function init() {
  try {
    const response = await fetch('./generated/entries.json', { cache: 'no-store' });
    if (!response.ok)
      throw Error('HTTP ' + response.status);
    DATA = await response.json();
    const params = new URLSearchParams(window.location.search);
    const requestedLanguage = params.get('lang');
    if (requestedLanguage === 'en' || requestedLanguage === 'fr')
      LANG = requestedLanguage;
    localize();
    localTexts().then(() => {
      if ($('search').value.trim())
        render();
    });
    const reference = params.get('ref');
    if (reference) {
      const match = DATA.find(e => e.reference === reference &&
        e.religion === params.get('religion') && e.collection === params.get('book'));
      const target = match && [...$('results').querySelectorAll('details.entry')]
        .find(node => node.dataset.passageKey === passageKey(match));
      if (target) {
        target.open = true;
        requestAnimationFrame(() => target.scrollIntoView({ block: 'start' }));
      } else {
        $('results').prepend(el('p', 'muted', tr('Shared passage not found.')));
      }
    }
  }
  catch (err) {
    $('count').textContent = tr('Could not load entries. Check that the database has been built and the site is served over HTTP.');
  }
}
init();
