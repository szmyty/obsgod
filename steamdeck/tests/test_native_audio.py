"""Verify the media detector rejects silence, wrong routes and mixed decoys."""
import importlib.util
import math
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("native_audio_metrics", Path(__file__).with_name("native-audio.py"))
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class NativeAudioMetrics(unittest.TestCase):
    def tone(self, frequency, second=0):
        return [int(0.2 * 32767 * (math.sin(2 * math.pi * frequency * index / 48000) + second * math.sin(2 * math.pi * 880 * index / 48000))) for index in range(48000)]

    def test_digital_silence_is_not_accepted(self):
        result = audio.measurements([0] * 48000, 48000, 440)
        self.assertFalse(result["audible"])
        self.assertFalse(result["expected_tone"])
        self.assertIsNone(result["rms_dbfs"])

    def test_audible_expected_tone_is_measured(self):
        result = audio.measurements(self.tone(440), 48000, 440)
        self.assertTrue(result["audible"])
        self.assertTrue(result["expected_tone"])
        self.assertGreater(result["rms_dbfs"], -20)
        self.assertLess(result["rms_dbfs"], -15)

    def test_loud_wrong_sink_is_not_accepted(self):
        result = audio.measurements(self.tone(880), 48000, 440)
        self.assertTrue(result["audible"])
        self.assertFalse(result["expected_tone"])

    def test_mixed_decoy_is_not_accepted(self):
        result = audio.measurements(self.tone(440, second=1), 48000, 440)
        self.assertTrue(result["audible"])
        self.assertFalse(result["expected_tone"])


if __name__ == "__main__":
    unittest.main()
