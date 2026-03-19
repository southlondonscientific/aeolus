"""Tests for the progress indicator wrapper."""

import logging

from aeolus.progress import _LoggingProgress, track


class TestTrack:
    def test_returns_tqdm_when_available(self):
        """track() returns a tqdm wrapper when tqdm is installed."""
        items = [1, 2, 3]
        result = track(items, "test")
        # tqdm wraps the iterable; should still yield all items
        assert list(result) == [1, 2, 3]

    def test_falls_back_to_logging(self, monkeypatch):
        """track() falls back to logging when tqdm is unavailable."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "tqdm" in name:
                raise ImportError("no tqdm")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        items = [1, 2, 3]
        result = track(items, "test")
        assert isinstance(result, _LoggingProgress)
        assert list(result) == [1, 2, 3]

    def test_skips_bar_for_single_item(self):
        """track() returns the iterable unchanged when total=1."""
        items = ["only"]
        result = track(items, "test")
        # Should return the original list, not a tqdm wrapper
        assert result is items

    def test_skips_bar_for_empty_iterable(self):
        """track() returns the iterable unchanged when total=0."""
        items = []
        result = track(items, "test")
        assert result is items

    def test_logging_fallback_logs_info(self, monkeypatch, caplog):
        """Logging fallback emits INFO-level messages."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "tqdm" in name:
                raise ImportError("no tqdm")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        items = ["a", "b", "c"]
        with caplog.at_level(logging.INFO, logger="aeolus.progress"):
            result = list(track(items, "Downloading"))

        assert result == ["a", "b", "c"]
        assert len(caplog.records) == 3
        assert "Downloading 1/3" in caplog.records[0].message
        assert "Downloading 2/3" in caplog.records[1].message
        assert "Downloading 3/3" in caplog.records[2].message

    def test_explicit_total(self):
        """track() accepts an explicit total parameter."""

        def gen():
            yield 1
            yield 2

        # Generators have no len(), so total must be explicit
        result = track(gen(), "test", total=2)
        assert list(result) == [1, 2]

    def test_logging_progress_len(self, monkeypatch):
        """_LoggingProgress supports len() when total is known."""
        progress = _LoggingProgress([1, 2, 3], "test", 3)
        assert len(progress) == 3
