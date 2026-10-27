#!/usr/bin/env python3
"""Index of the PDF library in Dropbox (read by the library web page).

Commands:
  sync [--limit N]       index new PDFs, drop entries whose files are gone
  review [-n N]          papers flagged for review, with page-1 text
  apply                  apply corrections, JSON list on stdin (see SKILL.md)
  add PDF [PDF ...]      move PDFs into the library, index and rename them
  attach PDF --to P --label L   add an appendix/slides/other version to paper P (id or file)
  verify                 flag papers whose metadata is not found in their PDFs
  rename FILE            rename a file to Author-Title-Year-Venue.pdf
  stats                  counts, authors with 4+ papers, duplicates
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import unicodedata
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lit  # noqa: E402

# settings: ~/.config/lit/config.json (written by `library.py setup --folder ...`)
CONFIG = os.path.expanduser('~/.config/lit/config.json')


def read_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def dropbox_local_root():
    """Where the Dropbox app keeps its files on this Mac (from ~/.dropbox/info.json)."""
    try:
        with open(os.path.expanduser('~/.dropbox/info.json')) as f:
            info = json.load(f)
        return next(v['path'] for v in info.values() if isinstance(v, dict) and v.get('path'))
    except (OSError, ValueError, StopIteration):
        return None


_cfg = read_config()
ROOT = os.path.expanduser(_cfg.get('library_folder', ''))
_dbx = dropbox_local_root()
# the same folder as the web page sees it inside Dropbox, e.g. '/Papers'
DROPBOX_ROOT = _cfg.get('dropbox_path') or ('/' + os.path.relpath(ROOT, _dbx) if _dbx and ROOT.startswith(_dbx) else '')
INDEX = os.path.join(ROOT, 'index.json')
READCUBE = os.path.expanduser(_cfg.get('readcube_csv', '~/Downloads/My Library.csv'))
INBOX = os.path.join(ROOT, '_inbox')   # uploads from the web page land here
SKIP_DIRS = {'Deleted from Library', '_inbox'}
FILENAME = re.compile(r'^(?P<author>.+?)-(?P<title>.+)-(?P<year>(?:19|20)\d\d)-(?P<venue>.+?)(?:_\d+| copy)?\.pdf$', re.I)
DOI = re.compile(r'\b(10\.\d{4,9}/[^\s"<>]+)', re.I)


# ---------- index file ----------

def load_index():
    if os.path.exists(INDEX):
        with open(INDEX, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'dropbox_root': DROPBOX_ROOT, 'papers': [], 'duplicates': []}


def save_index(ix):
    ix['updated'] = datetime.datetime.now().isoformat(timespec='seconds')
    if DROPBOX_ROOT:
        ix['dropbox_root'] = DROPBOX_ROOT
    today = datetime.date.today().isoformat()
    for p in ix['papers']:
        if p.get('jel'):
            p['jel'] = norm_jel(p['jel'])
        p.setdefault('added', today)
        for f in p['files']:
            f.setdefault('added', p['added'])
        # 'Recent' on the page: the paper or its latest new file
        p['last_added'] = max([p['added']] + [f['added'] for f in p['files']])
    used = {c for p in ix['papers'] for c in p.get('jel') or []}
    ix['jel_names'] = {c: jel_names()[c] for c in sorted(used) if c in jel_names()}
    ix['jel_short'] = {c: jel_short(c) for c in sorted(used)}
    ix['papers'].sort(key=lambda p: (p.get('authors') or [{'family': 'zzz'}])[0]['family'].lower())
    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ix, f, ensure_ascii=False, indent=1)
    os.replace(tmp, INDEX)


def all_files(ix):
    return {f['path']: (p, f) for p in ix['papers'] for f in p['files']}


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def scan():
    out = []
    for d, ds, fs in os.walk(ROOT):
        ds[:] = sorted(x for x in ds if x not in SKIP_DIRS and not x.startswith('.'))
        for f in sorted(fs):
            if f.lower().endswith('.pdf'):
                out.append(os.path.relpath(os.path.join(d, f), ROOT))
    # top-level files first, so they win over copies in subfolders
    return sorted(out, key=lambda p: (p.count('/'), p))


# ---------- metadata from the PDF ----------

def pdf_text(path, pages=3):
    r = subprocess.run(['pdftotext', '-l', str(pages), '-enc', 'UTF-8', path, '-'], capture_output=True, text=True)
    return clean(r.stdout) if r.returncode == 0 else ''


def clean(s):
    s = unicodedata.normalize('NFKC', s or '')
    return re.sub('[\u2010\u2011\u2012\u2013\u00ad]', lambda m: '' if m.group(0) == '\u00ad' else '-', s)


def pdf_title(path):
    r = subprocess.run(['pdfinfo', path], capture_output=True, text=True)
    m = re.search(r'^Title:\s*(.+)$', r.stdout, re.M)
    t = clean(m.group(1)).strip() if m else ''
    if len(t) < 15 or re.search(r'microsoft|\.docx?$|\.tex$|untitled|^paper$|working paper|^\S+$', t, re.I):
        return ''
    return t


def series_doi(name, text):
    """DOI from an NBER number or arXiv id in the file name or on page 1."""
    head = text[:3000]
    m = re.search(r'arxiv[:_ .-]?(?:abs/)?(\d{4}\.\d{4,5})', name + ' ' + head, re.I) or \
        (re.search(r'(?<![\d.])(\d{4}\.\d{4,5})(?:v\d)?(?![\d])', name) if 'arxiv' in (name + head).lower() or
         re.match(r'^\d{4}\.\d{4,5}', name) else None)
    if m:
        return '10.48550/arXiv.' + m.group(1)
    m = re.search(r'(?:^|[_ -])w(\d{4,5})(?:[_ .-]|$)', name) or re.search(r'NBER WORKING PAPER SERIES.{0,200}?(?:Working Paper|No\.?)\s*(\d{4,5})', head, re.I | re.S)
    if m and ('nber' in (name + head).lower()):
        return '10.3386/w' + m.group(1)
    return None


def title_guesses(text):
    """Title candidates from the first lines of page 1 (skipping series headers, dates, numbers)."""
    skip = re.compile(r'working paper|discussion paper|nber|\biza\b|arxiv|draft|this version|first version|'
                      r'^\W*$|^[\d\W]+$|january|february|march|april|may|june|july|august|september|october|'
                      r'november|december|series|http|www\.|doi|issn|cesifo|cepr|journal|volume|preprint', re.I)
    lines = [l.strip() for l in text.split('\f')[0].splitlines() if l.strip()][:15]
    lines = [l for l in lines if not skip.search(l) and len(l) > 3]
    out = []
    for i in range(min(3, len(lines))):
        for j in (1, 2, 3):
            t = ' '.join(lines[i:i + j])
            if 20 <= len(t) <= 220 and t not in out:
                out.append(t)
    return out[:4]


def find_doi(text):
    for m in DOI.finditer(text[:6000]):
        d = m.group(1).rstrip('.,;)]}')
        if not re.search(r'\.(png|jpg|pdf)$', d, re.I) and not d.lower().startswith('10.1257/rct'):
            return d
    return None


def extract_abstract(text):
    m = re.search(r'(?<![\w?=/_.-])(a\s?b\s?s\s?t\s?r\s?a\s?c\s?t|summary)(?![\w_=])\s*[.:—–-]?\s*', text, re.I)
    if not m:
        return ''
    rest = text[m.end():m.end() + 5000]
    # Elsevier puts the keyword block between the heading and the text
    while re.match(r'\s*(Keywords|JEL|Article history|Received|Available online)', rest, re.I):
        nxt = re.search(r'\n\s*\n', rest)
        if not nxt:
            return ''
        rest = rest[nxt.end():]
    stop = re.search(r'\n\s*(JEL\b|Keywords|Key\s?words|K\s?e\s?y\s?w\s?o\s?r\s?d\s?s|Classification|'
                     r'(1|I)\.?\s+Introduction|Introduction\s*\n|\*\s|©|Article history)', rest, re.I)
    if stop:
        rest = rest[:stop.start()]
    else:
        paras = re.split(r'\n\s*\n', rest)
        acc = ''
        for para in paras:
            acc += ' ' + para
            if len(acc) > 400:
                break
        rest = acc
    rest = re.sub(r'(\w)-\n(\w)', r'\1\2', rest)
    rest = re.sub(r'\s+', ' ', rest).strip()
    if len(rest) < 200 or re.search(r'DISCUSSION PAPER|WORKING PAPER SERIES|https?://|ssrn\.com', rest[:300], re.I):
        return ''
    tokens = rest.split()
    # table-of-contents dot leaders, or watermark letters spread through the text
    if re.search(r'(\.\s?){5,}', rest) or sum(len(t) == 1 and t.isalpha() and t not in 'aAI' for t in tokens) > 0.08 * len(tokens):
        return ''
    return rest[:2500]


_jel = None


def jel_names():
    """Official JEL codes with descriptions (AEA classification tree, saved in jel.json)."""
    global _jel
    if _jel is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jel.json'), encoding='utf-8') as f:
            _jel = json.load(f)
    return _jel


_short = None


def jel_short(code):
    """Readable topic name: curated list (jel_short.json), else the official text cleaned up."""
    global _short
    if _short is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jel_short.json'), encoding='utf-8') as f:
            _short = json.load(f)
    if code in _short:
        return _short[code]
    name = jel_names().get(code, code)
    if name.startswith('General') and len(code) == 3:
        name = jel_names().get(code[:2], code) + ' (general)'
    name = re.sub(r'\s*;\s*', ', ', name)
    return name if len(name) <= 60 else name[:name.rfind(',', 0, 60)] if ',' in name[:60] else name[:60]


def norm_jel(codes):
    """3-character codes only: 'J6' becomes 'J60'."""
    out = []
    for c in codes:
        c = c + '0' if len(c) == 2 and c + '0' in jel_names() else c
        if len(c) == 3 and c in jel_names() and c not in out:
            out.append(c)
    return out


def extract_jel(text):
    """JEL codes printed on the first pages ('JEL Classification: J24, J62')."""
    codes = []
    for m in re.finditer(r'\bJ\s?E\s?L\b[^:\n]{0,40}?[:.\-–—]?\s*((?:[A-Z]\s?\d{1,2}[\s,;.]*(?:and\s+)?){1,15})', text[:20000]):
        for c in re.findall(r'\b([A-Z])\s?(\d{1,2})\b', m.group(1)):
            code = c[0] + c[1]
            if code in jel_names() and code not in codes:
                codes.append(code)
    return codes


def title_in_text(title, text):
    """Share of the title's words (4+ letters) that occur on the first pages."""
    words = [w for w in lit.fold(title).split() if len(w) >= 4]
    body = ' ' + lit.fold(text[:8000]) + ' '
    return sum((' ' + w + ' ') in body for w in words) / len(words) if words else 0


