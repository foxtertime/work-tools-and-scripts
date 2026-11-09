import datetime as dt
import io
from http.client import IncompleteRead
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cvesummary import workcalendar as cal


XML = b'''<calendar year="2026" country="ru"><holidays>
<holiday id="8" title="Unity day"/></holidays><days>
<day d="11.03" t="2"/><day d="11.04" t="1" h="8"/>
<day d="12.31" t="1" f="01.04"/>
<day d="11.07" t="3"/>
</days></calendar>'''


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.net = mock.patch.object(cal, 'urlopen', side_effect=OSError('offline')).start()
        self.addCleanup(mock.patch.stopall)

    def test_parse_holiday_short_day_and_working_saturday(self):
        days = cal.parse(XML, 2026)
        self.assertEqual(days['2026-11-04'], dict(working=False, label='Unity day'))
        self.assertTrue(days['2026-11-03']['working'])
        self.assertTrue(days['2026-11-07']['working'])
        self.assertFalse(days['2026-12-31']['working'])
        self.assertIn('04.01', days['2026-12-31']['label'])

    def test_reject_invalid_response(self):
        for raw in (b'<html/>', XML.replace(b'2026', b'2025'),
                    XML.replace(b'11.04', b'02.30'), XML.replace(b't="1"', b't="9"'),
                    XML.replace(b'country="ru"', b'country="kz"'),
                    XML.replace(b'</days>', b'<day d="11.04" t="3"/></days>')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                cal.parse(raw, 2026)

    def test_fetch_caches_valid_xml_and_reuses_it(self):
        self.net.side_effect = lambda *a, **kw: io.BytesIO(XML)
        first = cal.load_year(2026, self.cache)
        self.assertEqual(self.net.call_count, 1)
        self.net.side_effect = OSError('offline')
        self.assertEqual(cal.load_year(2026, self.cache), first)
        self.assertEqual(self.net.call_count, 1)

    def test_stale_cache_survives_invalid_network_response(self):
        path = self.cache / 'ru-2026.xml'
        path.write_bytes(XML)
        os.utime(path, (0, 0))
        self.net.side_effect = lambda *a, **kw: io.BytesIO(b'<html>failure</html>')
        self.assertEqual(cal.load_year(2026, self.cache), cal.parse(XML, 2026))
        self.assertEqual(path.read_bytes(), XML)

    def test_broken_cache_and_network_use_bundled_calendar(self):
        (self.cache / 'ru-2026.xml').write_text('broken')
        days = cal.load_year(2026, self.cache)
        self.assertFalse(days['2026-11-04']['working'])
        self.assertIn('единства', days['2026-11-04']['label'])

    def test_interrupted_download_uses_bundled_calendar(self):
        self.net.side_effect = IncompleteRead(b'<calendar', 200)
        self.assertFalse(cal.load_year(2026, self.cache)['2026-11-04']['working'])

    def test_invalid_xml_encoding_in_download_or_cache_does_not_abort_report(self):
        raw = b'<?xml version="1.0" encoding="corrupt"?>' + XML
        self.net.side_effect = lambda *a, **kw: io.BytesIO(raw)
        with self.subTest(source='network'):
            self.assertFalse(cal.load_year(2026, self.cache)['2026-11-04']['working'])
        (self.cache / 'ru-2026.xml').write_bytes(raw)
        self.net.side_effect = OSError('offline')
        with self.subTest(source='cache'):
            self.assertFalse(cal.load_year(2026, self.cache)['2026-11-04']['working'])

    def test_actual_working_saturdays_from_bundled_calendar(self):
        self.assertTrue(cal.load_year(2025, self.cache)['2025-11-01']['working'])
        self.assertTrue(cal.load_year(2027, self.cache)['2027-02-20']['working'])

    def test_cache_write_failure_keeps_downloaded_calendar(self):
        self.net.side_effect = lambda *a, **kw: io.BytesIO(XML)
        blocked = self.cache / 'file'
        blocked.write_text('not a directory')
        self.assertEqual(cal.load_year(2026, blocked), cal.parse(XML, 2026))

    def test_history_and_next_year_embedded_with_explicit_missing_years(self):
        data = cal.load([dict(start='2024-12-30', end='2026-11-05', bad=[]),
                         dict(start='1900-01-01', bad=['start'])],
                        dt.date(2026, 11, 9), cache_dir=self.cache)
        self.assertEqual(data['years'], [2025, 2026, 2027])
        self.assertEqual(data['missing'], [2024])
        self.assertFalse(data['days']['2026-11-04']['working'])

    def test_unavailable_year_has_no_fabricated_calendar(self):
        self.assertIsNone(cal.load_year(2024, self.cache))


if __name__ == '__main__':
    unittest.main()
