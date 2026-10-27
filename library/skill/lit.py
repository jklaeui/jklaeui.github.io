#!/usr/bin/env python3
"""Literature lookups on OpenAlex, with Google Scholar results (fetched via Chrome) as fallback.

Commands:
  search QUERY [-n N]            free-text search
  find TITLE [--author A]        title match, best candidates with similarity
  work ID|DOI|TITLE              one work in full (with abstract)
  cites ID|DOI|TITLE [-n N]      works citing it, most cited first
  refs ID|DOI|TITLE              works it cites
  bib ID|DOI|TITLE               BibTeX (Crossref for DOIs, else built from OpenAlex)
  check BIB [--tex F ...] [--out REPORT.md]
                                 verify every entry of a .bib file
  scholar-add KEY                store Scholar results (JSON on stdin) for a bib key or query
  site-add NAME URL              store an author's homepage
  site NAME TITLE                find a paper on that author's pages (status, PDF link)
  sites                          list stored homepages
"""
import argparse
import difflib
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, 'cache')
KEY_FILE = os.path.expanduser('~/.config/openalex/api_key')
API = 'https://api.openalex.org'
CACHE_DAYS = 14

WP_WORDS = re.compile(r'working paper|discussion paper|\bwp\b|\bdp\b|nber|ssrn|arxiv|cepr|\biza\b|cesifo|mimeo|'
                      r'preprint|job market|unpublished|technical report|policy research', re.I)


# ---------- text helpers ----------

LATEX_ACCENT = re.compile(r"\\[`'^\"~=.uvHcdbtk]\s*\{?\\?([A-Za-z])\}?")


def delatex(s):
    s = LATEX_ACCENT.sub(r'\1', s or '')
    s = re.sub(r'\\(textit|textbf|emph|textsc|mathrm|text)\s*', '', s)
    s = s.replace('\\&', '&').replace('--', '-').replace('~', ' ')
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    return re.sub(r'\s+', ' ', s.replace('{', '').replace('}', '')).strip()


