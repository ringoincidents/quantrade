"""Synthetic, offline fixtures for the Treasury annual XML pilot."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from treasury_pilot import (
    archive_and_index, connect, latest_captured, official_url,
    parse_annual_xml, verified_historic_pit, fetch_official, MAX_XML_BYTES,
)


def xml_value(date, y2, y10):
    y2tag = f"<d:BC_2YEAR>{y2}</d:BC_2YEAR>" if y2 is not None else ""
    y10tag = f"<d:BC_10YEAR>{y10}</d:BC_10YEAR>" if y10 is not None else ""
    return f"""
      <entry>
        <content type="application/xml"><m:properties>
          <d:NEW_DATE>{date}T00:00:00</d:NEW_DATE>
          {y2tag}{y10tag}
        </m:properties></content>
      </entry>"""


def sample_xml(*entries):
    text = """<?xml version="1.0" encoding="UTF-8"?>
      <feed xmlns="http://www.w3.org/2005/Atom"
            xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
            xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
    """ + "".join(entries) + "</feed>"
    return text.encode("utf-8")


class TreasuryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.xml = sample_xml(
            xml_value("2025-01-02", "4.1", "4.5"),
            xml_value("2025-01-03", "4.2", "4.6"),
        )
        self.uri = official_url(2025)
        self.first_seen = "2026-11-23T10:00:00Z"

    def test_01_official_url_year_and_host_pinned(self):
        self.assertEqual(official_url(2025).split("?")[0],
                         "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml")
        with self.assertRaises(ValueError): official_url(1989)
        with self.assertRaises(ValueError): official_url(3000)

    def test_02_parse_atom_2y_and_10y(self):
        rows = parse_annual_xml(self.xml, 2025)
        self.assertEqual(rows["2Y"], [("2025-01-02", 4.1), ("2025-01-03", 4.2)])
        self.assertEqual(rows["10Y"][-1], ("2025-01-03", 4.6))

    def test_03_missing_series_is_not_filled_with_zero(self):
        missing = sample_xml(xml_value("2025-01-02", None, "4.5"))
        rows = parse_annual_xml(missing, 2025)
        self.assertEqual(rows["2Y"], [])
        self.assertEqual(rows["10Y"], [("2025-01-02", 4.5)])

    def test_04_duplicate_observation_rejected(self):
        bad = sample_xml(xml_value("2025-01-02", "4.1", "4.2"),
                         xml_value("2025-01-02", "4.1", "4.2"))
        with self.assertRaises(ValueError): parse_annual_xml(bad, 2025)

    def test_05_wrong_year_or_fake_response_rejected(self):
        with self.assertRaises(ValueError): parse_annual_xml(self.xml, 2024)
        with self.assertRaises(ValueError): parse_annual_xml(b"<html>blocked</html>", 2025)
        with self.assertRaises(ValueError): parse_annual_xml(b"x" * (MAX_XML_BYTES+1), 2025)

    def test_06_archive_private_hash_and_idempotent(self):
        a = archive_and_index(self.p, self.xml, 2025, self.uri, self.first_seen)
        self.assertEqual(a["status"], "archived")
        self.assertEqual(a["sha256"], hashlib.sha256(self.xml).hexdigest())
        self.assertEqual((self.p/"sha256"/(a["sha256"]+".xml")).read_bytes(), self.xml)
        b = archive_and_index(self.p, self.xml, 2025, self.uri, self.first_seen)
        self.assertEqual(b["status"], "unchanged")

    def test_07_captured_asof_does_not_invent_original_release(self):
        archive_and_index(self.p, self.xml, 2025, self.uri, self.first_seen)
        db = connect(self.p / "treasury_yields.sqlite")
        self.addCleanup(db.close)
        self.assertIsNone(latest_captured(db, "UST_PAR_10Y", "2025-01-03",
                                           "2025-01-04T00:00:00Z"))
        self.assertEqual(latest_captured(db, "UST_PAR_10Y", "2025-01-03",
                                         "2026-11-24T00:00:00Z"), 4.6)
        self.assertIsNone(verified_historic_pit(db, "UST_PAR_10Y",
                                                "2025-01-03", "2026-11-24T00:00:00Z"))

    def test_08_corrupt_archive_refused(self):
        a = archive_and_index(self.p, self.xml, 2025, self.uri, self.first_seen)
        (self.p / "sha256" / (a["sha256"] + ".xml")).write_bytes(b"corrupted")
        with self.assertRaises(ValueError):
            archive_and_index(self.p, self.xml, 2025, self.uri, self.first_seen)

    def test_09_untrusted_url_refused(self):
        with self.assertRaises(ValueError):
            archive_and_index(self.p, self.xml, 2025, "https://evil.example/feed",
                              self.first_seen)

    def test_10_network_client_rejects_redirects(self):
        class Response:
            def geturl(self): return "https://evil.example/redirect"
            def read(self, n): return b"<feed></feed>"
            def __enter__(self): return self
            def __exit__(self, *args): return False
        def opener(*args, **kwargs): return Response()
        with self.assertRaises(ValueError): fetch_official(2025, opener)

    def test_11_no_naive_collector_timestamps(self):
        with self.assertRaises(ValueError):
            archive_and_index(self.p, self.xml, 2025, self.uri,
                              "2026-11-23T10:00:00")


if __name__ == "__main__":
    unittest.main()
