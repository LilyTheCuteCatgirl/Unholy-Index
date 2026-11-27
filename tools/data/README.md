# Bundled LDS excerpts

`lds_passages.tsv` contains only the 14 currently indexed Latter-day Saint scripture excerpts (67 verses per language), not entire books. Each line contains the reference, verse number, source English text, and an unofficial French translation, separated by tabs.

English source for Book of Mormon: the 1920 edition in the Book of Mormon Editions Project, based on BYU OpenScripture: https://github.com/jonnyjackson26/bom-editions and https://github.com/BYU-ODH/OpenScripture. The eight English excerpts were checked against the corresponding numbered chapter JSON files. The 1920 source edition is historical/public domain.

English source for Doctrine and Covenants: Ben Crowder's Scripture JSON reference data (2013 base text, publisher describes the verse-only data as public domain): https://github.com/bcbooks/scriptures-json/blob/master/reference/doctrine-and-covenants-reference.json and https://bencrowder.net/scriptures-in-json/. The six English excerpts were checked against the numbered source data. The historical underlying revelations are public domain; the dataset's assertion about the modern edition has not been independently legally verified. No modern copyrighted introductory material is included.

French texts are AI-assisted translations from those English excerpts, not official Church translations or independent translations from an original manuscript. They have not been reviewed by a human translator. The site displays this attribution and links to the official French text for comparison. The numbered range is complete, but additional context is not bundled. Use the source links for full chapters.

The data file is tracked in Git, not generated. `tools/texts.py` imports it without relying on a network request and merges it with the other text providers. Do not add an unlicensed contemporary translation to this file.

## Hadith

The existing online hadith provider has been extended to 11 Sahih Muslim references with explicit internal IDs and Arabic reference checks. The corresponding English and French records were inspected through the source repository. The French translation provenance and redistribution rights are unresolved, so the texts are fetched on demand rather than bundled; on-demand display is not a guarantee of redistribution permission. Muslim 2922 and six Shia entries remain source-only. The existing erroneous reference 1676a is corrected to 1671a in both Markdown files, with a shared-link compatibility alias.