def authors_in_text(authors, text):
    """True if some author's family name occurs on the first pages (or there are no authors to check)."""
    if not authors or len(re.findall(r'[A-Za-z]', text[:5000])) < 300:
        return True  # no usable text layer (scan): nothing to check
    body = ' ' + re.sub(r'\d', ' ', lit.umlaut(lit.fold(text[:10000]))) + ' '  # superscripts: 'Frank1,2'
    fams = [a['family'] if isinstance(a, dict) else split_name(a, comma=False)['family'] for a in authors]
    return any((' ' + lit.umlaut(lit.fold(f)) + ' ') in body for f in fams if f)


def matches_pdf(title, authors, text, min_title=0.7):
    """A candidate only counts if its title and at least one author are on the PDF's first pages."""
    return len(re.findall(r'[A-Za-z]', text[:5000])) < 300 or (title_in_text(title, text) >= min_title and authors_in_text(authors, text))


def clean_venue(v):
    v = re.sub(r'^The ', '', (v or '').strip())
    return {'SSRN Electronic Journal': 'SSRN', 'RePEc: Research Papers in Economics': '', 'RePEc': '',
            'arXiv (Cornell University)': 'arXiv', 'Research Papers in Economics': ''}.get(v, v)


def parse_filename(name):
    m = FILENAME.match(name.replace('\xa0', ' '))
    if not m:
        return None
    return {'author': m.group('author'), 'title': m.group('title').replace('- ', ': ').strip(),
            'year': int(m.group('year')), 'venue': m.group('venue').strip()}


