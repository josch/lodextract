import crcmod
import colorsys

from PIL import ImageFont

font = ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans.ttf", 34)

def sanitize_filename(fname):
    # find the first character outside range [32-126]
    for i,c in enumerate(fname):
        if ord(c) < 32 or ord(c) > 126:
            break
    return fname[:i]

def get_complement(r,g,b):
    r = r/255.0
    g = g/255.0
    b = b/255.0
    h,l,s = colorsys.rgb_to_hls(r, g, b)
    if h > 0.5:
        h -= 0.5
    else:
        h += 0.5
    r,g,b = colorsys.hls_to_rgb(h, l, s)
    return int(r*255), int(g*255), int(b*255)

crc24_func = crcmod.mkCrcFun(0x1864CFBL) # polynomial from libgcrypt
