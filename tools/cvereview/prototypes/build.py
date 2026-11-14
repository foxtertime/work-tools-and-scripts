"""Inline the prototype sources into five standalone HTML files. No dependencies."""
from pathlib import Path
import base64
import re

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src"
VARIANTS = [
    ("01-cards.html", "Карточки", "Контекст + чеклист · в духе cvesummary", "Слева контекст задачи, справа чеклист с отметками ✓ / ✕ / пусто. «Ревьювед» активна после проверки всех пунктов.", "Последовательное ревью с явной проверкой каждого пункта"),
    ("02-inbox.html", "Входящие", "Очередь + подробности", "Список слева, полная карточка справа. Больше места для сборок, комментариев и исходных полей.", "Долгое ревью с частым переключением между задачами"),
    ("03-board.html", "Доска", "Три пула одновременно", "На ревью, проблемы и проверенные задачи видны рядом. Каждая карточка меняет колонку после решения.", "Контроль движения задач и возвратов на доработку"),
    ("04-focus.html", "Фокус", "Одна задача за раз", "Тёмное рабочее место с крупной карточкой, очередью и прогрессом. После решения открывается следующая задача.", "Последовательное ревью без постоянного выбора следующей задачи"),
    ("05-team.html", "По разработчикам", "Дизайн cvesummary", "Тёмная шапка, шрифты и палитра cvesummary. Задачи сгруппированы по разработчику, ссылки и решения доступны сразу.", "Проверка всех решений одного разработчика подряд"),
]


