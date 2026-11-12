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


def localize_prices(html, lang):
    """$4.50 -> $4,50 ; $2,250 -> $2.250 ; $9870.00 -> $9.870,00 (English digits in every language)."""
    def one(m):
        raw = m.group(2).replace(',', '')
        whole, _, dec = raw.partition('.')
        out = f'{int(whole):,}'.replace(',', '.') + (',' + dec if dec else '')
        return (m.group(1) or '') + out
    return re.sub(r'(\$)?(\d[\d,]*(?:\.\d+)?)(?(1)|(?=\s?\$))', one, html)


# Gaza "Food Security" table: (price now on the site, new price), in the order they appear on the page:
# unit cost, then "funding from" for GAZ-I001, I002, I003, I004, I005, I006, I007, I071, I072, I073, I074
GAZA_FOOD = [
    (4.5, '5.50'), (2250, '2,750'),
    (220, '245.00'), (1320, '1,470'),
    (165, '165.00'), (990, '990'),
    (20, '30.00'), (4000, '6,000'),
    (2.2, '2.20'), (2200, '2,200'),
    (33, '47.00'), (3300, '4,700'),
    (50, '60.00'), (5000, '6,000'),
    (9870, '10,164.00'), (9870, '10,000'),      # "funding from" rounded (Excel update, 7 Nov 2026)
    (39600, '43,560.00'), (39600, '43,500'),
    (7770, '6,930.00'), (7770, '6,900'),
    (30600, '29,700.00'), (30600, '29,500'),
]

# Other rows of the Gaza page: code -> (unit cost, funding from)
GAZA_ROWS = {
    'GAZ-I082': ('34.00', '34'),   # Hygiene & Personal Care Kit: new contents (see GAZA_KITS) cost $34
}

