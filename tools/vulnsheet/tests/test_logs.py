import io
import logging
import unittest

from vulnsheet import logs


class ConfigureTest(unittest.TestCase):
    def tearDown(self):
        logs.configure("info", stream=io.StringIO())

    def _handlers(self):
        return [h for h in logging.getLogger("vulnsheet").handlers
                if not isinstance(h, logging.NullHandler)]

    def test_repeated_configure_keeps_one_handler(self):
        # Второй хендлер задвоил бы каждую строку журнала.
        logs.configure("info", stream=io.StringIO())
        logs.configure("info", stream=io.StringIO())
        self.assertEqual(len(self._handlers()), 1)

    def test_module_name_is_shortened(self):
        stream = io.StringIO()
        logs.configure("info", stream=stream)
        logging.getLogger("vulnsheet.kojiclient").warning("нет тега")
        self.assertRegex(stream.getvalue(),
                         r"^\d\d:\d\d:\d\d WARNING koji: нет тега\n$")

    def test_debug_adds_thread_name(self):
        stream = io.StringIO()
        logs.configure("debug", stream=stream)
        logging.getLogger("vulnsheet.vex").debug("из кэша")
        self.assertIn("[MainThread] vex: из кэша", stream.getvalue())

    def test_records_below_level_are_dropped(self):
        stream = io.StringIO()
        logs.configure("warning", stream=stream)
        logging.getLogger("vulnsheet.cli").info("написан report.csv")
        self.assertEqual(stream.getvalue(), "")

    def test_unknown_level_is_rejected(self):
        with self.assertRaises(ValueError):
            logs.configure("verbose")