SPECIAL = str.maketrans({'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'Ae', 'ß': 'ss', 'ł': 'l', 'Ł': 'L', 'đ': 'd', 'ı': 'i', 'œ': 'oe'})


def fold(s):
    s = unicodedata.normalize('NFKD', delatex(s).translate(SPECIAL))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()


def sim(a, b):
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio()


def umlaut(s):
    """German transliteration: Bächli / Baechli / Bachli compare equal."""
    return re.sub(r'([aou])e', r'\1', s)


def surname_in(surname, names):
    """True if a (folded) surname occurs as whole words in any of the names."""
    s = umlaut(fold(surname))
    return bool(s) and any(re.search(r'(^| )' + re.escape(s) + r'( |$)', umlaut(fold(n))) for n in names)


# ---------- OpenAlex client with cache ----------

_cache = {}
_key_state = {'key': None, 'checked': False}


_MISSING = object()
_db = None


def db():
    """Shared cache in SQLite: safe when several scripts run at once."""
    global _db
    if _db is None:
        os.makedirs(CACHE_DIR, exist_ok=True)
        _db = sqlite3.connect(os.path.join(CACHE_DIR, 'cache.sqlite'), timeout=60)
        _db.execute('pragma journal_mode=wal')
        _db.execute('create table if not exists cache (name text, key text, data text, primary key (name, key))')
    return _db


class Store:
    """Dict-like view of one cache table; every write is saved at once."""

    def __init__(self, name):
        self.name = name

    def get(self, key, default=None):
        row = db().execute('select data from cache where name=? and key=?', (self.name, key)).fetchone()
        return json.loads(row[0]) if row else default

    def __getitem__(self, key):
        v = self.get(key, _MISSING)
        if v is _MISSING:
            raise KeyError(key)
        return v

    def __contains__(self, key):
        return self.get(key, _MISSING) is not _MISSING

    def __setitem__(self, key, value):
        db().execute('insert or replace into cache values (?, ?, ?)', (self.name, key, json.dumps(value, ensure_ascii=False)))
        db().commit()

    def items(self):
        return [(k, json.loads(d)) for k, d in db().execute('select key, data from cache where name=?', (self.name,))]


def cache_load(name):
    if name not in _cache:
        _cache[name] = Store(name)
    return _cache[name]


def cache_save(name):
    pass  # Store writes through


def contact_email():
    """Optional contact for Crossref's polite pool, from ~/.config/lit/config.json."""
    try:
        with open(os.path.expanduser('~/.config/lit/config.json')) as f:
            return json.load(f).get('email')
    except (OSError, ValueError):
        return None


def api_key():
    if not _key_state['checked']:
        _key_state['checked'] = True
        k = os.environ.get('OPENALEX_API_KEY')
        if not k and os.path.exists(KEY_FILE):
            k = open(KEY_FILE).read().strip()
        _key_state['key'] = k or None
    return _key_state['key']


def oa_get(path, params=None, fresh=False):
    """GET an OpenAlex endpoint; responses are cached for CACHE_DAYS. Returns None on 404."""
    params = dict(params or {})
    ck = path + '?' + urllib.parse.urlencode(sorted(params.items()))
    cache = cache_load('openalex')
    hit = cache.get(ck)
    if hit and not fresh and time.time() - hit['t'] < CACHE_DAYS * 86400:
        return hit['data']
    while True:
        q = dict(params)
        if api_key():
            q['api_key'] = api_key()
        r = requests.get(API + path, params=q, timeout=30)
        if r.status_code == 403 and api_key() and 'key_not_activated' in r.text:
            print('note: OpenAlex key not activated yet, running without it', file=sys.stderr)
            _key_state['key'] = None
            continue
        break
    time.sleep(0.15)
    if r.status_code == 404:
        data = None
    elif r.status_code == 429:
        sys.exit('OpenAlex: daily budget used up (429). Try again tomorrow or activate the API key.')
    else:
        r.raise_for_status()
        data = r.json()
    cache[ck] = {'t': time.time(), 'data': data}
    cache_save('openalex')
    return data


def abstract_from_index(inv):
    if not inv:
        return ''
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return ' '.join(w for _, w in pos)


def simplify(w):
    """Flatten an OpenAlex work into the fields we use."""
    locs = w.get('locations') or []
    journal = None
    for loc in [w.get('primary_location') or {}] + locs:
        src = (loc or {}).get('source') or {}
        if src.get('type') == 'journal' and not WP_WORDS.search(src.get('display_name') or ''):
            journal = src.get('display_name')
            break
    prim = ((w.get('primary_location') or {}).get('source') or {}).get('display_name')
    return {
        'id': (w.get('id') or '').rsplit('/', 1)[-1],
        'title': w.get('title') or w.get('display_name') or '',
        'year': w.get('publication_year'),
        'authors': [a['author']['display_name'] for a in w.get('authorships') or []],
        'venue': journal or prim or '',
        'journal': journal,
        'type': w.get('type'),
        'doi': (w.get('doi') or '').replace('https://doi.org/', '') or None,
        'cited_by': w.get('cited_by_count'),
        'abstract': abstract_from_index(w.get('abstract_inverted_index')),
        'referenced_works': [x.rsplit('/', 1)[-1] for x in w.get('referenced_works') or []],
        'other_venues': sorted({((l or {}).get('source') or {}).get('display_name') for l in locs} - {None, journal, prim}),
    }


def work_by_doi(doi):
    doi = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:)', '', doi.strip(), flags=re.I)
    w = oa_get('/works/doi:' + doi)
    return simplify(w) if w else None


def work_by_id(wid):
    w = oa_get('/works/' + wid)
    return simplify(w) if w else None


def find(title, author=None, n=8):
    """Title search; candidates sorted by title similarity (+ bonus if the author matches)."""
    t = re.sub(r'\s+', ' ', re.sub(r'[^\w\s-]', ' ', delatex(title))).strip()
    try:
        data = oa_get('/works', {'filter': 'title.search:' + t, 'per_page': n})
    except requests.HTTPError:
        data = None
    cands = [simplify(w) for w in (data or {}).get('results', [])]
    for c in cands:
        c['sim'] = round(sim(title, c['title']), 3)
        c['author_ok'] = bool(author) and surname_in(author, c['authors'])
    cands.sort(key=lambda c: (c['sim'] + (0.05 if c['author_ok'] else 0)), reverse=True)
    return cands


def resolve(arg):
    """Work from an OpenAlex id, a DOI or a title."""
    a = arg.strip()
    m = re.search(r'(W\d{5,})$', a)
    if m:
        return work_by_id(m.group(1))
    if re.match(r'^(https?://(dx\.)?doi\.org/|doi:)?10\.\d{4,9}/', a, re.I):
        return work_by_doi(a)
    cands = find(a)
    if cands and cands[0]['sim'] >= 0.85:
        return cands[0]
    print('No confident title match. Candidates:', file=sys.stderr)
    for c in cands[:5]:
        print('  ' + line(c) + f'  [sim {c["sim"]}]', file=sys.stderr)
    sys.exit(1)


def line(c):
    au = c['authors']
    au = ', '.join(au[:3]) + (' et al.' if len(au) > 3 else '')
    cb = f' | cited {c["cited_by"]}' if c.get('cited_by') is not None else ''
    doi = f' | doi:{c["doi"]}' if c.get('doi') else ''
    return f'{c["year"]} | {au} | {c["title"]} | {c["venue"] or c["type"]}{cb}{doi} | {c["id"]}'


# ---------- BibTeX ----------

def parse_bib(text):
    """Minimal .bib parser: list of dicts with 'ENTRYTYPE', 'ID' and lower-case field names."""
    entries = []
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,\s]+)\s*,', text):
        etype = m.group(1).lower()
        if etype in ('comment', 'string', 'preamble'):
            continue
        i, depth = m.end(), 1
        while i < len(text) and depth:
            depth += {'{': 1, '}': -1}.get(text[i], 0)
            i += 1
        body = text[m.end():i - 1]
        e = {'ENTRYTYPE': etype, 'ID': m.group(2)}
        j = 0
        for fm in re.finditer(r'(\w+)\s*=\s*', body):
            if fm.start() < j:
                continue
            k, j = fm.group(1).lower(), fm.end()
            if j < len(body) and body[j] in '{"':
                close = '}' if body[j] == '{' else '"'
                d, j0 = 1, j + 1
                j += 1
                while j < len(body) and d:
                    if close == '}':
                        d += {'{': 1, '}': -1}.get(body[j], 0)
                    elif body[j] == '"' and body[j - 1] != '\\':
                        d = 0
                    j += 1
                e[k] = body[j0:j - 1]
            else:
                v = re.match(r'[^,]*', body[j:]).group(0)
                j += len(v)
                e[k] = v.strip()
        entries.append(e)
    return entries


