"""Date font regression checks: python -m unittest discover -s tests -p test_date_font.py."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / 'src/font_sora_26.c'
CHARS = '0123456789ADEFHIMORSTUW'


def cmaps(source):
    return [tuple(map(int, values)) for values in re.findall(
        r'\.range_start = (\d+), \.range_length = (\d+), \.glyph_id_start = (\d+)', source)]


def descriptors(source):
    section = source.split('glyph_dsc[] = {', 1)[1].split('};', 1)[0]
    return [tuple(map(int, values)) for values in re.findall(
        r'\.bitmap_index = (\d+), \.adv_w = (\d+), \.box_w = (\d+), \.box_h = (\d+)', section)]


class DateFontTest(unittest.TestCase):
    def test_all_weekday_and_date_characters_have_real_glyphs(self):
        source = FONT.read_text(encoding='utf-8')
        clock = (ROOT / 'src/clock_view.cpp').read_text(encoding='utf-8')
        clock = clock.split('static void draw_date_de(', 1)[1].split('static void draw_baked_text(', 1)[0]
        arrays = re.findall(r'WD_(?:EN|DE)\[7\] = \{([^}]+)\}', clock)
        self.assertEqual(len(arrays), 2)
        required = set('0123456789 ' + ''.join(re.findall(r'"([A-Z]+)"', ''.join(arrays))))
        ranges = cmaps(source)
        glyphs = descriptors(source)
        for ch in sorted(required):
            with self.subTest(character=ch):
                matches = [(start, length, gid) for start, length, gid in ranges
                           if 0 <= ord(ch) - start < length]
                self.assertEqual(len(matches), 1, f'Missing or ambiguous glyph: {ch}')
                start, _, gid = matches[0]
                index = gid + ord(ch) - start
                self.assertTrue(0 < index < len(glyphs))
                if ch != ' ':
                    self.assertGreater(glyphs[index][2] * glyphs[index][3], 0)

    def test_every_glyph_bitmap_fits_the_actual_array(self):
        source = FONT.read_text(encoding='utf-8')
        bitmap = source.split('glyph_bitmap[] = {', 1)[1].split('};', 1)[0]
        size = len(re.findall(r'0x[0-9a-fA-F]{2}', bitmap))
        for offset, _, width, height in descriptors(source):
            self.assertLessEqual(offset + (width * height + 1) // 2, size)

    def test_generation_is_deterministic_and_preserves_font_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'font_sora_26.c'
            subprocess.run([sys.executable, str(ROOT / 'tools/gen_lv_font.py'),
                            str(ROOT / 'assets/fonts/Sora-Variable.ttf'), '26', '400',
                            'font_sora_26', CHARS, str(output)], check=True, capture_output=True)
            first = output.read_bytes()
            subprocess.run([sys.executable, str(ROOT / 'tools/gen_lv_font.py'),
                            str(ROOT / 'assets/fonts/Sora-Variable.ttf'), '26', '400',
                            'font_sora_26', CHARS, str(output)], check=True, capture_output=True)
            self.assertEqual(first, output.read_bytes())
            # FreeType builds can rasterise edge pixels differently on Windows/Linux.
            # Keep coverage and line metrics identical without pinning those pixels.
            generated = first.decode('utf-8')
            committed = FONT.read_text(encoding='utf-8')
            self.assertEqual(cmaps(generated), cmaps(committed))
            self.assertEqual(len(descriptors(generated)), len(descriptors(committed)))
            self.assertIn('.line_height = 34, .base_line = 8,', generated)

    def test_generator_guards_both_lvgl_entry_points(self):
        # Use the original dangerous final range R..S: LVGL 8.4.0 maps T to the
        # next descriptor. Generated callbacks must reject it before calling LVGL.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'subset.c'
            subprocess.run([sys.executable, str(ROOT / 'tools/gen_lv_font.py'),
                            str(ROOT / 'assets/fonts/Sora-Variable.ttf'), '26', '400',
                            'subset', 'RS', str(output)], check=True, capture_output=True)
            source = output.read_text(encoding='utf-8')
            ranges = cmaps(source)
            count = len(descriptors(source))
            unsafe_id = next(gid + ord('T') - start for start, length, gid in ranges
                             if 0 <= ord('T') - start <= length)
            self.assertEqual(unsafe_id, count)  # reproduction of the old overread
            self.assertFalse(any(0 <= ord('T') - start < length for start, length, _ in ranges))
            self.assertIn('if(relative < cmaps[i].range_length)', source)
            self.assertIn('if(!has_glyph(letter)) return false;', source)
            self.assertIn('if(!has_glyph(letter)) return NULL;', source)
            self.assertIn('.get_glyph_dsc = get_glyph_dsc,', source)
            self.assertIn('.get_glyph_bitmap = get_glyph_bitmap,', source)


if __name__ == '__main__':
    unittest.main()