def build():
    css = (SOURCE / "style.css").read_text()
    script = (SOURCE / "app.js").read_text()
    template = (SOURCE / "page.html").read_text()
    fonts = (SOURCE / "fonts" / "fonts.css").read_text()
    fonts = re.sub(
        r"url\(([^)]+)\)",
        lambda m: "url(data:font/woff2;base64," + base64.b64encode(
            (SOURCE / "fonts" / m[1]).read_bytes()).decode() + ")",
        fonts,
    )
    for i, (filename, title, *_rest) in enumerate(VARIANTS, 1):
        page = template.replace("__TITLE__", title).replace("__VARIANT__", str(i))
        page_css = css
        if i == 1:
            page_css += "\n" + (SOURCE / "cards-list.css").read_text()
        if i == 5:
            page_css += "\n" + fonts + "\n" + (SOURCE / "team-summary.css").read_text()
        page = page.replace("__STYLE__", page_css).replace("__SCRIPT__", script)
        (ROOT / filename).write_text(page)
    gallery_style = """
      body{background:#f5f7f9}.gallery{max-width:1260px;margin:auto;padding:45px 35px}
      .gallery-top{display:flex;justify-content:space-between;gap:25px;align-items:flex-end;margin-bottom:30px}
      .gallery-top h1{font-size:44px;letter-spacing:-1.8px}.gallery-top p{font-size:13px;color:var(--muted);max-width:680px;line-height:1.8;margin-top:15px}
      .gallery-top .tag{font:10px var(--mono);color:#1d6a8a;background:#e2eff5;padding:9px 12px;border-radius:5px;white-space:nowrap}
      .gallery-cards{display:grid;grid-template-columns:1fr 1fr;gap:24px}
      .example{position:relative;background:#fff;border:1px solid #dce3ea;border-radius:12px;overflow:hidden;text-decoration:none;display:block;transition:box-shadow .15s,transform .15s}
      a.example:hover{box-shadow:0 8px 30px #14202b12;transform:translateY(-2px)}
      .preview{height:255px;position:relative;overflow:hidden;border-bottom:1px solid #dce3ea;background:#e9eef2;pointer-events:none}
      .preview iframe{width:1440px;height:900px;border:0;transform:scale(.4);transform-origin:top left;pointer-events:none}
      .example-info{padding:23px 25px}.example-num{font:11px var(--mono);color:#8596a4;letter-spacing:1px}
      .example-info h2{font-size:24px;margin:5px 0 8px;display:flex;justify-content:space-between;align-items:center}.example-info h2 span{font-size:21px;font-weight:400;color:#1d6a8a}
      .example-info .sub{font-size:11px;color:#1d6a8a;font-weight:600}.example-info p{font-size:12px;line-height:1.8;color:#60717f;margin:12px 0 16px;min-height:44px}
      .use-case{padding-top:12px;border-top:1px solid #e9eef2;font-size:10px;color:#60717f}.use-case b{color:#14202b;font-weight:600}
      .guide{padding:32px;background:#0f1d29;color:#edf3f8;display:flex;flex-direction:column;justify-content:center;min-height:380px}
      .guide .eyebrow{color:#6dd3c5}.guide h2{font-size:28px;line-height:1.3;margin:8px 0 20px;letter-spacing:-.7px}.guide p{font-size:12px;line-height:1.9;color:#a3b6c5;margin-bottom:18px}.guide strong{color:#edf3f8;font-weight:500}
      .gallery-foot{padding:25px 0;font:10px/1.9 var(--mono);color:#7c8b97}
      @media(max-width:1000px){.gallery{padding:30px 22px}.preview{height:210px}.preview iframe{transform:scale(.3)}.gallery-top h1{font-size:36px}.gallery-top .tag{display:none}}
      @media(max-width:650px){.gallery-cards{grid-template-columns:1fr}.gallery{padding:28px 17px}.gallery-top h1{font-size:31px}.preview{height:220px}.preview iframe{transform:scale(.3)}.guide{min-height:300px}}
    """
    cards = []
    for i, (filename, title, subtitle, description, use) in enumerate(VARIANTS, 1):
        cards.append(f'''<a class="example" href="{filename}">
          <div class="preview" aria-hidden="true"><iframe src="{filename}" title="Превью {title}" tabindex="-1" loading="lazy" inert></iframe></div>
          <div class="example-info"><span class="example-num">ВАРИАНТ 0{i}</span><h2>{title}<span>↗</span></h2><span class="sub">{subtitle}</span><p>{description}</p><div class="use-case"><b>Подходит для:</b> {use}</div></div></a>''')
    cards.append('''<div class="example guide"><div class="eyebrow">КАК СРАВНИВАТЬ</div><h2>Один процесс.<br>Пять способов работать.</h2><p>Во всех вариантах одинаковые вымышленные строки vulnsheet и одинаковые действия: <strong>«Ревьювед»</strong> убирает задачу из очереди, <strong>«Есть проблема»</strong> требует комментарий и отправляет её в отдельный пул.</p><p>Попробуйте проверить пару задач, оставить замечание и открыть проблемный пул. Решения сохраняются отдельно для каждого варианта.</p><p>Для начала я бы сравнил <strong>01 «Карточки»</strong> и <strong>02 «Входящие»</strong>: первый ближе к cvesummary, второй даёт больше места для детального ревью.</p></div>''')
    gallery = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>cvereview · 5 UI-прототипов</title><style>{css}\n{gallery_style}</style></head><body><main class="gallery"><div class="gallery-top"><div><div class="eyebrow">CVEREVIEW / UI EXPLORATION</div><h1>Как будем ревьювить CVE?</h1><p>Пять интерактивных примеров для ревью задач разработчиков. Откройте вариант и попробуйте рабочий процесс. Загрузка таблицы появится после выбора интерфейса.</p></div><div class="tag">05 ВАРИАНТОВ · OFFLINE HTML</div></div><div class="gallery-cards">{''.join(cards)}</div><div class="gallery-foot">UI spike · 14.11.2026 · Все данные вымышленные · SecOps исключены из пула · Тикеты и GitLab используют ссылки-примеры<br>Каждый из пяти HTML-файлов можно открыть отдельно и перенести без дополнительных файлов.</div></main></body></html>'''
    (ROOT / "index.html").write_text(gallery)
    print("Built gallery and 5 standalone prototypes.")


if __name__ == "__main__":
    build()
