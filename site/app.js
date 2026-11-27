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
async function read(e) {
  const language = LANG;
  if (e.kind === 'bible') {
    let d = await getJSON('https://bible-api.com/' + encodeURIComponent(e.reference) + '?translation=web');
    let [c, a, b] = e.ranges[0];
    if (!Array.isArray(d.verses) || d.verses.length !== b - a + 1 || d.verses.some((v, i) => v.chapter !== c || v.verse !== a + i))
      throw Error('Incomplete or mismatched verse range');
    return { edition: d.translation_name || 'World English Bible', text: d.verses.map(v => v.chapter + ':' + v.verse + '  ' + v.text.trim()).join('\n\n') };
  }
  if (e.kind === 'quran') {
    let parts = [];
    for (let [c, a, b] of e.ranges) {
      let d = await getJSON('https://api.alquran.cloud/v1/surah/' + c + (language === 'fr' ? '/fr.hamidullah' : '/en.pickthall'));
      let verses = d.data?.ayahs?.filter(v => v.numberInSurah >= a && v.numberInSurah <= b);
      if (d.data?.number !== c || !verses || verses.length !== b - a + 1)
        throw Error('Incomplete or mismatched verse range');
      parts.push(...verses.map(v => c + ':' + v.numberInSurah + '  ' + v.text));
    }
    return { edition: language === 'fr' ? 'Muhammad Hamidullah - Al Quran Cloud' : 'Pickthall - Al Quran Cloud', text: parts.join('\n\n') };
  }
  if (e.hadithAPI) {
    let d = await getJSON(e.hadithAPI);
    let n = Number(e.hadithNumber);
    let h = d.hadiths?.find(x => Number(x.hadithnumber) === n && Number(x.arabicnumber) === n);
    if (!h?.text)
      throw Error('Numbering could not be matched');
    return { edition: 'Hadith API - English edition (compare Sunnah.com)', text: h.text };
  }
  return null;
}
function entry(e) {
  const d = el('details', 'entry');
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
  for (const [name, url] of localizedSources(e)) {
    const li = el('li');
    li.append(link(name, url));
    sources.append(li);
  }
  if (!e.sources.length)
    sources.append(el('li', 'muted', tr('No source configured.')));
  const retry = el('button', '', tr('Retry'));
  retry.hidden = true;
  panel.append(edition, verse, el('strong', '', tr('Sources')), sources, retry);
  d.append(panel);
  let loaded = false;
  async function load() {
    loaded = true;
    retry.hidden = true;
    edition.textContent = '';
    verse.textContent = tr('Loading...');
    try {
      const result = await read(e);
      if (result) {
        edition.textContent = (LANG === 'fr' && e.kind !== 'quran' ? tr('English full text') + ' - ' : '') + result.edition;
        verse.textContent = result.text;
      }
      else {
        verse.textContent = e.sources.length ? tr('Full text is available at the linked source. Inline text is not configured for this reference.') : tr('Full text and source links have not been added for this reference.');
      }
    }
    catch (err) {
      verse.textContent = tr('Full text unavailable. Use a source link below if available.');
      retry.hidden = false;
    }
  }
  retry.onclick = load;
  d.addEventListener('toggle', () => {
    if (d.open && !loaded)
      load();
  });
  return d;
}
function render() {
  const theme = $('theme').value, items = bookBase().filter(e => !theme || e.themes.includes(theme));
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
function localize() {
  document.documentElement.lang = LANG;
  document.querySelectorAll('[data-i18n]').forEach(n => n.textContent = tr(n.dataset.i18n));
  $('menu').setAttribute('aria-label', tr('Open filters'));
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
    localize();
  }
  catch (err) {
    $('count').textContent = tr('Could not load entries. Check that the database has been built and the site is served over HTTP.');
  }
}
init();
