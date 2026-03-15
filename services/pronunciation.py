"""Text-to-speech adapter for German pronunciation."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from gtts import gTTS
from playsound import playsound


class PronunciationService:
    """Generate and play German word pronunciation."""

    def play(self, german_word: str) -> tuple[bool, str]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            temp_path = Path(tmp.name)
        try:
            tts = gTTS(text=german_word, lang="de")
            tts.save(str(temp_path))
            ok, message = self._play_file(temp_path)
            if ok:
                return True, "played"
            return False, message
        except Exception as exc:
            return False, f"TTS generation failed: {exc}"
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _play_file(self, path: Path) -> tuple[bool, str]:
        try:
            playsound(str(path))
            return True, "played with playsound"
        except Exception:
            pass

        # WSL/Linux fallbacks.
        for command in (
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
            ["mpg123", "-q", str(path)],
            ["paplay", str(path)],
            ["aplay", str(path)],
        ):
            try:
                result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=8)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0:
                return True, f"played with {command[0]}"

        wsl_ok, wsl_message = self._play_in_wsl_windows(path)
        if wsl_ok:
            return True, wsl_message

        return False, "No working audio backend (playsound/ffplay/mpg123/paplay/aplay)."

    def _play_in_wsl_windows(self, path: Path) -> tuple[bool, str]:
        """Fallback for WSL: play audio using Windows Media Player COM object."""
        if not self._is_wsl():
            return False, "not running in WSL"

        try:
            win_path = subprocess.run(
                ["wslpath", "-w", str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if win_path.returncode != 0:
                return False, "wslpath conversion failed"
            path_windows = win_path.stdout.strip().replace("'", "''")
            if not path_windows:
                return False, "empty Windows path"

            script = (
                "$p = New-Object -ComObject WMPlayer.OCX;"
                f"$p.URL = '{path_windows}';"
                "$p.controls.play();"
                "Start-Sleep -Seconds 3;"
                "$p.close();"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=6,
            )
            if result.returncode == 0:
                return True, "played with powershell.exe (WMPlayer)"
            return False, "powershell playback failed"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "powershell.exe not available"

    @staticmethod
    def _is_wsl() -> bool:
        return bool(os.environ.get("WSL_DISTRO_NAME")) or bool(os.environ.get("WSL_INTEROP"))