_rc = None


def readcube():
    global _rc
    if _rc is None:
        _rc = []
        if os.path.exists(READCUBE):
            with open(READCUBE, encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    if r.get('Title') and not r['Title'].lower().endswith('.pdf'):
                        _rc.append(r)
    return _rc


def readcube_match(doi, text, title_hint):
    for r in readcube():
        if doi and r.get('doi') and r['doi'].lower() == doi.lower():
            return r
    best, score = None, 0
    for r in readcube():
        s = lit.sim(title_hint, r['Title']) if title_hint else 0
        if s < 0.9 and len(lit.fold(r['Title']).split()) >= 4 and lit.fold(r['Title'])[:60] in lit.fold(text[:8000]):
            s = 0.9
        if s > score:
            best, score = r, s
    return best if score >= 0.9 else None


def split_name(display, comma=True):
    """'Gerard J. van den Berg' or 'van den Berg, Gerard J.' -> {'family', 'given'}.
    comma=False for OpenAlex display names, where a comma is a typo ('Mollie,E. Brooks')."""
    display = re.sub(r'\s+', ' ', clean(display).replace('\xa0', ' ')).strip()
    if not comma:
        display = re.sub(r'\s*,\s*', ' ', display)
    if ',' in display:
        fam, giv = [x.strip() for x in display.split(',', 1)]
        return {'family': fam, 'given': giv}
    parts = display.split(' ')
    i = len(parts) - 1
    while i > 0 and parts[i - 1].lower() in ('van', 'von', 'de', 'der', 'den', 'del', 'della', 'di', 'da', 'le', 'la', 'du', 'dos'):
        i -= 1
    return {'family': ' '.join(parts[i:]), 'given': ' '.join(parts[:i])}


def file_label(fn, w, path):
    if fn:
        return f'{fn["venue"]} {fn["year"]}'
    if w and (w.get('venue') or w.get('year')):
        return f'{w.get("venue") or ""} {w.get("year") or ""}'.strip()
    return os.path.splitext(os.path.basename(path))[0]


def describe(path):
    """Metadata for one PDF: OpenAlex (by DOI in the text, then by title), checked against the text."""
    full = os.path.join(ROOT, path)
    with open(full, 'rb') as fh:
        if not fh.read(1024).lstrip().startswith(b'%PDF'):
            meta = {'title': 'Not a PDF (failed download?): ' + os.path.basename(path), 'authors': [], 'year': None,
                    'venue': '', 'doi': None, 'abstract': ''}
            return meta, {'path': path, 'md5': md5(full), 'label': 'not a PDF', 'added': datetime.date.today().isoformat()}, \
                ['not a PDF: download again']
    text = pdf_text(full)
    fn = parse_filename(os.path.basename(path))
    doi = find_doi(text)
    review = []
    w = None
    if doi:
        w = lit.work_by_doi(doi)
        if w and not matches_pdf(w['title'], w['authors'], text):
            w = None  # DOI of something else (a cited paper, the journal)
    rc = readcube_match(doi, text, fn['title'] if fn else None)
    if rc and text.strip() and title_in_text(rc['Title'], text) < 0.7:
        rc = None
    if not w and rc and rc.get('doi'):
        w = lit.work_by_doi(rc['doi'])
        if w and not matches_pdf(w['title'], w['authors'], text):
            w = None
    if not w:
        sd = series_doi(os.path.basename(path), text)
        if sd:
            w = lit.work_by_doi(sd)
            if w and not matches_pdf(w['title'], w['authors'], text):
                w = None
    if not w and not rc and not fn and text.strip():
        for guess in ([pdf_title(full)] if pdf_title(full) else []) + title_guesses(text):
            cands = lit.find(guess)
            if cands and cands[0]['sim'] >= 0.85 and matches_pdf(cands[0]['title'], cands[0]['authors'], text, 0.8):
                w = cands[0]
                break
    if not w:
        hint = (rc or {}).get('Title') or (fn or {}).get('title')
        if hint:
            cands = lit.find(hint, (fn or {}).get('author'))
            if cands and cands[0]['sim'] >= 0.9 and matches_pdf(cands[0]['title'], cands[0]['authors'], text):
                w = cands[0]
    if w:
        meta = {'title': clean(w['title']), 'authors': [split_name(a, comma=False) for a in w['authors']], 'year': w['year'],
                'venue': clean_venue(w['venue']), 'doi': w['doi'], 'openalex': w['id']}
        if not w['authors']:
            review.append('no authors in OpenAlex')
    elif rc:
        meta = {'title': clean(rc['Title']), 'authors': [split_name(a) for a in rc.get('Author', '').split(';') if a.strip()],
                'year': int(rc['year']) if rc.get('year', '').isdigit() else None,
                'venue': rc.get('Journal') or '', 'doi': rc.get('doi') or None}
        review.append('ReadCube metadata only')
    elif fn and (not text.strip() or title_in_text(fn['title'], text) >= 0.7):
        meta = {'title': fn['title'], 'authors': [{'family': fn['author'], 'given': ''}], 'year': fn['year'],
                'venue': fn['venue'], 'doi': None}
        review.append('from file name only: co-authors missing')
    else:
        meta = {'title': os.path.splitext(os.path.basename(path))[0], 'authors': [], 'year': None, 'venue': '', 'doi': None}
        review.append('not identified' + (' (no text layer)' if not text.strip() else ''))
    abstract = extract_abstract(text) or (rc or {}).get('Abstract', '') or (w or {}).get('abstract', '')
    meta['abstract'] = clean(re.sub(r'^Abstract\s*', '', abstract or '')).strip()
    meta['jel'] = extract_jel(text)
    f = {'path': path, 'md5': md5(full), 'label': file_label(fn, w, path), 'added': datetime.date.today().isoformat()}
    return meta, f, review


# ---------- grouping versions ----------

def same_paper(p, meta):
    if meta.get('doi') and p.get('doi') and meta['doi'].lower() == p['doi'].lower():
        return True
    if not meta.get('authors') or not p.get('authors'):
        return False
    fams = [a['family'] for a in p['authors']]
    return lit.sim(p['title'], meta['title']) >= 0.9 and any(lit.surname_in(a['family'], fams) for a in meta['authors'])


def paper_id(meta, ix):
    fam = lit.fold(meta['authors'][0]['family']).replace(' ', '') if meta.get('authors') else 'unknown'
    word = next((w for w in lit.fold(meta['title']).split() if len(w) > 3), 'x')
    base = f'{fam}{meta.get("year") or ""}{word}'
    ids = {p['id'] for p in ix['papers']}
    pid, i = base, 2
    while pid in ids:
        pid, i = f'{base}{i}', i + 1
    return pid


def is_published(meta):
    """Journal version: a DOI that is not a working-paper series (NBER, SSRN, arXiv, IZA...)."""
    doi, venue = meta.get('doi') or '', meta.get('venue') or ''
    return bool(doi) and not re.match(r'10\.(3386|2139|48550)/', doi, re.I) and \
        not lit.WP_WORDS.search(venue) and not re.search(r'National Bureau|Research Papers|LSE Research Online', venue)


def add_to_index(ix, meta, f, review):
    for p in ix['papers']:
        if same_paper(p, meta):
            # a published version becomes the main PDF
            p['files'].insert(0, f) if is_published(meta) and not is_published(p) else p['files'].append(f)
            if is_published(meta) and not is_published(p):
                p.update({k: v for k, v in meta.items() if v and k != 'abstract'})
            if not p.get('abstract') and meta.get('abstract'):
                p['abstract'] = meta['abstract']
            p['jel'] = list(dict.fromkeys((p.get('jel') or []) + (meta.get('jel') or [])))
            return p, False
    p = {'id': paper_id(meta, ix), **meta, 'files': [f], 'added': datetime.date.today().isoformat()}
    if review:
        p['review'] = '; '.join(review)
    ix['papers'].append(p)
    return p, True


# ---------- commands ----------

def cmd_sync(a):
    ix = load_index()
    present = scan()
    known = all_files(ix)
    gone = [p for p in known if p not in set(present)]
    for path in gone:
        p, f = known[path]
        p['files'].remove(f)
    ix['papers'] = [p for p in ix['papers'] if p['files']]
    ix['duplicates'] = [d for d in ix.get('duplicates', []) if d['path'] in set(present)]
    hashes = {f['md5']: f['path'] for p in ix['papers'] for f in p['files']}
    dup_paths = {d['path'] for d in ix['duplicates']}
    new = [p for p in present if p not in known and p not in dup_paths]
    if a.limit:
        new = new[:a.limit]
    added = versions = dups = 0
    for i, path in enumerate(new, 1):
        h = md5(os.path.join(ROOT, path))
        if h in hashes:
            ix['duplicates'].append({'path': path, 'same_as': hashes[h]})
            dups += 1
            continue
        print(f'[{i}/{len(new)}] {path}', file=sys.stderr)
        meta, f, review = describe(path)
        _, is_new = add_to_index(ix, meta, f, review)
        hashes[f['md5']] = path
        added += is_new
        versions += not is_new
        if i % 20 == 0:
            save_index(ix)
    save_index(ix)
    n_rev = sum(1 for p in ix['papers'] if p.get('review'))
    print(f'{added} new papers, {versions} new versions of known papers, {dups} identical copies skipped, '
          f'{len(gone)} files gone. Index: {len(ix["papers"])} papers, {n_rev} flagged for review.')


def cmd_retry(a):
    """Re-run identification for flagged papers (after the builder learned new tricks)."""
    ix = load_index()
    todo = [p for p in ix['papers'] if p.get('review')]
    fixed = 0
    for i, p in enumerate(todo, 1):
        print(f'[{i}/{len(todo)}] {p["files"][0]["path"]}', file=sys.stderr)
        results = [describe(f['path']) for f in p['files']]
        if any(r[2] for r in results):
            continue
        ix['papers'].remove(p)
        for meta, f, review in results:
            add_to_index(ix, meta, f, review)
        fixed += 1
    save_index(ix)
    print(f'{fixed} of {len(todo)} flagged papers identified; {sum(1 for p in ix["papers"] if p.get("review"))} still flagged.')


def cmd_verify(a):
    """Flag papers whose title and authors are not found in any of their PDFs (wrong OpenAlex match)."""
    ix = load_index()
    bad = 0
    for p in ix['papers']:
        if p.get('review') or p.get('checked') or not p.get('authors'):
            continue
        texts = [pdf_text(os.path.join(ROOT, f['path'])) for f in p['files']]
        # versions may be retitled, but each must carry one of the authors (appendices are exempt)
        strays = [f['path'] for f, t in zip(p['files'], texts)
                  if not re.search(r'appendix|supplement|tables|slides', f.get('label') or '', re.I) and not authors_in_text(p['authors'], t)]
        if not any(matches_pdf(p['title'], p['authors'], t) for t in texts) or strays:
            p['review'] = ('files without any of the authors: ' + ', '.join(strays)) if strays else \
                'metadata may not match the PDF (title or authors not on page 1-3)'
            bad += 1
            print(f'{p["id"]}: {p["title"][:70]} <- {strays or p["files"][0]["path"]}')
        p['venue'] = clean_venue(p.get('venue'))
    save_index(ix)
    print(f'{bad} papers flagged.')


def cmd_jel(a):
    """Read JEL codes from all version files (appendices skipped) into the index."""
    ix = load_index()
    found = 0
    for p in ix['papers']:
        if p.get('jel_source') == 'assigned' and not a.redo:
            continue
        codes = []
        for f in p['files']:
            if re.search(r'appendix|supplement|tables|slides', f.get('label') or '', re.I):
                continue
            for c in extract_jel(pdf_text(os.path.join(ROOT, f['path']), 3)):
                if c not in codes:
                    codes.append(c)
        if codes:
            p['jel'], p['jel_source'] = codes, 'pdf'
            found += 1
    save_index(ix)
    print(f'{found} of {len(ix["papers"])} papers have JEL codes printed in the PDF; '
          f'{sum(1 for p in ix["papers"] if not p.get("jel"))} without.')


def cmd_notes(a):
    """Attach the notes from the ReadCube export (column 'notes') to papers in the library."""
    rows = [r for r in csv.DictReader(open(a.csv, encoding='utf-8-sig')) if (r.get('notes') or '').strip()]
    ix = load_index()
    done, missing = 0, []
    for r in rows:
        doi = (r.get('doi') or '').lower()
        p = next((p for p in ix['papers'] if doi and (p.get('doi') or '').lower() == doi), None) or \
            next((p for p in ix['papers'] if lit.sim(p['title'], r['Title']) >= 0.9), None)
        if not p:
            missing.append(f"{(r.get('First author') or '?').split(',')[0]} {r.get('year') or ''}: {r['Title'][:70]}")
            continue
        p['notes'] = r['notes'].strip()
        done += 1
    save_index(ix)
    print(f'{done} notes attached; {len(missing)} belong to papers without a PDF in the library:')
    for m in missing:
        print('  ' + m)


def cmd_want(a):
    """Add a paper to the to-download list shown on the page."""
    ix = load_index()
    w = {'title': a.title, 'authors': a.authors or '', 'venue': a.venue or '', 'year': a.year or '',
         'notes': a.notes or '', 'added': datetime.date.today().isoformat()}
    ix.setdefault('wanted', []).append(w)
    save_index(ix)
    print(f'to download: {a.title} ({len(ix["wanted"])} on the list)')


def cmd_wanted(a):
    ix = load_index()
    if a.remove:
        before = len(ix.get('wanted', []))
        ix['wanted'] = [w for w in ix.get('wanted', []) if a.remove.lower() not in w['title'].lower()]
        save_index(ix)
        print(f'removed {before - len(ix["wanted"])}')
    for w in ix.get('wanted', []):
        print(f'- {w["title"]} | {w["authors"]} | {w["year"]} | {w["venue"]}' + (' | has notes' if w.get('notes') else ''))


def cmd_setup(a):
    """Point the scripts at a library folder inside Dropbox (once per computer)."""
    folder = os.path.abspath(os.path.expanduser(a.folder))
    os.makedirs(os.path.join(folder, '_inbox'), exist_ok=True)
    cfg = read_config()
    cfg['library_folder'] = folder
    if a.email:
        cfg['email'] = a.email
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, 'w') as f:
        json.dump(cfg, f, indent=1)
    dbx = dropbox_local_root()
    inside = '/' + os.path.relpath(folder, dbx) if dbx and folder.startswith(dbx) else None
    print(f'library folder: {folder}')
    print(f'on the web page pick: {inside}' if inside else 'warning: this folder is not inside your Dropbox, the web page cannot see it')
    print('next: python3 library.py sync')


