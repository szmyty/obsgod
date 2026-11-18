"""Owned-root ancestry fixtures: unsafe shared parents and supported home aliases."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths
import install
import update


class OwnedAncestors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "player"
        self.home.mkdir(mode=0o700)
        self.enterContext(patch.dict(os.environ, {"HOME": str(self.home)}))

    def test_unsafe_group_or_other_writable_parents_fail_before_creation(self):
        for mode in (0o770, 0o777):
            with self.subTest(mode=oct(mode)):
                parent = self.home / ("shared-" + oct(mode))
                parent.mkdir(mode=mode)
                parent.chmod(mode)
                target = parent / "obsgod"
                for create in (install.owned_directory, update.private_directory):
                    with self.assertRaisesRegex(RuntimeError, "nonsticky"):
                        create(target, self.home)
                    self.assertFalse(target.exists())

    def test_home_itself_and_missing_grandchildren_are_checked(self):
        self.home.chmod(0o770)
        with self.assertRaisesRegex(ValueError, "nonsticky"):
            paths.validate_owned_root(self.home / "new/child", self.home)
        self.assertFalse((self.home / "new").exists())

    def test_safe_owner_only_and_trusted_sticky_custom_xdg_roots_work(self):
        for mode in (0o700, 0o1777):
            parent = self.home / ("data-" + oct(mode))
            parent.mkdir(mode=mode)
            parent.chmod(mode)
            base, _ = paths.app_directories(self.home, {"XDG_DATA_HOME": str(parent)})
            install.owned_directory(base, self.home)
            self.assertTrue(base.is_dir())

    def test_only_the_home_alias_is_normalized_not_links_inside_owned_roots(self):
        alias = Path(self.temp.name) / "home-alias"
        alias.symlink_to(self.home)
        with patch.dict(os.environ, {"HOME": str(alias)}):
            install.owned_directory(alias / "data/obsgod", alias)
            paths.validate_owned_root(alias / "data/obsgod", self.home)
            self.assertTrue((self.home / "data/obsgod").is_dir())
            (self.home / "inside-link").symlink_to(self.home / "data")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                paths.validate_owned_root(alias / "inside-link/obsgod", alias)

    def test_home_alias_under_replaceable_ancestor_fails_before_raw_alias_writes(self):
        for mode in (0o770, 0o777):
            parent = Path(self.temp.name) / ("alias-parent-" + oct(mode))
            parent.mkdir(mode=mode)
            parent.chmod(mode)
            alias = parent / "player"
            alias.symlink_to(self.home)
            with patch.dict(os.environ, {"HOME": str(alias)}):
                for create in (install.owned_directory, update.private_directory):
                    with self.assertRaisesRegex(RuntimeError, "nonsticky"):
                        create(alias / "data/obsgod", alias)
                    self.assertFalse((self.home / "data").exists())


if __name__ == "__main__":
    unittest.main()
