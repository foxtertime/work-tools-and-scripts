"""Build the application, not the user's CSV. Python standard library only."""
import argparse
import base64
import json
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
    catalog = json.loads((ASSETS / 'checklists.json').read_text(encoding='utf-8'))
    definitions = json.dumps(catalog, ensure_ascii=False, separators=(',', ':'))
    definitions = definitions.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    script += 'CR.checklistDefinitions = ' + definitions + ';\n'
    script += '\n'.join((ASSETS / 'js' / name).read_text(encoding='utf-8') for name in ['csv.js', 'checklists.js', 'links.js', 'model.js', 'search.js', 'app.js'])
    if template.count('/*@style*/') != 1 or template.count('/*@script*/') != 1:
        raise ValueError('Template markers must occur exactly once')
    parts = {'/*@style*/': css, '/*@script*/': script.replace('</script', '<\\/script')}
    return re.sub(r'/\*@(?:style|script)\*/', lambda m: parts[m[0]], template)


def checklist_document():
    catalog = json.loads((ASSETS / 'checklists.json').read_text(encoding='utf-8'))
    lines = ['# Чеклисты ревью', '',
             'Список собирается из [assets/checklists.json](../assets/checklists.json).',
             'Текст пункта можно менять, сохраняя его ID. Новый смысл — новый ID.',
             'Добавленный пункт требует проверки; удалённый сохраняется в истории.', '']
    for profile in catalog['profiles']:
        lines += ['## ' + profile['label'], '']
        lines += ['- ' + item['label'] for item in profile['items']]
        lines += ['']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify checked-in HTML matches sources')
    args = parser.parse_args()
    text = render()
    outputs = {ROOT / 'cvereview.html': text, ROOT / 'docs/checklists.md': checklist_document()}
    if args.check:
        for output, content in outputs.items():
            if not output.exists() or output.read_text(encoding='utf-8') != content:
                parser.exit(1, output.name + ' differs from sources; run build.py\n')
        print('HTML and checklist documentation match sources')
    else:
        for output, content in outputs.items():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding='utf-8')
            print('Built ' + str(output))


if __name__ == '__main__':
    main()