def cmd_review(a):
    ix = load_index()
    todo = [p for p in ix['papers'] if p.get('review')]
    print(f'{len(todo)} papers flagged for review.\n')
    for p in todo[:a.n]:
        f = p['files'][0]
        au = '; '.join(f'{x["family"]}, {x["given"]}' for x in p.get('authors', []))
        print(f'=== {f["path"]}\n  reason: {p["review"]}\n  now: {p["title"]} | {au} | {p.get("year")} | {p.get("venue")}')
        lines = [l.strip() for l in pdf_text(os.path.join(ROOT, f['path']), 1).splitlines() if l.strip()]
        print('  page 1: ' + ' / '.join(lines[:18])[:900] + '\n')


def cmd_apply(a):
    """JSON list on stdin: {"file": path, then any of: "doi", "title", "authors": ["Family, Given", ...],
    "year", "venue", "abstract", "lookup": true (refetch from OpenAlex by doi/title), "merge_with": other path, "main": true (make it the paper's main PDF), "jel": [codes] (assigned from title/abstract),
    "split": true, "ok": true (clear review flag)}."""
    ix = load_index()
    for u in json.load(sys.stdin):
        known = all_files(ix)
        if u['file'] not in known:
            print(f'not in index: {u["file"]}', file=sys.stderr)
            continue
        p, f = known[u['file']]
        if u.get('split') or u.get('merge_with'):
            p['files'].remove(f)
            if not p['files']:
                ix['papers'].remove(p)
            if u.get('merge_with'):
                if 'label' in u:
                    f['label'] = u['label']
                known[u['merge_with']][0]['files'].append(f)
                print(f'merged {u["file"]} into {known[u["merge_with"]][0]["id"]}')
                continue
            meta = {k: p.get(k) for k in ('title', 'authors', 'year', 'venue', 'doi', 'abstract')}
            p = {'id': paper_id(meta, ix), **meta, 'files': [f], 'added': p.get('added')}
            ix['papers'].append(p)
        if u.get('lookup'):
            w = lit.work_by_doi(u['doi']) if u.get('doi') else lit.resolve(u.get('title') or p['title'])
            if w:
                p.update({'title': clean(w['title']), 'authors': [split_name(x, comma=False) for x in w['authors']],
                          'year': w['year'], 'venue': clean_venue(w['venue']), 'doi': w['doi'], 'openalex': w['id']})
                if not p.get('abstract'):
                    p['abstract'] = w.get('abstract', '')
        for k in ('title', 'year', 'venue', 'doi', 'abstract', 'notes'):
            if k in u:
                p[k] = u[k]
        if 'authors' in u:
            p['authors'] = [split_name(x) for x in u['authors']]
        if 'jel' in u:
            # codes chosen from title and abstract, not printed in the paper
            p['jel'] = [c for c in u['jel'] if c in jel_names()]
            p['jel_source'] = 'assigned'
        if 'label' in u:
            f['label'] = u['label']
        if u.get('main'):
            # first file = the PDF the page opens by default
            p['files'].remove(f)
            p['files'].insert(0, f)
        if u.get('ok') or u.get('lookup'):
            p.pop('review', None)
        if u.get('ok'):
            p['checked'] = True  # confirmed by hand: verify leaves it alone
        old_id = p['id']
        p['id'] = 'tmp'
        p['id'] = paper_id(p, ix) if p.get('authors') else old_id
        print(f'{p["id"]}: {p["title"]} ({p.get("year")})')
    save_index(ix)


