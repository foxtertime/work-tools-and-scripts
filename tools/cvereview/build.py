"""Build the application, not the user's CSV. Python standard library only."""
import argparse
import base64
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'


def render():
    template = (ASSETS / 'review.html').read_text(encoding='utf-8')
    fonts = (ASSETS / 'fonts/fonts.css').read_text(encoding='utf-8')
    fonts = re.sub(r'url\(([^)]+)\)', lambda m: 'url(data:font/woff2;base64,' + base64.b64encode((ASSETS / 'fonts' / m[1]).read_bytes()).decode() + ')', fonts)
    licenses = '\n'.join(p.read_text(encoding='utf-8').replace('*/', '* /') for p in sorted((ASSETS / 'fonts').glob('*OFL.txt')))
    css = fonts + '\n/* Font licenses:\n' + licenses + '\n*/\n' + (ASSETS / 'style.css').read_text(encoding='utf-8') + '\n' + (ASSETS / 'app.css').read_text(encoding='utf-8')
    version = (ROOT / 'VERSION').read_text().strip()
    script = 'globalThis.CR = {VERSION: ' + repr(version) + '};\n'
    script += '\n'.join((ASSETS / 'js' / name).read_text(encoding='utf-8') for name in ['csv.js', 'checklists.js', 'links.js', 'model.js', 'app.js'])
    if template.count('/*@style*/') != 1 or template.count('/*@script*/') != 1:
        raise ValueError('Template markers must occur exactly once')
    parts = {'/*@style*/': css, '/*@script*/': script.replace('</script', '<\\/script')}
    return re.sub(r'/\*@(?:style|script)\*/', lambda m: parts[m[0]], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify checked-in HTML matches sources')
    args = parser.parse_args()
    text = render()
    output = ROOT / 'cvereview.html'
    if args.check:
        if not output.exists() or output.read_text(encoding='utf-8') != text:
            parser.exit(1, 'cvereview.html differs from sources; run build.py\n')
        print('cvereview.html matches sources')
    else:
        output.write_text(text, encoding='utf-8')
        print('Built ' + str(output))


if __name__ == '__main__':
    main()
