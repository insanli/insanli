#!/usr/bin/env python3
"""Build www.insanlik.tr: the start page, the Reports (Raporlar) section and the Projects pages.

Reads content/ and templates/, writes the finished site to _site/.
GitHub runs this automatically after every change (.github/workflows/deploy.yml).
Local test:  pip install -r requirements.txt && python build.py
"""
import glob
import os
import re
import shutil
import zipfile
import sys

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, 'content')
OUT = os.path.join(ROOT, '_site')
MONTHS = {
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    'tr': ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
    'ar': ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'],
}
errors = []


def read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        errors.append(f'{os.path.relpath(path, ROOT)}: could not be read ({e}). Check colons, quotes and indentation.')
        return {}


def fmt_period(value, lang):
    m = re.match(r'(\d{4})-(\d{1,2})', str(value or ''))
    return f'{MONTHS[lang][int(m.group(2)) - 1]} {m.group(1)}' if m else str(value or '')


def fmt_date(value, lang):
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(value or ''))
    return f'{int(m.group(3))} {MONTHS[lang][int(m.group(2)) - 1]} {m.group(1)}' if m else str(value or '')


def main():
    S = read(os.path.join(CONTENT, 'settings.yml'))
    langs = S.get('languages', ['tr', 'en', 'ar'])
    cats = S.get('categories', ['country', 'sectoral', 'needs', 'emergency', 'data'])
    T = {l: read(os.path.join(CONTENT, 'text', f'{l}.yml')) for l in langs}
    impact = read(os.path.join(CONTENT, 'data', 'impact.yml'))
    reports = []
    for p in sorted(glob.glob(os.path.join(CONTENT, 'reports', '*.yml'))):
        name = os.path.basename(p)[:-4]
        if name.startswith('_'):
            continue
        r = read(p)
        rel = os.path.relpath(p, ROOT)
        if not r or r.get('draft'):
            continue
        if r.get('category') not in cats or r.get('category') == 'data':
            errors.append(f'{rel}: "category:" must be one of: country, sectoral, needs, emergency')
            continue
        for l in langs:
            if not (r.get(l) or {}).get('title'):
                errors.append(f'{rel}: the "{l}" part has no title.')
        if r.get('image') and not os.path.exists(os.path.join(ROOT, 'static', r['image'].lstrip('/'))):
            errors.append(f'{rel}: image "{r["image"]}" not found. Upload it to static{r["image"]}')
        r['slug'] = name
        reports.append(r)
    if errors:
        report()
    reports.sort(key=lambda r: (str(r.get('updated') or r.get('period') or ''), -(r.get('order') or 0)), reverse=True)

    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, 'templates')), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.globals['S'] = S
    env.globals['cats'] = cats
    env.filters['period'] = fmt_period
    env.filters['date'] = fmt_date
    env.filters['loc'] = lambda v, lang='en': str(v).replace(',', '.') if lang == 'tr' and str(v).replace(',', '').isdigit() else v
    env.filters['num'] = lambda n, lang='en': f'{n:,}'.replace(',', '.' if lang == 'tr' else ',')

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, 'static'), OUT)
    # project pages (built earlier from the Zoho portfolio): copied, with the Projects top bar put in
    has_projects = True
    if os.path.isdir(os.path.join(ROOT, 'portfolio')):
        shutil.copytree(os.path.join(ROOT, 'portfolio'), OUT, dirs_exist_ok=True)
    elif os.path.exists(os.path.join(ROOT, 'portfolio.zip')):
        with zipfile.ZipFile(os.path.join(ROOT, 'portfolio.zip')) as z:
            z.extractall(OUT)
    else:
        has_projects = False
    if has_projects:
        hdr_tpl = env.get_template('proj_header.html')
        WC = read(os.path.join(CONTENT, 'women-children.yml'))
        for l in langs:
            for f in glob.glob(os.path.join(OUT, l, '**', '*.html'), recursive=True):
                html = open(f, encoding='utf-8').read()
                m = re.search(r'<header class="hdr" id="top">.*?</header>', html, re.S)
                if not m:
                    continue
                alt = {lg: href for href, lg in re.findall(r'<a href="([^"]+)" hreflang="(\w\w)"', m.group(0))}
                alt = {lg: alt.get(lg, f'/{lg}/projects/') for lg in langs}
                section = os.path.relpath(f, os.path.join(OUT, l)).split(os.sep)[0]
                section = {'kits': 'quick-funding', 'about': '', 'achievements': ''}.get(section, section)
                new = hdr_tpl.render(lang=l, t=T[l], T=T, langs=langs, alt=alt, section=section)
                html = html[:m.start()] + new + html[m.end():]
                html = html.replace('/img/brand/logo-ar.png', '/img/brand/logo-en.png')
                # same photo banner as the Reports pages
                html = html.replace('<section class="phero "', f'<section class="phero has-img" style="--bg:url(\'{S.get("projects_image", "")}\')"')
                if WC.get('wash_label', {}).get(l):
                    html = html.replace('>WASH<', '>' + WC['wash_label'][l] + '<')
                if section == 'projects' and f.endswith(os.path.join('projects', 'index.html')):
                    label = (WC.get('label') or {}).get(l, 'Women & Children')
                    html = re.sub(r'(<select data-filter="sector">.*?)(</select>)', lambda mm: mm.group(1) + f'<option value="women-children">{label}</option>' + mm.group(2), html, count=1, flags=re.S)
                    for code in WC.get('projects', []):
                        html = html.replace(f'<a class="pcard" href="/{l}/projects/{code}/"', f'<a class="pcard" data-groups="women-children" href="/{l}/projects/{code}/"')
                with open(f, 'w', encoding='utf-8') as fh:
                    fh.write(html)

    pages, refs = [], {}
    for l in langs:
        t = T[l]
        R = []
        for r in reports:
            x = {k: v for k, v in r.items() if k not in langs}
            x.update(r.get(l) or r.get('en') or {})
            x['url'] = f'/{l}/reports/{r["category"]}/{r["slug"]}/'
            R.append(x)
        imp = dict(impact.get(l) or {})
        base = dict(lang=l, t=t, dir='rtl' if l == 'ar' else 'ltr', langs=langs, T=T, reports=R,
                    contact=(S.get('contacts') or {}).get(l, {}))

        def add(tpl, url, ref, **kw):
            pages.append((tpl, url, ref, dict(base, **kw)))
            refs.setdefault(ref, {})[l] = url

        add('landing.html', f'/{l}/', 'home')
        add('reports_home.html', f'/{l}/reports/', 'reports')
        for c in cats:
            if c == 'data':
                add('data.html', f'/{l}/reports/data/', 'reports/data', imp=imp,
                    country_reports=[r for r in R if r['category'] == 'country'])
            elif c == 'needs':
                add('needs.html', f'/{l}/reports/needs/', 'reports/needs', items=[r for r in R if r['category'] == 'needs'],
                    country_reports=[r for r in R if r['category'] == 'country'])
            else:
                add('report_list.html', f'/{l}/reports/{c}/', f'reports/{c}', cat=c, items=[r for r in R if r['category'] == c])
        for r in R:
            add('report.html', r['url'], 'reports/' + r['slug'], r=r,
                more=[x for x in R if x['category'] == r['category'] and x['slug'] != r['slug']][:3])

    for tpl, url, ref, ctx in pages:
        alt = {ll: refs.get(ref, {}).get(ll) or f'/{ll}/' for ll in langs}
        write(url, env.get_template(tpl).render(**ctx, alt=alt, ref=ref, page_url=url))
    write('/', env.get_template('root.html').render(langs=langs, default=S.get('default_lang', 'tr'), T=T))
    base_url = S.get('url', '').rstrip('/')
    urls = [p[1] for p in pages] + sorted('/' + os.path.relpath(os.path.dirname(f), OUT).replace(os.sep, '/') + '/'
                                          for f in glob.glob(os.path.join(OUT, '*', '**', 'index.html'), recursive=True)
                                          if '/reports/' not in f and os.path.dirname(os.path.dirname(f)) != OUT)
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f'  <url><loc>{base_url}{u}</loc></url>' for u in dict.fromkeys(urls)]
    write('/sitemap.xml', '\n'.join(sm + ['</urlset>']) + '\n')
    write('/robots.txt', f'User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n')
    # cache-busting: browsers fetch the new CSS/JS/logos after every change
    import hashlib
    ver = {u: hashlib.md5(open(os.path.join(OUT, u.lstrip('/')), 'rb').read()).hexdigest()[:8]
           for u in ['/css/style.css', '/js/main.js'] + ['/img/brand/' + n for n in os.listdir(os.path.join(OUT, 'img', 'brand')) if n.endswith('.png')]}
    for f in glob.glob(os.path.join(OUT, '**', '*.html'), recursive=True):
        html = open(f, encoding='utf-8').read()
        new = re.sub(r'(["\'(])(' + '|'.join(re.escape(u) for u in ver) + r')(?=["\')])', lambda mm: mm.group(1) + mm.group(2) + '?v=' + ver[mm.group(2)], html)
        if new != html:
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(new)
    print(f'Built {len(pages)} report pages (+ project pages) into _site/')


def write(url, content):
    path = url.lstrip('/')
    if path == '' or path.endswith('/'):
        path += 'index.html'
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content)


def report():
    print('\nThe site was NOT updated because of these problems:\n', file=sys.stderr)
    for e in errors:
        print('  - ' + e, file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    main()
