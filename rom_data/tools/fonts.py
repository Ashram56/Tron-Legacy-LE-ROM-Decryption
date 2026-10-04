"""Font table -> rom_data/fonts.json.

Source: font count u32 RAM 0x36f44, table pointer RAM 0x36f48 (data address 0x04000000 + ptr),
20-byte records read by text_width 0x28a74 / text_draw_str 0x28f74:
  +0x00 u32  char-range list (offset in the bank at +0x10): byte pairs (first, last), 0-terminated
  +0x04 u32  glyph table (same bank), 8 bytes per char in range order: u32 image ptr (banked),
             s16 x offset, s16 y offset
  +0x08 u16  height (font_height 0x28940)
  +0x0a s16  spacing added after every glyph
  +0x0c u32  non-zero: glyphs drawn masked (pixel 255 transparent, bitmap_blit_masked)
  +0x10 u8   flash bank of the lists
Drawing (text_draw_str): flag 2 centres (x -= width//2), flag 4 right-aligns (x = x + 1 - width);
each glyph is blitted at (x + xoff, y - glyph_h + yoff + 1); then x += glyph_w + xoff + spacing.
text_width returns max_right - min_left over the same pen walk (pen before spacing).
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from rom import *  # noqa

OUT = os.path.join(os.path.dirname(__file__), "..", "fonts.json")

NIMG = u32(0x36f4c)
IMG_TAB = u32(0x36f50)
img_index = {}
for i in range(NIMG):
    img_index[fu32(IMG_TAB + 4 * i)] = i


def img_hdr(p):
    o = banked(p)
    return dict(rid=fu16(o), group=fu16(o + 2), flags=fu32(o + 4), w=fs16(o + 8), h=fs16(o + 10), format=ROM[o + 12])


NF = u32(0x36f44)
FT = u32(0x36f48)
fonts = []
for f in range(NF):
    a = 0x04000000 + FT + f * 0x14
    rng_p, gl_p, height, spacing, masked, bank = u32(a), u32(a + 4), u16(a + 8), s16(a + 10), u32(a + 12), u8(a + 16)
    base = bank * 0x800000
    ranges, o = [], base + rng_p
    while ROM[o]:
        ranges.append((ROM[o], ROM[o + 1]))
        o += 2
    glyphs, k = {}, 0
    for lo, hi in ranges:
        for c in range(lo, hi + 1):
            g = base + gl_p + 8 * k
            ip, xo, yo = fu32(g), fs16(g + 4), fs16(g + 6)
            hd = img_hdr(ip)
            glyphs[chr(c)] = dict(code=c, image=img_index.get(ip), image_ptr=hx(ip, 8), rid=hd["rid"],
                                  w=hd["w"], h=hd["h"], x_offset=xo, y_offset=yo,
                                  advance=hd["w"] + xo + spacing)
            k += 1
    imgs = [g["image"] for g in glyphs.values() if g["image"] is not None]
    fonts.append(dict(font=f, record_addr=hx(a, 8), height=height, spacing=spacing, masked=bool(masked),
                      bank=bank, ranges=[[chr(lo), chr(hi)] for lo, hi in ranges],
                      range_list_file_offset=hx(base + rng_p), glyph_table_file_offset=hx(base + gl_p),
                      image_first=min(imgs) if imgs else None, image_last=max(imgs) if imgs else None,
                      chars="".join(glyphs), glyphs=glyphs))

doc = {
    "source": "ROM trn_174h (Tron LE 1.74): font table RAM 0x36f48 -> 0x04000000+0x%x, count RAM 0x36f44 = %d" % (FT, NF),
    "tag": "code",
    "placement": {
        "glyph_blit": "x_draw = pen_x + x_offset; y_draw = y - h + y_offset + 1 (y = baseline row passed to the draw call)",
        "pen_advance": "pen_x += w + x_offset + spacing",
        "flags": {"1": "fit only: allow x + width <= 128 (font lists, max_width 0)", "2": "centre: x -= text_width // 2", "4": "right: x = x + 1 - text_width"},
        "text_width": "max(pen positions after each glyph, before spacing) - min(pen positions) -- code 0x28a74",
        "masked": "true: pixel 255 in the glyph image is transparent (bitmap_blit_masked 0x2b2a0), else opaque blit 0x2b194",
        "image": "index into the ROM image table (RAM 0x36f50); = file name NNNN.png in mpf_package/media/rom_images_all.zip",
    },
    "fonts": fonts,
}
json.dump(doc, open(OUT, "w"), indent=1)
for f in fonts:
    print(f["font"], f["height"], f["spacing"], f["masked"], f["image_first"], f["image_last"], "".join(f["chars"])[:70])
