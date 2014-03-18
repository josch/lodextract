#!/usr/bin/env python

import numpy as np
from PIL import Image
import crcmod
import os

crc24_func = crcmod.mkCrcFun(0x1864CFBL) # polynomial from libgcrypt

def handle_img(inf, color):
    with open(inf) as f:
        im = Image.open(f)
        pal = im.getpalette()
        pixels = np.array(im)
    if pal:
        pal[765], pal[766], pal[767] = color
        pixels[pixels > 7] = 255
        im = Image.fromarray(pixels)
        im.putpalette(pal)
    else:
        # non-palette pictures have no transparency
        im = Image.new('RGB', im.size, color)
        # in case we ever want to replace colors in rgb images: 
        #rc, gc, bc = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2]
        #mask = (rc == 0) & (gc == 255) & (bc == 255)
        #pixels[:,:,:3][mask] = color
    im.save(inf)

def main(inf):
    print "processing %s"%inf
    crc = crc24_func(inf)
    r = crc>>16
    g = (crc&0xff00)>>8
    b = crc&0xff
    color = r%255,g%255,b%255 # avoid hitting special values
    if os.path.isdir(inf):
        for fname in os.listdir(inf):
            fname = os.path.join(inf,fname)
            handle_img(fname, color)
    else:
        handle_img(inf, color)
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print "usage: %s indir/infile"
        exit(0)
    ret = main(sys.argv[1])
    exit(0 if ret else 1)