def bib_surnames(author_field):
    out = []
    for a in re.split(r'\s+and\s+', delatex(author_field or '')):
        a = a.strip()
        if not a or a.lower() == 'others':
            continue
        out.append(a.split(',')[0].strip() if ',' in a else a.split()[-1])
    return out


def cited_keys(tex_files):
    keys = []
    pat = re.compile(r'\\(?:[cC]ite\w*|[pP]arencite|[tT]extcite|autocite|nocite)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}')
    for f in tex_files:
        txt = re.sub(r'(?<!\\)%.*', '', open(f, encoding='utf-8', errors='replace').read())
        for m in pat.finditer(txt):
            keys += [k.strip() for k in m.group(1).split(',') if k.strip()]
    return list(dict.fromkeys(keys))


STOPWORDS = {'a', 'an', 'the', 'on', 'of', 'in', 'and', 'for', 'to', 'do', 'does', 'is', 'are', 'how', 'what', 'why', 'when'}
PROTECT = re.compile(r'(?<![{\w])([A-Z]{2,}[a-z]*s?|AI|Swiss|Switzerland|Europe(?:an)?|German(?:y)?|French|France|'
                     r'Danish|Denmark|Norw(?:ay|egian)|Swed(?:en|ish)|Austria(?:n)?|Ital(?:y|ian)|U\.S\.|US|UK|'
                     r'American|British|Chinese|ChatGPT|LinkedIn|Google|Bayesian|Poisson|Markov|Nash)(?![\w}])')


def bib_key(family, year, title):
    fam = fold(family).replace(' ', '') or 'anon'
    word = next((w for w in fold(title).split() if w not in STOPWORDS), '')
    return f'{fam}{year or ""}{word}'


