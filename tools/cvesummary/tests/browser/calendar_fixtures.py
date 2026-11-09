"""CLI-built holiday reports: real bundled calendars, no network or user cache."""
import csv
import os
from pathlib import Path
import sys
from unittest import mock

from cvesummary import cli, workcalendar

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
header = ['CVE ID', 'Компонент', 'RHEL state', 'RHEL severity', 'Разработчик',
          'Статус', 'Start date', 'End date', 'Task date', 'Принятая мера']


def row(dev, start, end='', status=None):
    return ['CVE-demo', 'demo', 'Affected', 'Important', dev,
            status or ('Готов' if end else 'В работе'), start, end, start, 'Патч из апстрима']


fixtures = {
    'holiday-week': ('2026-11-06', [row('Алиса', '2026-11-02', '2026-11-06') for _ in range(3)]
                     + [row('Алиса', '2026-11-02', '2026-11-06', 'Ожидает ревью')]),
    'holiday-work': ('2026-11-04', [row('Алиса', '2026-11-03'),
                     row('Борис', '2026-11-03', '2026-11-04', 'Ожидает ревью'),
                     row('Вера', '2026-11-04')]),
    'working-saturday': ('2025-11-05', [row('Алиса', '2025-10-31', '2025-11-05')]),
    'holiday-forecast': ('2026-11-03', [row('Алиса', '2026-11-03', '2026-11-03'),
                         row('', '2026-11-03', status='')]),
}
with mock.patch.object(workcalendar, 'urlopen', side_effect=OSError('offline')), \
        mock.patch.dict(os.environ, {'XDG_CACHE_HOME': str(out / 'cache')}):
    for name, (as_of, rows) in fixtures.items():
        path = out / (name + '.csv')
        for i, values in enumerate(rows):
            values[0] = 'CVE-2026-%d' % (9000 + i)
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        assert cli.main([str(path), '--as-of', as_of, '--release', name]) == 0
