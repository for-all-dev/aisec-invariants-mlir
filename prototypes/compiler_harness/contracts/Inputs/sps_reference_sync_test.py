from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

sys.dont_write_bytecode = True


def load_sync_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("sps_reference_sync_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sync utility: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ReferenceSyncTransactionTests(unittest.TestCase):
    sync: ModuleType
    source_template: Path
    interface_lock_template: Path

    @classmethod
    def configure(
        cls,
        sync_path: Path,
        source_template: Path,
        interface_lock_template: Path,
    ) -> None:
        cls.sync = load_sync_module(sync_path)
        cls.source_template = source_template
        cls.interface_lock_template = interface_lock_template

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sps-reference-sync-test-")
        root = Path(self.temporary.name)
        self.source = root / "source"
        self.harness = root / "harness"
        shutil.copytree(self.source_template, self.source)
        contracts = self.harness / "contracts"
        contracts.mkdir(parents=True)
        shutil.copy2(
            self.interface_lock_template, contracts / "sps-interface.lock.json"
        )
        self.sync.HARNESS_ROOT = self.harness
        self.sync.CONTRACT_ROOT = contracts
        self.sync.VENDOR_ROOT = contracts / "vendor" / "sps-reference-rev4"
        self.sync.LOCK_PATH = contracts / "sps-reference.lock.json"
        self.sync.INTERFACE_LOCK_PATH = contracts / "sps-interface.lock.json"
        self.sync.update(self.source)
        self.old_vendor = tree_bytes(self.sync.VENDOR_ROOT)
        self.old_lock = self.sync.LOCK_PATH.read_bytes()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assert_old_generation_restored(self) -> None:
        self.assertEqual(tree_bytes(self.sync.VENDOR_ROOT), self.old_vendor)
        self.assertEqual(self.sync.LOCK_PATH.read_bytes(), self.old_lock)
        self.sync.verify_vendor()

    def test_post_install_verification_failure_rolls_back(self) -> None:
        readme = self.source / "reference" / "README.md"
        readme.write_bytes(readme.read_bytes() + b" ")
        with patch.object(
            self.sync,
            "verify_vendor",
            side_effect=self.sync.ReferenceSyncError("injected post-install failure"),
        ):
            with self.assertRaisesRegex(
                self.sync.ReferenceSyncError, "injected post-install failure"
            ):
                self.sync.update(self.source)
        self.assert_old_generation_restored()

    def test_staged_copy_drift_is_refused_before_install(self) -> None:
        readme = self.source / "reference" / "README.md"
        readme.write_bytes(readme.read_bytes() + b" ")
        real_copy = self.sync.shutil.copy2

        def corrupt_staged_readme(source: Path, target: Path) -> Path:
            result = real_copy(source, target)
            target_path = Path(target)
            if target_path.name == "README.md":
                target_path.write_bytes(target_path.read_bytes() + b"staged-drift")
            return result

        with patch.object(self.sync.shutil, "copy2", side_effect=corrupt_staged_readme):
            with self.assertRaisesRegex(
                self.sync.ReferenceSyncError,
                "staged reference changed while it was being copied",
            ):
                self.sync.update(self.source)
        self.assert_old_generation_restored()


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: sps_reference_sync_test.py SYNC_UTILITY SOURCE INTERFACE_LOCK"
        )
    ReferenceSyncTransactionTests.configure(
        Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    )
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        ReferenceSyncTransactionTests
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print("SPS reference sync staging and rollback verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