def canonical_name(p, f):
    fam = p['authors'][0]['family'] if p.get('authors') else 'Unknown'
    title = re.sub(r'[:/?*"<>|\\]', '-', p['title']).strip()
    venue = re.sub(r'[:/?*"<>|\\]', '-', p.get('venue') or 'WP').strip()
    name = f'{fam}-{title}-{p.get("year") or "nd"}-{venue}'[:180] + '.pdf'
    return name


def rename_file(ix, path):
    p, f = all_files(ix)[path]
    if p.get('review'):
        print(f'not renamed (flagged for review): {path}', file=sys.stderr)
        return path
    new = canonical_name(p, f)
    if len(p['files']) > 1 and f.get('label'):
        # a version: Author-Title-<its own label>.pdf
        new = canonical_name(p, f)[:-4].rsplit('-', 2)[0] + '-' + re.sub(r'[:/?*"<>|\\]', '-', f['label']) + '.pdf'
    if new == os.path.basename(path):
        return path
    target = os.path.join(ROOT, new)
    # macOS is case-insensitive: a change of case only is not a clash
    if os.path.exists(target) and target.lower() != os.path.join(ROOT, path).lower():
        print(f'not renamed, target exists: {new}', file=sys.stderr)
        return path
    os.rename(os.path.join(ROOT, path), target)
    f['path'] = new
    print(f'renamed: {path} -> {new}')
    return new