def crossref(doi):
    cache = cache_load('crossref_json')
    if doi not in cache:
        r = requests.get('https://api.crossref.org/works/' + urllib.parse.quote(doi), timeout=30,
                         params={'mailto': contact_email()} if contact_email() else None)
        cache[doi] = r.json()['message'] if r.ok else None
        cache_save('crossref_json')
    return cache[doi]


def bib_name(family, given):
    family = family.strip()
    return (f'{{{family}}}' if ' ' in family else family) + (f', {given.strip()}' if given else '')


def bibtex_for(w):
    """BibTeX entry following the format agreed in SKILL.md."""
    doi = w.get('doi')
    cr = crossref(doi) if doi and not doi.lower().startswith(('10.3386/', '10.48550/', '10.2139/')) else None
    if cr and cr.get('type') in ('journal-article', 'proceedings-article', 'book-chapter'):
        authors = [bib_name(a.get('family', ''), a.get('given', '')) for a in cr.get('author', []) if a.get('family')]
        title = (cr.get('title') or [w['title']])[0]
        journal = re.sub(r'^The ', '', (cr.get('container-title') or [w.get('journal') or ''])[0])
        year = ((cr.get('published-print') or cr.get('issued') or cr.get('published-online') or {}).get('date-parts') or [[w.get('year')]])[0][0]
        fields = [('author', ' and '.join(authors)), ('title', title), ('journal', journal), ('year', year)]
        if cr.get('volume'):
            fields += [('volume', cr['volume']), ('number', cr.get('issue')), ('pages', (cr.get('page') or '').replace('-', '--'))]
        else:
            online = (cr.get('published-online') or cr.get('issued') or {}).get('date-parts', [[None]])[0][0]
            fields[3] = ('year', online or year)
            fields.append(('note', 'Forthcoming'))
        fields.append(('doi', doi))
        typ, fam = 'article', (cr.get('author') or [{}])[0].get('family', '')
    else:
        names = [(n.split()[-1], ' '.join(n.split()[:-1])) for n in w['authors']]
        authors = [bib_name(f, g) for f, g in names]
        title, year, fam = w['title'], w.get('year'), names[0][0] if names else ''
        fields = [('author', ' and '.join(authors)), ('title', title)]
        m_nber = re.match(r'10\.3386/w(\d+)', doi or '', re.I)
        m_arx = re.match(r'10\.48550/arxiv\.(.+)', doi or '', re.I)
        m_ssrn = re.match(r'10\.2139/ssrn\.(\d+)', doi or '', re.I)
        if m_nber:
            fields += [('institution', 'National Bureau of Economic Research'), ('type', 'NBER Working Paper'), ('number', m_nber.group(1))]
        elif m_arx:
            fields += [('institution', 'arXiv'), ('type', 'arXiv preprint'), ('number', m_arx.group(1))]
        elif m_ssrn:
            fields += [('institution', 'SSRN'), ('type', 'SSRN Working Paper'), ('number', m_ssrn.group(1))]
        elif w.get('venue'):
            fields += [('institution', w['venue']), ('type', 'Working Paper')]
        typ = 'techreport' if len(fields) > 2 else 'unpublished'
        if typ == 'unpublished':
            fields.append(('note', 'Mimeo'))
        fields.append(('year', year))
        if doi and not (m_nber or m_arx or m_ssrn):
            fields.append(('doi', doi))
    fields = [(k, PROTECT.sub(r'{\1}', str(v)) if k == 'title' else v) for k, v in fields]
    body = ',\n'.join(f'  {k:<11} = {{{v}}}' for k, v in fields if v not in (None, ''))
    return f'@{typ}{{{bib_key(fam, dict(fields).get("year"), title)},\n{body}\n}}'


