import io
import tarfile
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from backup.legacy.media_staging import MediaStaging, StagingError


def write_tar(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in entries:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


class LegacyMediaStagingTests(SimpleTestCase):
    databases = set()

    def test_stages_only_referenced_file_and_cleans_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tar_path = root / "media.tar.gz"
            write_tar(
                tar_path,
                [
                    ("media/productos/foto.jpg", b"image"),
                    ("media/no-usado.txt", b"unused"),
                ],
            )
            staging = MediaStaging(root / "staging", root / "media-root")

            result = staging.stage(
                tar_path,
                [{"path": "productos/foto.jpg"}],
            )

            self.assertEqual(len(result["files"]), 1)
            self.assertTrue(Path(result["files"][0]["staged_path"]).is_file())
            self.assertFalse((root / "staging" / "no-usado.txt").exists())
            staging.cleanup()
            self.assertFalse((root / "staging").exists())

    def test_rejects_missing_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tar_path = root / "media.tar.gz"
            write_tar(tar_path, [("media/otro.jpg", b"image")])
            staging = MediaStaging(root / "staging", root / "media-root")

            with self.assertRaises(StagingError):
                staging.stage(
                    tar_path,
                    [{"path": "productos/faltante.jpg"}],
                )

    def test_rejects_reference_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tar_path = root / "media.tar.gz"
            write_tar(tar_path, [("media/safe.jpg", b"image")])
            staging = MediaStaging(root / "staging", root / "media-root")

            with self.assertRaisesRegex(StagingError, "insegura"):
                staging.stage(tar_path, [{"path": "../safe.jpg"}])

    def test_rejects_unsafe_archive_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tar_path = root / "media.tar.gz"
            write_tar(tar_path, [("../escape.jpg", b"image")])
            staging = MediaStaging(root / "staging", root / "media-root")

            with self.assertRaises(StagingError):
                staging.stage(tar_path, [])

            self.assertTrue((root / "staging").is_dir())
            self.assertEqual(list((root / "staging").iterdir()), [])
