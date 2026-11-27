# Unholy Index

A simple dark-mode reference browser. Python 3; no additional dependencies.

## Run

Extract the ZIP and open a terminal in the extracted folder. Run `python tools/localhost.py` (or `python3 tools/localhost.py` / `py tools/localhost.py`).

- Computer: http://localhost:8888
- Phone: connect to the same Wi-Fi and open the local IP URL printed by the server.
- Allow Python through the firewall for private networks if necessary. Anyone on the reachable LAN can access the site; do not forward port 8888. Stop with Ctrl+C.

## Add books and religions

The builder recursively discovers `.md` files under `books/<religion>/`. The first folder name defines the religion, and the filename defines the collection. Use lowercase folder names and hyphens for spaces. The hidden left-side filter menu contains Religion, Book, Theme and Language dropdowns populated from the data. Open it using the top-left hamburger icon. The Book filter supports entire collections and individual books/surahs.

Use this format:

```markdown
# Slavery

- Leviticus 25:44-46 - Allows buying and inheriting foreign slaves.
```

For new collections with no built-in source provider, append one or more direct URLs:

```markdown
# Theme

- Reference 1:2 - Short description. | https://example.org/passage/1/2 | https://example.com/other-edition
```

The example URLs are placeholders. The links will appear below the entry; unknown collections do not automatically fetch full text or discover sources. Bible and Quran references in their existing formats get generated source URLs and inline text loading. Supported hadith get direct links and selected editions get inline text. Unknown reference formats are still listed. Source URLs are not automatically verified. Full text requires internet. Opening a supported entry sends the reference to an external provider.

Restart `tools/localhost.py` after changes, then refresh the browser. Alternatively run `python tools/build.py` while the server is running and refresh. No edits to HTML or Python are needed to add a religion, theme, or book unless you want a new automatic source/text provider. Do not edit `generated/entries.json`; it is rebuilt from the Markdown files. The HTML, styles and JavaScript are maintained separately in `site/`. The page loads the generated JSON over HTTP using a relative URL.

The existing collection contains 496 records. See `sources.md` for recovery and verification limitations. Keep notes and non-entry Markdown outside `books/`.

## Languages

English is the canonical reference database in `books/`. French translations mirror the original directory structure in `translations/fr/`. Keep the original English heading and reference exactly the same, and translate only the summary after ` - `. The builder matches by collection path, original heading and reference rather than line number. Do not translate references in these files. Adding a new English entry without a translation works normally: in French mode the English summary is displayed with a translation-pending label. Add the corresponding French bullet and rebuild to translate it. The browser remembers the selected language. UI labels and book/theme names are translated via `site/i18n.js`; add new theme or religion labels there as needed. New language directories are read by the builder, but offering another language in the UI requires adding its dictionary, language option and display logic.

All 496 existing summaries have French translations. These are translations of the recovered English summaries, not a new independent verification of each passage. French Quran text uses the Muhammad Hamidullah edition from Al Quran Cloud, and French source links open Quran.com. French Bible links use Louis Segond (LSG) on Bible Gateway; inline Bible text is still WEB in English and labeled accordingly. Inline hadith text remains English and is labeled; availability varies by source. Live external providers have not been retested.

## Git and GitHub Pages

The Markdown files and site source are tracked; `generated/` and `dist/` are build outputs ignored by Git. If you committed the generated database in an older version, run `git rm --cached generated/entries.json` once to stop tracking it. This does not delete your local file.

The Pages workflow is deliberately manual (`workflow_dispatch` only). Pushing commits does not trigger a deployment. You can keep your repository private and leave Pages disabled while developing. When you are ready to publish, and your GitHub plan supports Pages for the repository visibility:

1. Open the repository's Settings → Pages and select GitHub Actions as the publishing source.
2. Open Actions → Deploy Unholy Index → Run workflow on the default branch.
3. The workflow builds the database and uploads only the `site/` assets and the generated JSON, not the raw Markdown files or Python tools.

A deployed website may be publicly accessible even if its repository is private. The generated JSON contains the entire reference database, including translations and sources, so all of that data becomes accessible to website visitors. Do not enable Pages until you are ready for this. See [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Code style and checks

The site has no runtime dependencies other than Python 3.10+ for local serving/building. Ruff and Prettier are optional development tools. Configuration is included in `pyproject.toml`, `.prettierrc.json`, and `.editorconfig`. Install/use them only if you want to check or format the source:

```bash
python -m pip install ruff
ruff check tools/
ruff format --check tools/
npx --yes prettier --check site/ .github/workflows/ .prettierrc.json
```

To apply formatting, use `ruff check --fix tools/`, `ruff format tools/` and `npx --yes prettier --write site/ .github/workflows/ .prettierrc.json`. The Markdown reference files are excluded from Prettier so their entry format and content are preserved. This release was manually cleaned and syntax-checked; Ruff/Prettier were unavailable in the build environment and their checks have not been run.

## Updating an older checkout

Back up or commit your local changes first. Copy the new archive contents into the existing checkout without deleting its `.git` directory. Remove the obsolete root `build.py` and `server.py` and review the changes in GitHub Desktop. If you edited books or translations since the previous ZIP, keep or merge your own versions rather than overwriting them.