def style_notes(e):
    """Breaches of the agreed BibTeX format (SKILL.md)."""
    out = []
    if re.search(r'\band\s+others\b', e.get('author', '')):
        out.append('"and others": give the full author list')
    if re.match(r'\s*\{?The ', e.get('journal', '')):
        out.append('journal starts with "The"')
    extra = [k for k in ('url', 'issn', 'abstract', 'keywords', 'month') if k in e]
    if extra:
        out.append('drop ' + ', '.join(extra))
    for k in ('year', 'volume', 'pages'):
        if re.search(r'forthcoming|conditionally', e.get(k, ''), re.I):
            out.append(f'status in `{k}`: use note={{Forthcoming}} or a `status` field')
    if re.search(r'conditionally accepted', e.get('note', ''), re.I):
        out.append('conditionally accepted goes in `status`, not `note` (should not print)')
    if e['ENTRYTYPE'] == 'article' and not e.get('doi') and 'forthcoming' not in e.get('note', '').lower():
        out.append('article without doi')
    if e['ENTRYTYPE'] == 'techreport' and not (e.get('institution') and e.get('type')):
        out.append('techreport needs institution and type')
    return out


# ---------- Scholar fallback (results come from Chrome, see SKILL.md) ----------

def parse_scholar(r):
    """Split a Scholar byline 'A Smith, B Jones - Journal, 2021 - site' into fields."""
    parts = [p.strip() for p in (r.get('byline') or '').replace('\xa0', ' ').split(' - ')]
    authors = [a.strip(' …') for a in parts[0].split(',')] if parts else []
    venue, year = '', None
    if len(parts) > 1:
        m = re.search(r'((?:19|20)\d\d)\s*$', parts[1])
        if m:
            year = int(m.group(1))
        venue = re.sub(r',?\s*(?:19|20)\d\d\s*$', '', parts[1]).strip(' ,…')
        if re.fullmatch(r'(?:19|20)\d\d', parts[1]):
            venue = ''
    # Scholar venues are noisy (report series, publishers, cut-off text): never treated as a journal
    return {'id': 'scholar:' + (r.get('cid') or ''), 'title': r.get('title', ''), 'year': year, 'authors': authors,
            'venue': venue, 'journal': None, 'truncated': '…' in parts[0] if parts else False,
            'type': 'scholar', 'doi': None, 'cited_by': r.get('cited_by'), 'url': r.get('url')}


def scholar_url(q):
    return 'https://scholar.google.com/scholar?hl=en&q=' + urllib.parse.quote_plus(q)


# ---------- author websites ----------

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120 Safari/537.36'}
SUBPAGE = re.compile(r'research|papers|publications|working|work in progress|projects', re.I)


def site_for(surname):
    """Homepage stored for an author whose name contains this surname (see `site-add`)."""
    for name, url in cache_load('sites').items():
        if surname_in(surname, [name]):
            return name, url
    return None


def fetch_page(url):
    cache = cache_load('sitepages')
    hit = cache.get(url)
    if hit and time.time() - hit['t'] < 7 * 86400:
        return hit['html']
    try:
        r = requests.get(url, headers=UA, timeout=20)
        html = r.text if r.ok and 'html' in r.headers.get('content-type', '') else ''
    except requests.RequestException:
        html = ''
    cache[url] = {'t': time.time(), 'html': html}
    cache_save('sitepages')
    return html


def site_pages(url):
    """The homepage plus its research/papers subpages on the same site."""
    from bs4 import BeautifulSoup
    html = fetch_page(url)
    pages = [(url, html)]
    host = urllib.parse.urlparse(url).netloc
    seen = {url}
    for a in BeautifulSoup(html, 'lxml').find_all('a', href=True):
        href = urllib.parse.urljoin(url, a['href']).split('#')[0]
        if (href not in seen and urllib.parse.urlparse(href).netloc == host and not href.lower().endswith('.pdf')
                and SUBPAGE.search(a.get_text(' ') + ' ' + href)):
            seen.add(href)
            pages.append((href, fetch_page(href)))
        if len(pages) >= 5:
            break
    return pages