def match_wanted(ix, p):
    """Tick a paper off the to-download list; its notes move to the paper."""
    for w in list(ix.get('wanted', [])):
        if (w.get('doi') and p.get('doi') and w['doi'].lower() == p['doi'].lower()) or lit.sim(w['title'], p['title']) >= 0.85:
            ix['wanted'].remove(w)
            if w.get('notes'):
                p['notes'] = (p['notes'] + '\n\n' if p.get('notes') else '') + w['notes']
            return w
    return None


def cmd_add(a):
    ix = load_index()
    add_files(ix, a.pdfs)
    save_index(ix)


def cmd_inbox(a):
    """Index everything uploaded to literature/_inbox from the web page."""
    pdfs = sorted(os.path.join(INBOX, f) for f in os.listdir(INBOX) if f.lower().endswith('.pdf')) if os.path.isdir(INBOX) else []
    if not pdfs:
        print('inbox is empty')
        return
    ix = load_index()
    add_files(ix, pdfs)
    save_index(ix)
    left = [f for f in os.listdir(INBOX) if not f.startswith('.')]
    print(f'{len(pdfs) - len(left)} of {len(pdfs)} files moved into the library' + (f'; still in the inbox: {", ".join(left)}' if left else ''))


def add_files(ix, srcs):
    hashes = {f['md5']: f['path'] for p in ix['papers'] for f in p['files']}
    for src in srcs:
        h = md5(src)
        if h in hashes:
            print(f'already in the library: {src} = {hashes[h]}')
            continue
        name = os.path.basename(src)
        if os.path.exists(os.path.join(ROOT, name)):
            name = os.path.splitext(name)[0] + f'_{h[:6]}.pdf'
        shutil.move(src, os.path.join(ROOT, name))
        meta, f, review = describe(name)
        p, is_new = add_to_index(ix, meta, f, review)
        hashes[h] = name
        print(('new paper ' if is_new else 'new version of ') + f'{p["id"]}: {p["title"]} ({p.get("year")})'
              + (f'  [review: {p["review"]}]' if p.get('review') else ''))
        w = match_wanted(ix, p)
        if w:
            print(f'  ticked off the to-download list: {w["title"]}' + (' (notes attached)' if w.get('notes') else ''))
        if not p.get('review'):
            rename_file(ix, name)


