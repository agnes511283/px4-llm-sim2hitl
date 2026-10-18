#!/usr/bin/env python3
"""Embed the Chinese font into an SVG picture, so it looks the same on every computer.

  python3 embed_fonts.py <picture.svg>

Rewrites the file in place: collects every character used in its text, subsets Noto Sans CJK TC
(Regular and Bold, SIL Open Font License 1.1) to those characters plus printable ASCII, and puts
them in the SVG's <style> as WOFF2 data. Run it again after changing any text (an old embedded
font is replaced). Needs fontTools and brotli, and Noto Sans CJK installed (fc-match finds it).
"""
import base64
import io
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection

FAMILY = 'EmbeddedNotoSansTC'
FACE = 'Noto Sans CJK TC'
BEGIN, END = '/* embedded-font-begin */', '/* embedded-font-end */'


def font_file(style):
    out = subprocess.run(['fc-match', '-f', '%{file}', f'{FACE}:style={style}'],
                         capture_output=True, text=True, check=True).stdout
    if not out.endswith('.ttc'):
        raise SystemExit(f'{FACE} {style} not found (fc-match gave {out!r})')
    return out


def subset_woff2(path, text):
    collection = TTCollection(path)
    font = next(f for f in collection.fonts if f['name'].getDebugName(4).startswith(FACE))
    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = ['*']
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.flavor = 'woff2'
    font.recalcTimestamp = False  # same text, same bytes: no spurious git diffs
    font.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def main():
    svg = Path(sys.argv[1])
    source = svg.read_text(encoding='utf-8')
    source = re.sub(r'\n[ \t]*' + re.escape(BEGIN) + r'.*?' + re.escape(END), '', source, flags=re.S)
    root = ET.fromstring(source)
    used = ''.join(''.join(e.itertext()) for e in root.iter() if e.tag.endswith(('text', 'title')))
    text = ''.join(sorted(set(used) | {chr(c) for c in range(0x20, 0x7f)}))
    faces = []
    for weight, style in ((400, 'Regular'), (700, 'Bold')):
        data = subset_woff2(font_file(style), text)
        faces.append(f"@font-face {{ font-family: '{FAMILY}'; font-weight: {weight}; "
                     f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    block = (f'{BEGIN}\n    /* Noto Sans CJK TC subset, SIL Open Font License 1.1 (https://openfontlicense.org) */\n    '
             + '\n    '.join(faces) + f'\n    {END}')
    if '<style>' not in source:
        raise SystemExit('the SVG needs a <style> element')
    source = source.replace('<style>', '<style>\n    ' + block, 1)
    if FAMILY not in source.split('<style>', 1)[0]:
        source = re.sub(r'font-family="', f'font-family="\'{FAMILY}\',', source, count=1)
    svg.write_text(source, encoding='utf-8')
    print(f'{svg}: {len(set(used))} characters, {svg.stat().st_size / 1024:.0f} KiB')


if __name__ == '__main__':
    main()