def find_on_site(url, title):
    """Smallest block on the author's pages that contains the title; with its links."""
    from bs4 import BeautifulSoup
    words = [w for w in fold(title).split() if len(w) >= 4]
    if not words:
        return None
    best = None
    for page, html in site_pages(url):
        for el in BeautifulSoup(html, 'lxml').find_all(['li', 'p', 'div', 'tr', 'article', 'section', 'h3', 'h4']):
            text = el.get_text(' ', strip=True)
            if len(text) > 1500 or len(text) < len(title) * 0.8:
                continue
            body = ' ' + fold(text) + ' '
            if sum((' ' + w + ' ') in body for w in words) / len(words) >= 0.85:
                if best is None or len(text) < len(best['text']):
                    best = {'page': page, 'text': text, 'el': el}
    if not best:
        return None
    el = best.pop('el')
    # a heading alone holds the title but not the status or co-authors: widen to the enclosing block
    while len(best['text']) < len(title) * 1.5 and el.parent is not None and el.parent.name not in ('body', '[document]'):
        wider = el.parent.get_text(' ', strip=True)
        if len(wider) > 1500:
            break
        el, best['text'] = el.parent, wider
    best['links'] = [urllib.parse.urljoin(best['page'], a['href']) for a in el.find_all('a', href=True)]
    return best


# ---------- check ----------

def check_entry(e):
    title = delatex(e.get('title', ''))
    surnames = bib_surnames(e.get('author', ''))
    year = e.get('year', '').strip()
    venue = delatex(e.get('journal') or e.get('booktitle') or e.get('institution') or e.get('publisher') or '')
    is_wp = e['ENTRYTYPE'] in ('techreport', 'unpublished', 'misc') or bool(WP_WORDS.search(venue + ' ' + e.get('note', '')))
    flags, minor, w, source = [], [], None, 'OpenAlex'

    # working papers and entries without DOI: the authors' own pages first
    site_note, site_text = None, ''
    if is_wp or not e.get('doi'):
        known = [s for s in (site_for(x) for x in surnames) if s]
        for name, url in known:
            hit = find_on_site(url, title)
            if hit:
                site_text = hit['text']
                pdfs = [l for l in hit['links'] if '.pdf' in l.lower()]
                site_note = f'{name} site: "{hit["text"][:300]}"' + (f' PDF: {pdfs[0]}' if pdfs else '')
                break
        if known and not site_note:
            minor.append('not found on ' + ', '.join(n for n, _ in known) + ' site(s)')
        if not known:
            minor.append('no author site stored (' + ', '.join(surnames[:4]) + ')')

    if e.get('doi'):
        w = work_by_doi(e['doi'])
        if not w:
            flags.append(f'DOI {e["doi"]} not found in OpenAlex')
    cands = find(title, surnames[0] if surnames else None) if title else []
    if not w and cands and cands[0]['sim'] >= 0.85:
        w = cands[0]
    if not w:
        sch = cache_load('scholar').get(e['ID'])
        if sch:
            sc = sorted((parse_scholar(r) for r in sch['results']), key=lambda c: sim(title, c['title']), reverse=True)
            if sc and sim(title, sc[0]['title']) >= 0.85:
                w, source = sc[0], 'Scholar'
        if not w and site_note:
            return {'key': e['ID'], 'status': 'CHECK', 'source': 'Author site', 'notes': [site_note] + flags}
        if not w:
            short =' '.join(re.split(r'[:.?]', title)[0].split()[:12])
            q = f'"{short}" {surnames[0] if surnames else ""}'.strip()
            return {'key': e['ID'], 'status': 'NOT FOUND', 'source': '-', 'notes': flags, 'scholar_query': q}

    if sim(title, w['title']) < 0.95:
        flags.append(f'title differs: "{w["title"]}"')
    miss = [s for s in surnames if not surname_in(s, w['authors'])]
    if miss and w.get('truncated'):
        miss = []  # Scholar cut the author list
    if source == 'Scholar' and w.get('venue'):
        minor.append(f'Scholar lists: {w["venue"]} {w.get("year") or ""}'.strip())
    if miss:
        flags.append(f'author(s) {", ".join(miss)} not in {source} list ({", ".join(w["authors"][:6])})')
    elif source == 'OpenAlex' and len(w['authors']) > len(surnames) and 'others' not in e.get('author', ''):
        flags.append(f'{source} lists more authors: {", ".join(w["authors"])}')
    if year.isdigit():
        y = int(year)
        doi = e.get('doi') or (w.get('doi') if w.get('journal') and not is_wp else None)
        cr = crossref(doi) if doi and not re.match(r'10\.(3386|48550|2139)/', doi, re.I) else None
        cr_years = sorted({(cr.get(k) or {}).get('date-parts', [[None]])[0][0]
                           for k in ('published-print', 'published-online', 'issued', 'published')} - {None}) if cr else []
        if cr_years:
            if y not in cr_years:
                flags.append(f'year {year} vs {"/".join(map(str, cr_years))} (Crossref, print/online)')
        elif w.get('year') and w['year'] != y:
            msg = f'year {year} vs {w["year"]} ({w["venue"]})'
            if is_wp and y > w['year']:
                minor.append(f'OpenAlex has an earlier version ({w["year"]})')
            elif not is_wp and not w.get('journal'):
                minor.append(f'OpenAlex matched another version ({w["year"]}, {w["venue"] or w["type"]})')
            elif w.get('journal') and abs(w['year'] - y) == 1:
                minor.append(msg + ', likely online-first')
            else:
                flags.append(msg)
    if is_wp:
        pubs = [c for c in cands if c['sim'] >= 0.9 and c.get('journal')]
        if w.get('journal'):
            pubs.insert(0, w)
        if pubs:
            p = pubs[0]
            flags.append(f'published: {p["journal"]} {p["year"]}' + (f', doi:{p["doi"]}' if p.get('doi') else ''))
    elif e['ENTRYTYPE'] == 'article' and w.get('journal') and venue and sim(venue, w['journal']) < 0.8:
        flags.append(f'journal "{venue}" vs "{w["journal"]}"')
    if not e.get('doi') and w.get('doi') and w.get('journal') and not is_wp:
        flags.append(f'DOI available: {w["doi"]}')
    if site_note:
        # the author's page is the latest word on a working paper: its year beats OpenAlex
        if year and re.search(r'\b' + year + r'\b', site_text):
            minor += ['author site confirms ' + year + ' (' + f.split(' (')[0] + ')' for f in flags if f.startswith('year ')]
            flags = [f for f in flags if not f.startswith('year ')]
        minor.insert(0, site_note) if not flags else flags.insert(0, site_note)
    minor += ['style: ' + x for x in style_notes(e)]
    return {'key': e['ID'], 'status': 'CHECK' if flags else 'OK', 'source': source + (' + author site' if site_note else ''),
            'notes': flags + ['(minor) ' + m for m in minor], 'match': w['id']}