def cmd_attach(a):
    """Add a PDF (online appendix, slides, another version) to an existing paper."""
    ix = load_index()
    known = all_files(ix)
    p = known[a.to][0] if a.to in known else next((x for x in ix['papers'] if x['id'] == a.to), None)
    if not p:
        sys.exit(f'no paper with id or file {a.to}')
    h = md5(a.pdf)
    for q in ix['papers']:
        for f in q['files']:
            if f['md5'] == h:
                sys.exit(f'already in the library: {f["path"]} ({q["id"]})')
    slug = re.sub(r'[^A-Za-z0-9]+', ' ', a.label).strip()
    name = canonical_name(p, None)[:-4][:150] + f'-{slug}.pdf'
    if os.path.exists(os.path.join(ROOT, name)):
        name = name[:-4] + f'_{h[:6]}.pdf'
    shutil.move(a.pdf, os.path.join(ROOT, name))
    p['files'].append({'path': name, 'md5': h, 'label': a.label, 'added': datetime.date.today().isoformat()})
    save_index(ix)
    print(f'attached to {p["id"]} as "{a.label}": {name}')


def cmd_rename(a):
    ix = load_index()
    rename_file(ix, a.file)
    save_index(ix)


def author_key(x):
    given = lit.fold(x.get('given', ''))
    return lit.fold(x['family']) + '|' + (given[:1] if given else '')


