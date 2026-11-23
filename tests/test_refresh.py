import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import refresh  # noqa: E402


def asset(name):
    return {"name": name, "browser_download_url": "https://github.com/o/r/releases/download/v1/" + name, "size": 1000}


class DetectOs(unittest.TestCase):
    def test_extensions(self):
        self.assertEqual(refresh.detect_os("autopsy-4.22.1-64bit.msi"), "windows")
        self.assertEqual(refresh.detect_os("Tool-2.0.dmg"), "macos")
        self.assertEqual(refresh.detect_os("tool-x86_64.AppImage"), "linux")
        self.assertEqual(refresh.detect_os("tool_1.2_amd64.deb"), "linux")

    def test_tokens(self):
        self.assertEqual(refresh.detect_os("hayabusa-3.0.0-win-x64.zip"), "windows")
        self.assertEqual(refresh.detect_os("chainsaw_x86_64-pc-windows-msvc.zip"), "windows")
        self.assertEqual(refresh.detect_os("chainsaw_x86_64-apple-darwin.zip"), "macos")
        self.assertEqual(refresh.detect_os("velociraptor-v0.74.1-linux-amd64"), "linux")
        self.assertEqual(refresh.detect_os("tool-linux-musl.tar.gz"), "linux")

    def test_skipped(self):
        for name in ("tool-win-x64.zip.sha256", "tool.msi.asc", "tool-1.0-src.zip", "tool-1.0.tar.gz",
                     "checksums.txt", "tool-windows-symbols.zip", "tool-linux.bin", "app-release.apk",
                     "tool-win-linux-mac.zip"):
            self.assertIsNone(refresh.detect_os(name), name)


class Classify(unittest.TestCase):
    def test_prefers_installer_and_x64(self):
        picked = refresh.classify_assets([asset(n) for n in (
            "imhex-1.37-Windows-x86_64.msi", "imhex-1.37-Windows-Portable-x86_64.zip",
            "imhex-1.37-Windows-Portable-NoGPU-x86_64.zip", "imhex-1.37-macOS-arm64.dmg",
            "imhex-1.37-x86_64.AppImage", "imhex-1.37-Ubuntu-24.04-x86_64.deb", "imhex-1.37-Debian-12-x86_64.deb",
            "imhex-1.37-Windows-x86_64.msi.sha256")])
        self.assertEqual(picked["windows"]["name"], "imhex-1.37-Windows-x86_64.msi")
        self.assertEqual(picked["macos"]["name"], "imhex-1.37-macOS-arm64.dmg")
        self.assertEqual(picked["linux"]["name"], "imhex-1.37-x86_64.AppImage")

    def test_arm_not_preferred_on_linux(self):
        picked = refresh.classify_assets([asset("t-linux-arm64.tar.gz"), asset("t-linux-amd64.tar.gz")])
        self.assertEqual(picked["linux"]["name"], "t-linux-amd64.tar.gz")

    def test_plain_variant_wins_a_tie(self):
        picked = refresh.classify_assets([asset(n) for n in (
            "hayabusa-4.4.0-win-x64.zip", "hayabusa-4.4.0-win-x64-live-response.zip", "hayabusa-4.4.0-win-x86.zip",
            "hayabusa-4.4.0-lin-x64-gnu.zip", "hayabusa-4.4.0-lin-x64-musl.zip",
            "imhex-1.38.1-macOS-NoGPU-x86_64.dmg", "imhex-1.38.1-macOS-x86_64.dmg", "imhex-1.38.1-macOS-arm64.dmg")])
        self.assertEqual(picked["windows"]["name"], "hayabusa-4.4.0-win-x64.zip")
        self.assertEqual(picked["linux"]["name"], "hayabusa-4.4.0-lin-x64-gnu.zip")
        self.assertEqual(picked["macos"]["name"], "imhex-1.38.1-macOS-x86_64.dmg")

    def test_addons_are_not_the_main_download(self):
        picked = refresh.classify_assets([asset("IPED-4.3.1_and_java_plugins.zip"),
                                          asset("IPED-4.3.x_plugins_Whisper_FaceRecognition_AgeClassifier_Win64_CPU.zip")])
        self.assertEqual(picked, {})

    def test_musl_only_is_still_picked(self):
        picked = refresh.classify_assets([asset("velociraptor-v0.77.4-linux-amd64-musl.gz"), asset("velociraptor-v0.77.4-linux-amd64.gz"),
                                          asset("velociraptor-v0.77.4-linux-amd64-sumo-musl.gz"), asset("velociraptor-v0.77.4-linux-arm64.gz")])
        self.assertEqual(picked["linux"]["name"], "velociraptor-v0.77.4-linux-amd64.gz")
        self.assertEqual(refresh.classify_assets([asset("t-linux-amd64-musl.tar.gz")])["linux"]["name"], "t-linux-amd64-musl.tar.gz")

    def test_tie_means_no_pick(self):
        picked = refresh.classify_assets([asset("a-win-x64.zip"), asset("b-win-x64.zip")])
        self.assertNotIn("windows", picked)

    def test_only_github_links(self):
        bad = {"name": "tool.exe", "browser_download_url": "https://example.com/tool.exe", "size": 1}
        self.assertEqual(refresh.classify_assets([bad]), {})

    def test_nothing_recognised(self):
        self.assertEqual(refresh.classify_assets([asset("volatility3-2.7.0.tar.gz"), asset("volatility3-2.7.0-py3-none-any.whl")]), {})


if __name__ == "__main__":
    unittest.main()