def cmd_check(a):
    entries = parse_bib(open(a.bib, encoding='utf-8', errors='replace').read())
    keys = {e['ID'] for e in entries}
    head = [f'# Reference check: {os.path.basename(a.bib)}', '', f'{len(entries)} entries in the .bib file.']
    if a.tex:
        cited = cited_keys(a.tex)
        missing = [k for k in cited if k not in keys]
        unused = [e['ID'] for e in entries if e['ID'] not in set(cited)]
        head += [f'{len(cited)} keys cited in the .tex file(s).', '']
        if missing:
            head.append('**Cited but not in the .bib:** ' + ', '.join(missing))
        if unused:
            head.append('**In the .bib but never cited:** ' + ', '.join(unused))
        if not a.all:
            entries = [e for e in entries if e['ID'] in set(cited)]
    if a.only:
        only = set(a.only.split(','))
        entries = [e for e in entries if e['ID'] in only]
    rows = []
    for i, e in enumerate(entries, 1):
        print(f'[{i}/{len(entries)}] {e["ID"]}', file=sys.stderr)
        rows.append(check_entry(e))
    order = {'NOT FOUND': 0, 'CHECK': 1, 'OK': 2}
    rows.sort(key=lambda r: order[r['status']])
    n = {s: sum(r['status'] == s for r in rows) for s in order}
    out = head + ['', f'Checked {len(rows)}: {n["OK"]} OK, {n["CHECK"]} to check, {n["NOT FOUND"]} not found.', '',
                  '| Key | Status | Source | Notes |', '|---|---|---|---|']
    for r in rows:
        notes = '; '.join(r['notes']).replace('|', '/') or ''
        if r['status'] == 'NOT FOUND':
            notes = (notes + '; ' if notes else '') + f'Scholar: `{r["scholar_query"]}`'
        out.append(f'| {r["key"]} | {r["status"]} | {r["source"]} | {notes} |')
    nf = [r for r in rows if r['status'] == 'NOT FOUND']
    if nf:
        out += ['', '## For Scholar (via Chrome)', '']
        out += [f'- {r["key"]}: {scholar_url(r["scholar_query"])}' for r in nf]
    text = '\n'.join(out) + '\n'
    if a.out:
        with open(a.out, 'w') as f:
            f.write(text)
        print(f'report written to {a.out}', file=sys.stderr)
    print(text)