def cmd_stats(a):
    ix = load_index()
    counts = {}
    for p in ix['papers']:
        for k in {author_key(x) for x in p.get('authors', [])}:
            counts[k] = counts.get(k, 0) + 1
    top = sorted((k for k, v in counts.items() if v >= 4))
    print(f'{len(ix["papers"])} papers, {sum(len(p["files"]) for p in ix["papers"])} files, '
          f'{len(ix.get("duplicates", []))} identical copies, {len(counts)} authors, '
          f'{sum(1 for p in ix["papers"] if p.get("review"))} flagged, '
          f'{sum(1 for p in ix["papers"] if not p.get("abstract"))} without abstract.')
    print('4+ papers: ' + ', '.join(f'{k} ({counts[k]})' for k in top))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('sync'); s.add_argument('--limit', type=int)
    s = sp.add_parser('review'); s.add_argument('-n', type=int, default=15)
    sp.add_parser('apply')
    sp.add_parser('retry')
    sp.add_parser('verify')
    s = sp.add_parser('jel', help='read JEL codes from the PDFs'); s.add_argument('--redo', action='store_true')
    s = sp.add_parser('notes', help='attach notes from the ReadCube export'); s.add_argument('--csv', default=READCUBE)
    sp.add_parser('inbox', help='index PDFs uploaded to literature/_inbox')
    s = sp.add_parser('setup', help='choose the library folder (inside Dropbox)'); s.add_argument('--folder', required=True)
    s.add_argument('--email', help='your email, sent to Crossref and OpenAlex as a polite contact')
    s = sp.add_parser('want', help='add a paper to the to-download list'); s.add_argument('title')
    s.add_argument('--authors'); s.add_argument('--venue'); s.add_argument('--year'); s.add_argument('--notes')
    s = sp.add_parser('wanted', help='show (or --remove) the to-download list'); s.add_argument('--remove')
    s = sp.add_parser('add'); s.add_argument('pdfs', nargs='+')
    s = sp.add_parser('rename'); s.add_argument('file')
    s = sp.add_parser('attach', help='add an appendix or other version to a paper')
    s.add_argument('pdf'); s.add_argument('--to', required=True, help='paper id or one of its files')
    s.add_argument('--label', required=True, help='e.g. "Online appendix", "Slides", "NBER WP 2023"')
    sp.add_parser('stats')
    a = p.parse_args()
    if a.cmd != 'setup' and not os.path.isdir(ROOT):
        sys.exit('No library folder set up yet. Run once:\n  python3 library.py setup --folder "~/Dropbox/<your PDF folder>"')
    {'sync': cmd_sync, 'retry': cmd_retry, 'verify': cmd_verify, 'attach': cmd_attach, 'jel': cmd_jel, 'notes': cmd_notes,
     'inbox': cmd_inbox, 'setup': cmd_setup, 'want': cmd_want, 'wanted': cmd_wanted, 'review': cmd_review, 'apply': cmd_apply, 'add': cmd_add,
     'rename': cmd_rename, 'stats': cmd_stats}[a.cmd](a)


if __name__ == '__main__':
    main()
