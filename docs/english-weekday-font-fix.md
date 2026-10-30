# English weekday date font fix

The date window selects English SU/MO/TU/WE/TH/FR/SA or German SO/MO/DI/MI/DO/FR/SA.
The original Sora 26 subset contained the German letters but omitted English E/H/T/U/W.

LVGL 8.4.0 checks `relative > range_length` rather than `relative >= range_length` in
its fmt_txt cmap lookup. The original final range starts at R (82), has length 2,
and starts at glyph 18. Requesting T (84) therefore returned glyph 20 even though
only descriptors 0 through 19 exist. Reading that descriptor is undefined behavior
and can turn unrelated memory into glyph dimensions and bitmap data. This matches
the reported Tuesday/Thursday corruption and clearing at midnight, but the patched
firmware still requires testing on the physical ORB.

The fix regenerates the date font with the union of both languages' weekday letters
and all date digits. It also makes generated C font callbacks reject code points
outside their cmap ranges before calling LVGL. This preserves normal LVGL fallback
handling and avoids changing or patching installed PlatformIO dependencies. Other
existing generated fonts are unchanged; they gain this guard when regenerated.
Binary font output is unchanged and does not use the generated C callback guard.

Regenerate from the repository root:

```sh
python tools/gen_lv_font.py assets/fonts/Sora-Variable.ttf 26 400 font_sora_26 "0123456789ADEFHIMORSTUW" src/font_sora_26.c
python -m unittest discover -s tests -p test_date_font.py -v
```

Generation was checked with Pillow 12.3.0. Original 26 px size, weight 400,
34 px line height and 8 px baseline are preserved. The bitmap grows by 951 bytes.
CI also checks C compilation against the pinned LVGL 8.4.0 headers.

After building and installing firmware, validate English TU and TH on the device,
then all other weekdays and the German abbreviations. Installing a theme alone
cannot replace this font: font_sora_26 is compiled into the firmware.