# ---------- CLI ----------

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('search'); s.add_argument('query'); s.add_argument('-n', type=int, default=10)
    s = sp.add_parser('find'); s.add_argument('title'); s.add_argument('--author'); s.add_argument('-n', type=int, default=8)
    s = sp.add_parser('work'); s.add_argument('ref')
    s = sp.add_parser('cites'); s.add_argument('ref'); s.add_argument('-n', type=int, default=25)
    s = sp.add_parser('refs'); s.add_argument('ref')
    s = sp.add_parser('bib'); s.add_argument('ref')
    s = sp.add_parser('check'); s.add_argument('bib'); s.add_argument('--tex', nargs='*')
    s.add_argument('--all', action='store_true', help='with --tex: also check entries that are never cited')
    s.add_argument('--only', help='comma-separated keys'); s.add_argument('--out')
    s = sp.add_parser('scholar-add'); s.add_argument('key')
    s = sp.add_parser('site-add', help='store an author homepage'); s.add_argument('name'); s.add_argument('url')
    s = sp.add_parser('site', help='find a paper on an author homepage'); s.add_argument('name'); s.add_argument('title')
    sp.add_parser('sites', help='list stored author homepages')
    a = p.parse_args()

    if a.cmd == 'search':
        data = oa_get('/works', {'search': a.query, 'per_page': a.n})
        for w in data['results']:
            print(line(simplify(w)))
    elif a.cmd == 'find':
        for c in find(a.title, a.author, a.n):
            print(line(c) + f' [sim {c["sim"]}]')
    elif a.cmd == 'work':
        w = resolve(a.ref)
        print(json.dumps({k: v for k, v in w.items() if k != 'referenced_works'}, indent=1, ensure_ascii=False))
    elif a.cmd == 'cites':
        w = resolve(a.ref)
        print('Citing: ' + line(w))
        data = oa_get('/works', {'filter': 'cites:' + w['id'], 'sort': 'cited_by_count:desc', 'per_page': a.n}, fresh=True)
        print(f'{data["meta"]["count"]} citing works in OpenAlex; top {a.n}:')
        for x in data['results']:
            print('  ' + line(simplify(x)))
    elif a.cmd == 'refs':
        w = resolve(a.ref)
        ids = w['referenced_works']
        print(f'{len(ids)} references of: ' + line(w))
        for i in range(0, len(ids), 50):
            data = oa_get('/works', {'filter': 'openalex:' + '|'.join(ids[i:i + 50]), 'per_page': 50})
            for x in sorted(data['results'], key=lambda x: x.get('publication_year') or 0):
                print('  ' + line(simplify(x)))
    elif a.cmd == 'bib':
        print(bibtex_for(resolve(a.ref)))
    elif a.cmd == 'check':
        cmd_check(a)
    elif a.cmd == 'scholar-add':
        results = json.load(sys.stdin)
        cache = cache_load('scholar')
        cache[a.key] = {'t': time.time(), 'results': results}
        cache_save('scholar')
        for r in results:
            print(line(parse_scholar(r)))
    elif a.cmd == 'site-add':
        cache_load('sites')[a.name] = a.url
        cache_save('sites')
        print(f'stored: {a.name} -> {a.url}; subpages: ' + ', '.join(u for u, _ in site_pages(a.url)[1:]))
    elif a.cmd == 'sites':
        for name, url in sorted(cache_load('sites').items()):
            print(f'{name}: {url}')
    elif a.cmd == 'site':
        s = site_for(a.name)
        if not s:
            sys.exit(f'no homepage stored for {a.name}; add one with site-add')
        hit = find_on_site(s[1], a.title)
        if not hit:
            sys.exit(f'not found on {s[1]} (pages: ' + ', '.join(u for u, _ in site_pages(s[1])) + ')')
        print(f'{hit["page"]}\n{hit["text"]}\nlinks: ' + '\n       '.join(hit['links']))


if __name__ == '__main__':
    main()