# Gaza aid packages, "View contents" pages (Excel update, 7 Nov 2026).
# Totals are the Excel totals; unit price = row total / quantity, so every row and the package total add up.
GAZA_KITS = {
    # Vegetable Basket: whole list replaced. (Turkish, English, Arabic name), size, unit, quantity, unit price
    'gaz-i006': {'total': 47, 'rows': [
        (('Havuç', 'Carrot', 'جزر'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 3.50),
        (('Limon', 'Lemons', 'ليمون'), ('1', '1', '1'), ('PAKET', 'PACK', 'عبوة'), 1, 3.50),
        (('Portakal', 'Oranges', 'برتقال'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 4.40),
        (('Elma', 'Apples', 'تفاح'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 5.40),
        (('Sarımsak', 'Garlic', 'ثوم'), ('1', '1', '1'), ('PAKET', 'PACK', 'عبوة'), 1, 2.00),
        (('Yeşil biber', 'Green Peppers', 'فلفل أخضر'), ('250 G', '250 G', '250 G'), ('G', 'G', 'G'), 1, 2.40),
        (('Salatalık', 'Cucumbers', 'خيار'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 4.40),
        (('Patlıcan', 'Eggplant', 'باذنجان'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 4.40),
        (('Soğan', 'Onions', 'بصل'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 3.00),
        (('Domates', 'Tomatoes', 'بندورة'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 2, 5.50),
        (('Patates', 'Potatoes', 'بطاطا'), ('1 KG', '1 KG', '1 كغ'), ('KG', 'KG', 'كغ'), 1, 3.00),
    ]},
    # Food Parcel and Hygiene Kit: same items and quantities as before, new unit prices (in page order)
    'gaz-i007': {'total': 60, 'prices': [2.55, 1.80, 1.65, 1.75, 1.25, 2.30, 11.00, 1.10, 1.10, 1.10,
                                         3.65, 2.25, 4.50, 2.75, 2.60, 1.10, 3.70]},
    'gaz-i082': {'total': 34, 'prices': [3.20, 1.15, 1.80, 4.40, 0.675, 2.75, 0.50, 1.50, 4.50, 4.50]},
}
REGION_ORDER = []   # filled from settings.yml (region_order) when the build starts


def region_pos(slug):
    """Place of a region in the top-bar menus (settings.yml region_order); regions not in the list go last."""
    return REGION_ORDER.index(slug) if slug in REGION_ORDER else len(REGION_ORDER)


def by_region(items, attr='country'):
    """Template filter: the same list in region order (the order of everything else stays as it was)."""
    get = lambda x: x.get(attr) if isinstance(x, dict) else getattr(x, attr, None)
    return sorted(items, key=lambda x: region_pos(get(x)))


LANG_INDEX = {'tr': 0, 'en': 1, 'ar': 2}


def money(v):
    """3.5 -> '3.50', 0.675 -> '0.68' (two decimals, the page's own format; localize_prices adds the comma later)."""
    from decimal import Decimal, ROUND_HALF_UP
    return str(Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def set_row_prices(html, code, unit, funding):
    """In the table row of one intervention, write the unit cost (first amount) and funding from (last amount)."""
    def row(m):
        s = m.group(0)
        a = list(re.finditer(r'<strong>\$[\d.,]+</strong>', s))
        if len(a) != 2:
            return s
        return s[:a[0].start()] + f'<strong>${unit}</strong>' + s[a[0].end():a[1].start()] + f'<strong>${funding}</strong>' + s[a[1].end():]
    return re.subn(r'<tr id="%s">.*?</tr>' % re.escape(code), row, html, count=1, flags=re.S)


def update_kit(html, lang, kit):
    """Rewrite the contents table of an aid package page, its total and the price at the top. Returns (html, ok)."""
    m = re.search(r'(<tbody>)(.*?)(</tbody>)', html, re.S)
    if not m:
        return html, False
    old_rows = re.findall(r'<tr>.*?</tr>', m.group(2), re.S)
    new_rows, total = [], 0
    if 'rows' in kit:
        i = LANG_INDEX[lang]
        for names, size, unit, qty, price in kit['rows']:
            total += qty * price
            new_rows.append(f'<tr><td>{names[i]}</td><td>{size[i]}</td><td>{unit[i]}</td><td>{qty}</td>'
                            f'<td class="num">${money(price)}</td><td class="num">${money(qty * price)}</td></tr>')
    else:
        if len(old_rows) != len(kit['prices']):
            return html, False
        for r, price in zip(old_rows, kit['prices']):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
            qty = int(cells[3])
            total += qty * price
            new_rows.append(re.sub(r'<td class="num">\$[\d.,]+</td><td class="num">\$[\d.,]+</td>',
                                   f'<td class="num">${money(price)}</td><td class="num">${money(qty * price)}</td>', r, count=1))
    if abs(total - kit['total']) > 0.001:
        return html, False
    html = html[:m.start(2)] + '\n' + ''.join(new_rows) + html[m.end(2):]
    html = re.sub(r'(<tfoot>.*?<td class="num">)\$[\d.,]+(</td>)', r'\g<1>$' + money(total) + r'\g<2>', html, count=1, flags=re.S)
    html = re.sub(r'(<div class="kit-price">.*?<strong>)\$[\d.,]+(</strong>)', r'\g<1>$' + money(total) + r'\g<2>', html, count=1, flags=re.S)
    return html, True

# Sentence shown under the title of the Gaza quick-funding page (replaces the old sentence)
HERO_TEXT = {
    'tr': 'Gıda Güvenliği • Su, Sanitasyon ve Hijyen • Sağlık • Barınma ve Temel İhtiyaç Malzemeleri • Eğitim ve Toplum Hizmetleri',
    'en': 'Food Security • Water, Sanitation and Hygiene • Health • Shelter and Basic Needs Supplies • Education and Community Services',
    'ar': 'الأمن الغذائي • المياه والصرف الصحي والنظافة • الصحة • المأوى والمستلزمات الأساسية • التعليم والخدمات المجتمعية',
}


def replace_hero_text(html, lang):
    """Replace the intro sentence under the page title (the first <p> right after the first </h1>)."""
    return re.subn(r'(</h1>(?:(?!<h[12][\s>]|<p[\s>]|</section).)*?<p(?:\s[^>]*)?>)[^<]{10,400}(</p>)',
                   lambda m: m.group(1) + HERO_TEXT[lang] + m.group(2), html, count=1, flags=re.S)


def override_prices(html, pairs):
    """Go through the $ amounts in page order. When an amount equals the next expected old price, write the new one."""
    state = [0]

    def one(m):
        if state[0] >= len(pairs):
            return m.group(0)
        s = m.group(1)
        v = float(s.replace('.', '') if re.fullmatch(r'\d{1,3}(?:\.\d{3})+', s) else s.replace(',', ''))
        old, new = pairs[state[0]]
        if abs(v - old) < 0.001:
            state[0] += 1
            return '$' + new
        return m.group(0)
    out = re.sub(r'\$(\d[\d,.]*\d|\d)', one, html)
    return out, state[0]


# Dollar sign after the amount on every page: $28.350 -> 28.350 $ ; $2.57 billion -> 2.57 billion $.
# Done last, so all price rules above still work on the original "$28.350" form.
# Arabic pages: invisible left-to-right marks keep the $ on the right of the number (instead of jumping to the left).
DOLLAR = re.compile(r'(?<![\w$])\$(\d(?:[\d.,]*\d)?)(\s(?:million|billion|thousand|trillion)\b)?')


def dollar_right(html, lang):
    def one(m):
        out = m.group(1) + (m.group(2) or '') + ' $'
        return '‎' + out + '‎' if lang == 'ar' else out
    parts = re.split(r'(<script\b.*?</script>|<style\b.*?</style>)', html, flags=re.S)
    return ''.join(p if p.startswith(('<script', '<style')) else DOLLAR.sub(one, p) for p in parts)


# Gaza Quick Funding (Acil Müdahaleler) page and its "View contents" pages, from content/gaza-quick-funding.yml:
# every number is written exactly as the Excel file shows it (no dots/commas swapped, no cents added).
def gaza_rows(html, lang, G):
    """Write unit cost, unit, recommended minimum and funding from of every row. Returns (html, rows written)."""
    from html import escape
    i, done = LANG_INDEX[lang], 0
    pick = lambda r, k: (r.get(k) or [None, None, None])[i]
    for r in G.get('rows', []):
        m = re.search(r'(<tr id="%s">)(.*?)(</tr>)' % re.escape(r['code']), html, re.S)
        if not m:
            continue
        tds = re.findall(r'(<td[^>]*>)(.*?)(</td>)', m.group(2), re.S)
        if len(tds) != 4:
            continue
        cells = [list(t) for t in tds]
        if pick(r, 'title'):
            cells[0][1] = re.sub(r'(<strong class="qtitle">).*?(</strong>)', lambda k: k.group(1) + escape(pick(r, 'title')) + k.group(2), cells[0][1], count=1, flags=re.S)
        cells[1][1] = re.sub(r'<strong>\$[\d.,]+</strong>', lambda k: f'<strong>${r["price"]}</strong>', cells[1][1], count=1)
        if pick(r, 'unit'):
            cells[1][1] = re.sub(r'(<span class="qunit">).*?(</span>)', lambda k: k.group(1) + escape(pick(r, 'unit')) + k.group(2), cells[1][1], count=1, flags=re.S)
        old_unit = re.sub(r'^\s*[\d.,]+\s*', '', cells[2][1]).strip()
        cells[2][1] = f'{r["min"]} ' + (escape(pick(r, 'min_unit')) if pick(r, 'min_unit') else old_unit)
        cells[3][1] = re.sub(r'<strong>\$[\d.,]+</strong>', lambda k: f'<strong>${r["funding"]}</strong>', cells[3][1], count=1)
        if r.get('thousand') and lang == 'tr':      # "1.000 Litre" is written "1,000" in the file
            for c in cells[:3]:
                c[1] = c[1].replace('1.000', '1,000')
        inner = m.group(2)
        for (o, old, c), new in zip(tds, cells):
            inner = inner.replace(o + old + c, o + new[1] + c, 1)
        html = html[:m.start(2)] + inner + html[m.end(2):]
        done += 1
    return html, done


def gaza_kit(html, lang, kit):
    """Rewrite the contents table, its total, the price at the top (and the intro / title when given). Returns (html, ok)."""
    from html import escape
    i = LANG_INDEX[lang]
    if not re.search(r'<tbody>.*?</tbody>', html, re.S):
        return html, False
    rows = ''.join(f'<tr><td>{escape(n[i])}</td><td>{escape(sz[i])}</td><td>{escape(u[i])}</td><td>{q}</td>'
                   f'<td class="num">${p}</td><td class="num">${t}</td></tr>' for n, sz, u, q, p, t in kit['items'])
    html = re.sub(r'(<tbody>).*?(\s*</tbody>)', lambda m: m.group(1) + '\n' + rows + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(<tfoot>.*?<td class="num">)\$[\d.,]+(</td>)', lambda m: m.group(1) + '$' + kit['total'] + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(<div class="kit-price">.*?<strong>)\$[\d.,]+(</strong>)', lambda m: m.group(1) + '$' + kit['price'] + m.group(2), html, count=1, flags=re.S)
    if (kit.get('lead') or [None] * 3)[i]:
        html = re.sub(r'(<p class="lead">).*?(</p>)', lambda m: m.group(1) + escape(kit['lead'][i]) + m.group(2), html, count=1, flags=re.S)
    if (kit.get('title') or [None] * 3)[i]:
        old = re.search(r'<h1>(.*?)</h1>', html, re.S).group(1)
        html = html.replace(old, escape(kit['title'][i]))
    return html, True


# Yemen Quick Funding page: extra rows and "View contents" pages from content/yemen-quick-funding.yml
def yemen_amount(v, whole=False):
    """Written like the existing Yemen rows: unit cost $6600.00, funding from $6,600 (thousands get dots later)."""
    from decimal import Decimal, ROUND_HALF_UP
    d = Decimal(str(v))
    if not whole:
        return f'{d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}'
    if d >= 1000 or d == d.to_integral_value():
        return f'{int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)):,}'
    return f'{d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}'


def yemen_rows(html, lang, Y):
    """Add the rows at the end of their table (sector). Returns (html, rows added)."""
    from html import escape
    i = LANG_INDEX[lang]
    lab = Y.get('labels', {})
    link = re.search(r'<a class="tbl-link" href="/%s/kits/yem-qi-049/">.*?</a>' % lang, html, re.S)
    added = 0
    for r in Y.get('rows', []):
        if f'<tr id="{r["code"]}">' in html:
            continue
        lines = []
        if r.get('details'):
            lines.append(escape(r['details'][i]))
        extra = [escape(r['place'][i])] if r.get('place') else []
        if r.get('beneficiaries'):
            extra.append(escape(lab['beneficiaries'][i] + r['beneficiaries'][i]))
        if r.get('duration'):
            extra.append(escape(lab['duration'][i] + r['duration'][i]))
        if extra:
            lines.append(' · '.join(extra))
        notes = ''.join(f'<span class="qnote">{x}</span>' for x in lines)
        kit = link.group(0).replace('yem-qi-049', r['kit']) if r.get('kit') and link else ''
        row = (f'          <tr id="{r["code"]}">\n'
               f'            <td><span class="pcard-code">{r["code"]}</span><strong class="qtitle">{escape(r["title"][i])}</strong>\n{notes}{kit}</td>\n'
               f'            <td class="num"><strong>${yemen_amount(r["price"])}</strong><span class="qunit">{escape(r["unit"][i])}</span></td>\n'
               f'            <td>{escape((r.get("min") or lab["flexible"])[i])}</td>\n'
               f'            <td class="num"><strong>${yemen_amount(r.get("funding", r["price"]), whole=True)}</strong></td>\n'
               f'          </tr>\n')
        m = re.search(r'<div class="qcat" id="%s">.*?(\s*</tbody>)' % re.escape(r['sector']), html, re.S)
        if not m:
            continue
        html = html[:m.start(1)] + '\n' + row.rstrip('\n') + html[m.start(1):]
        added += 1
    return html, added


def yemen_kits(Y, langs):
    """Create the "View contents" pages, copied from the YEM-QI-049 page in each language."""
    from html import escape, unescape
    made = 0
    for l in langs:
        src = os.path.join(OUT, l, 'kits', 'yem-qi-049', 'index.html')
        if not os.path.exists(src):
            continue
        base = open(src, encoding='utf-8').read()
        old_title = re.search(r'<h1>(.*?)</h1>', base, re.S).group(1)
        old_lead = re.search(r'<p class="lead">(.*?)</p>', base, re.S).group(1)
        i = LANG_INDEX[l]
        for k in Y.get('kits', []):
            row = next(r for r in Y['rows'] if r['code'] == k['code'])
            html = base.replace('yem-qi-049', k['slug']).replace('YEM-QI-049', k['code'])
            html = html.replace(old_title, escape(row['title'][i])).replace(old_lead, escape(k['lead'][i]))
            if unescape(old_lead) != old_lead:
                html = html.replace(unescape(old_lead), escape(k['lead'][i]))
            rows = []
            for names, size, unit, qty, price in k['items']:
                q = f'{qty:g}'.replace('.', ',') if l == 'tr' else f'{qty:g}'
                p = (f'${yemen_amount(price)}', f'${yemen_amount(qty * price)}') if price is not None else ('—', '—')
                rows.append(f'<tr><td>{escape(names[i])}</td><td>{escape(size[i])}</td><td>{escape(unit[i])}</td><td>{q}</td>'
                            f'<td class="num">{p[0]}</td><td class="num">{p[1]}</td></tr>')
            html = re.sub(r'(<tbody>).*?(\s*</tbody>)', lambda m: m.group(1) + '\n' + ''.join(rows) + m.group(2), html, count=1, flags=re.S)
            total = f'${yemen_amount(k["total"])}'
            html = re.sub(r'(<tfoot>.*?<td class="num">)\$[\d.,]+(</td>)', lambda m: m.group(1) + total + m.group(2), html, count=1, flags=re.S)
            html = re.sub(r'(<div class="kit-price"><span class="small-label">).*?(</span><strong>)\$[\d.,]+(</strong>)',
                          lambda m: m.group(1) + escape(k['label'][i]) + m.group(2) + total + m.group(3), html, count=1, flags=re.S)
            os.makedirs(os.path.join(OUT, l, 'kits', k['slug']), exist_ok=True)
            with open(os.path.join(OUT, l, 'kits', k['slug'], 'index.html'), 'w', encoding='utf-8') as fh:
                fh.write(html)
            made += 1
    return made


# Project cards (Projects list, country pages, "related projects"): the short description is shown
# only on the project's own page; the cards show its Target Beneficiaries and Duration instead,
# copied from the figures strip at the top of that page (so they are always the same, in every language).
FACT_LABELS = {
    'beneficiaries': ('Target Beneficiaries', 'Hedef Faydalanıcı', 'المستفيدون المستهدفون'),
    'duration': ('Duration', 'Süre', 'مدة التنفيذ'),
}
FACT_ICONS = {
    'beneficiaries': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    'duration': '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
}
# small grey line under a number that only repeats the label ("3000 · target beneficiaries") is left off the card
FACT_PLAIN_NOTES = ('target beneficiaries', 'hedef faydalanıcı', 'مستفيداً مستهدفاً')
# not filled in yet on the project page: the card shows nothing for it until it is
FACT_PLACEHOLDERS = ('TO BE ADDED', 'EKLENECEK', 'سيُضاف')


def project_facts(lang):
    """{project code: [(kind, label, value, note), ...]} read from each project page of one language."""
    facts = {}
    for f in glob.glob(os.path.join(OUT, lang, 'projects', '*', 'index.html')):
        code = os.path.basename(os.path.dirname(f))
        m = re.search(r'<section class="stats-strip">(.*?)</section>', open(f, encoding='utf-8').read(), re.S)
        if not m:
            continue
        found = {}
        for st in re.findall(r'<div class="st">(.*?)</div>', m.group(1), re.S):
            label = re.search(r'<span class="small-label">(.*?)</span>', st, re.S)
            value = re.search(r'<strong>(.*?)</strong>', st, re.S)
            note = re.search(r'<span class="st-note">(.*?)</span>', st, re.S)
            if not (label and value):
                continue
            label, value, note = label.group(1).strip(), value.group(1).strip(), (note.group(1).strip() if note else '')
            kind = next((k for k, names in FACT_LABELS.items() if label in names), None)
            if not kind or not value or value in FACT_PLACEHOLDERS:
                continue
            if not value[:1].isdigit() or note.lower() in FACT_PLAIN_NOTES:
                note = ''
            found[kind] = (kind, label, value, note)
        facts[code] = [found[k] for k in FACT_LABELS if k in found]
    return facts


def facts_html(rows):
    out = []
    for kind, label, value, note in rows:
        icon = ('<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + FACT_ICONS[kind] + '</svg>')
        val = f'<strong>{value}</strong>' + (f' <span class="pcard-fact-note">{note}</span>' if note else '')
        out.append(f'<div class="pcard-fact pcard-fact-{kind}">{icon}<div><span class="small-label">{label}</span>'
                   f'<span class="pcard-fact-val">{val}</span></div></div>')
    return '<div class="pcard-facts">' + ''.join(out) + '</div>' if out else ''


def cards_with_facts(html, lang, facts):
    """Every project card on the page: description out, beneficiaries + duration in. Returns (html, cards changed)."""
    n = [0]

    def card(m):
        rows = facts.get(m.group(2))
        if rows is None:
            print(f'  note: no project page found for card {m.group(2)} ({lang})')
        body, k = re.subn(r'<p class="pcard-text">.*?</p>', lambda _: facts_html(rows or []), m.group(3), count=1, flags=re.S)
        n[0] += k
        return m.group(1) + body + '</a>'
    out = re.sub(r'(<a class="pcard"[^>]*\bhref="/%s/projects/([^/"]+)/"[^>]*>)(.*?)</a>' % lang, card, html, flags=re.S)
    return out, n[0]


def home_nav(lang, t, areas):
    """Start page top bar: the same headings as the Projects top bar; each one opens the main contents of its page.
    Read from the project pages already written to _site (so titles and links are always the current ones)."""
    import html as H

    def page(name):
        f = os.path.join(OUT, lang, name, 'index.html')
        return open(f, encoding='utf-8').read() if os.path.exists(f) else ''

    def txt(v):
        return H.unescape(re.sub(r'<[^>]+>', '', v)).strip()
    slug = {a['title']: a['url'].rstrip('/').split('/')[-1] for a in areas}
    kids = {'areas': [dict(title=a['title'], url=a['url']) for a in areas]}
    sel = re.search(r'<select data-filter="sector">(.*?)</select>', page('projects'), re.S)
    kids['projects'] = [dict(title=txt(n), url=f'/{lang}/projects/?sector={v}') for v, n in
                        re.findall(r'<option value="([^"]+)">([^<]*)</option>', sel.group(1))] if sel else []
    kids['seasonal'] = [dict(title=txt(n), url=u) for u, n in re.findall(
        r'<a class="ccard" href="(/%s/seasonal/[^"]+/)">.*?<h3[^>]*>(.*?)</h3>' % lang, page('seasonal'), re.S)]
    kids['quick-funding'] = [dict(title=txt(n), url=u) for u, n in re.findall(
        r'<a class="tile[^"]*" href="(/%s/quick-funding/[^"]+/)"[^>]*>\s*<span class="tile-name">([^<]+)</span>' % lang,
        page('quick-funding'), re.S)]
    # Yetim Destek: one entry per country card; each card gets an id so the link goes straight to it
    f = os.path.join(OUT, lang, 'orphan-sponsorship', 'index.html')
    kids['orphan-sponsorship'] = []
    if os.path.exists(f):
        src = open(f, encoding='utf-8').read()

        def card(m):
            name = txt(m.group(2))
            sid = slug.get(name)
            if not sid:
                return m.group(0)
            kids['orphan-sponsorship'].append(dict(title=name, url=f'/{lang}/orphan-sponsorship/#{sid}'))
            return f'<div class="ocard orphan-card" id="{sid}">' + m.group(1)
        src = re.sub(r'<div class="ocard orphan-card">(\s*<h3 class="bar-title">(.*?)</h3>)', card, src, flags=re.S)
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(src)
    for k in ('quick-funding', 'orphan-sponsorship'):   # regions: same order as in the other menus
        kids[k].sort(key=lambda c: region_pos(c['url'].rstrip('/').split('/')[-1].lstrip('#').split('#')[-1]))
    out = []
    for it in t.get('projects_nav') or []:
        k = kids.get(it['page']) or []
        out.append(dict(title=it['title'], url=f"/{lang}/{it['page']}/", children=k, drop=bool(k), all=t.get('all')))
    return out


def main():
    S = read(os.path.join(CONTENT, 'settings.yml'))
    REGION_ORDER[:] = S.get('region_order') or []
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
    env.filters['by_region'] = by_region
    env.filters['date'] = fmt_date
    env.filters['loc'] = lambda v, lang='en': str(v).replace(',', '.') if lang == 'tr' and str(v).replace(',', '').isdigit() else v
    env.filters['num'] = lambda n, lang='en': f'{n:,}'.replace(',', '.' if lang == 'tr' else ',')

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, 'static'), OUT)
    # project pages (built earlier from the Zoho portfolio): copied, with the Projects top bar put in
    has_projects = True
    HN = {}  # start page top bar: the Projects headings and the main contents of each
    if os.path.isdir(os.path.join(ROOT, 'portfolio')):
        shutil.copytree(os.path.join(ROOT, 'portfolio'), OUT, dirs_exist_ok=True)
    elif os.path.exists(os.path.join(ROOT, 'portfolio.zip')):
        with zipfile.ZipFile(os.path.join(ROOT, 'portfolio.zip')) as z:
            z.extractall(OUT)
    else:
        has_projects = False
    YQ = read(os.path.join(CONTENT, 'yemen-quick-funding.yml')) if os.path.exists(os.path.join(CONTENT, 'yemen-quick-funding.yml')) else {}
    GQ = read(os.path.join(CONTENT, 'gaza-quick-funding.yml')) if os.path.exists(os.path.join(CONTENT, 'gaza-quick-funding.yml')) else {}
    if has_projects:
        if YQ:
            print(f'YEMEN: {yemen_kits(YQ, langs)} "View contents" pages made')
        hdr_tpl = env.get_template('proj_header.html')
        WC = read(os.path.join(CONTENT, 'women-children.yml'))
        for l in langs:
            facts = project_facts(l)
            cards_done = 0
            areas = []
            ai = os.path.join(OUT, l, 'areas', 'index.html')
            if os.path.exists(ai):
                areas = [dict(url=u.replace('/areas//', '/areas/africa/'), title=n.strip()) for u, n in re.findall(
                    r'<a class="tile[^"]*" href="(/%s/areas/[^"]*)"[^>]*>(?:(?!</a>).)*?<span class="tile-name">([^<]+)</span>' % l,
                    open(ai, encoding='utf-8').read(), re.S)]
                areas.sort(key=lambda a: region_pos(a['url'].rstrip('/').split('/')[-1]))   # top-bar menus: region order
            for f in glob.glob(os.path.join(OUT, l, '**', '*.html'), recursive=True):
                html = open(f, encoding='utf-8').read()
                m = re.search(r'<header class="hdr" id="top">.*?</header>', html, re.S)
                if not m:
                    continue
                alt = {lg: href for href, lg in re.findall(r'<a href="([^"]+)" hreflang="(\w\w)"', m.group(0))}
                alt = {lg: alt.get(lg, f'/{lg}/projects/') for lg in langs}
                section = os.path.relpath(f, os.path.join(OUT, l)).split(os.sep)[0]
                section = {'kits': 'quick-funding', 'about': '', 'achievements': ''}.get(section, section)
                new = hdr_tpl.render(lang=l, t=T[l], T=T, langs=langs, alt=alt, section=section, areas=areas)
                html = html[:m.start()] + new + html[m.end():]
                html = html.replace('/img/brand/logo-ar.png', '/img/brand/logo-en.png')
                html = html.replace(f'href="/{l}/areas//"', f'href="/{l}/areas/africa/"')  # Africa tile link
                # same photo banner as the Reports pages
                html = html.replace('<section class="phero "', f'<section class="phero has-img" style="--bg:url(\'{S.get("projects_image", "")}\')"')
                if WC.get('wash_label', {}).get(l):
                    html = html.replace('>WASH<', '>' + WC['wash_label'][l] + '<')
                if section == 'projects' and f.endswith(os.path.join('projects', 'index.html')):
                    label = (WC.get('label') or {}).get(l, 'Women & Children')
                    html = re.sub(r'(<select data-filter="sector">.*?)(</select>)', lambda mm: mm.group(1) + f'<option value="women-children">{label}</option>' + mm.group(2), html, count=1, flags=re.S)
                    for code in WC.get('projects', []):
                        html = html.replace(f'<a class="pcard" href="/{l}/projects/{code}/"', f'<a class="pcard" data-groups="women-children" href="/{l}/projects/{code}/"')
                html, k = cards_with_facts(html, l, facts)
                cards_done += k
                with open(f, 'w', encoding='utf-8') as fh:
                    fh.write(html)
            print(f'CARDS {l}: {cards_done} project cards now show beneficiaries + duration ({len(facts)} project pages read)')
            HN[l] = home_nav(l, T[l], areas)

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
        base = dict(lang=l, t=t, dir='rtl' if l == 'ar' else 'ltr', langs=langs, T=T, reports=R, menu_imp=imp,
                    contact=(S.get('contacts') or {}).get(l, {}))

        def add(tpl, url, ref, **kw):
            pages.append((tpl, url, ref, dict(base, **kw)))
            refs.setdefault(ref, {})[l] = url

        add('landing.html', f'/{l}/', 'home', home_nav=HN.get(l, []))
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
    # prices: thousands written with dots ($10.000 instead of $10,000)
    price = re.compile(r'(?:\$|USD\s?)\d{1,3}(?:,\d{3})+|\d{1,3}(?:,\d{3})+(?=\s?(?:\$|USD))')
    for f in glob.glob(os.path.join(OUT, '**', '*.html'), recursive=True):
        html = open(f, encoding='utf-8').read()
        rel = os.path.relpath(f, OUT).replace(os.sep, '/')
        mm = re.match(r'(tr|en|ar)/(quick-funding/gaza/|kits/gaz-)', rel)
        if mm and GQ:   # Gaza: every number exactly as in the Excel file (content/gaza-quick-funding.yml)
            if mm.group(2) == 'quick-funding/gaza/':
                html, n = gaza_rows(html, mm.group(1), GQ)
                print(f'GAZA {rel}: {n} of {len(GQ.get("rows", []))} rows written from the file')
                html, k = replace_hero_text(html, mm.group(1))
                print(f'HERO {rel}: ' + ('replaced' if k else 'NOT FOUND'))
            else:
                slug = rel.split('/')[2]
                if slug in GQ.get('kits', {}):
                    html, ok = gaza_kit(html, mm.group(1), GQ['kits'][slug])
                    print(f'KIT {rel}: ' + ('written from the file' if ok else 'NOT UPDATED (table not found)'))
        elif mm:
            if mm.group(2) == 'quick-funding/gaza/':
                html, n = override_prices(html, GAZA_FOOD)
                print(f'PRICES {rel}: {n} of {len(GAZA_FOOD)} updated')
                html, k = replace_hero_text(html, mm.group(1))
                print(f'HERO {rel}: ' + ('replaced' if k else 'NOT FOUND'))
                for code, (unit, funding) in GAZA_ROWS.items():
                    html, k = set_row_prices(html, code, unit, funding)
                    print(f'ROW {rel} {code}: ' + ('updated' if k else 'NOT FOUND'))
            else:
                slug = rel.split('/')[2]
                if slug in GAZA_KITS:
                    html, ok = update_kit(html, mm.group(1), GAZA_KITS[slug])
                    print(f'KIT {rel}: ' + ('updated' if ok else 'NOT UPDATED (table did not match)'))
            html = localize_prices(html, mm.group(1))
        ym = re.match(r'(tr|en|ar)/quick-funding/(yemen/)?index\.html$', rel)
        if ym and YQ:
            if ym.group(2):
                html, k = yemen_rows(html, ym.group(1), YQ)
                print(f'YEMEN {rel}: {k} rows added')
            else:   # Quick Funding overview: number of interventions on the Yemen tile
                yp = os.path.join(OUT, ym.group(1), 'quick-funding', 'yemen', 'index.html')
                n = len(set(re.findall(r'<tr id="(YEM-[^"]+)"', open(yp, encoding='utf-8').read())) | {r['code'] for r in YQ.get('rows', [])})
                html, k = re.subn(r'(href="/%s/quick-funding/yemen/"[^>]*>\s*<span class="tile-name">[^<]*</span>\s*<span class="tile-text">)\d+' % ym.group(1),
                                  lambda mm: mm.group(1) + str(n), html, count=1)
                print(f'YEMEN {rel}: tile count ' + (f'set to {n}' if k else 'NOT FOUND'))
        if not (mm and GQ):   # Gaza pages keep the commas of the file
            html = price.sub(lambda m2: m2.group(0).replace(',', '.'), html)
        html = dollar_right(html, rel.split('/')[0] if rel.split('/')[0] in langs else 'en')
        new = re.sub(r'(["\'(])(' + '|'.join(re.escape(u) for u in ver) + r')(?=["\')])', lambda mm: mm.group(1) + mm.group(2) + '?v=' + ver[mm.group(2)], html)
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
