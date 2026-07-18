"""Unit tests for the pure ingestion pipeline (no network, no database)."""

from datetime import datetime

from app.services.ingestion import normalize, rate_freshness, split_into_pages


class TestNormalize:
    def test_strips_trailing_whitespace_and_collapses_blank_runs(self):
        assert normalize("a   \n\n\n\nb  ") == "a\n\nb"

    def test_keeps_headers(self):
        assert normalize("# Title\n\ntext") == "# Title\n\ntext"


class TestSplitIntoPages:
    def test_splits_on_headers_with_preamble_page(self):
        text = "intro para\n# Header A\ncontent a\n## Header B\ncontent b"
        pages = split_into_pages(text, max_page_tokens=800)

        assert [p.raw_text for p in pages] == [
            "intro para",
            "# Header A\ncontent a",
            "## Header B\ncontent b",
        ]
        assert [p.order_index for p in pages] == [0, 1, 2]

    def test_windows_oversized_section_with_continuous_order_index(self):
        words = " ".join(str(i) for i in range(20))  # 20 words, no headers
        pages = split_into_pages(words, max_page_tokens=10)  # budget ~7 words

        assert len(pages) > 1
        assert [p.order_index for p in pages] == list(range(len(pages)))

    def test_empty_input_yields_no_pages(self):
        assert split_into_pages("   \n\n  ", max_page_tokens=800) == []


class TestRateFreshness:
    NOW = datetime(2026, 7, 18)

    def test_no_date_is_neutral(self):
        assert rate_freshness("no dates here", now=self.NOW) == 0.5

    def test_recent_iso_date_is_high(self):
        assert rate_freshness("updated 2026-06-01", now=self.NOW) > 0.9

    def test_old_year_decays_toward_floor(self):
        old = rate_freshness("as of 2015", now=self.NOW)
        recent = rate_freshness("as of 2025", now=self.NOW)
        assert old < recent
        assert old >= 0.1

    def test_picks_most_recent_of_several_dates(self):
        # The recent date wins over the old one.
        assert rate_freshness("2018 and January 2026", now=self.NOW) == rate_freshness(
            "January 2026", now=self.NOW
        )

    def test_future_date_saturates_at_one(self):
        assert rate_freshness("2030-01-01", now=self.NOW) == 1.0
