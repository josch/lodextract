#!/usr/bin/env python

import os
import re
import struct
from collections import defaultdict
from PIL import Image, ImageDraw
from common import crc24_func, font

def get_color(fname):
    crc = crc24_func(fname)
    # values 0-7 must not be used as they might represent transparency
    # so we are left with 248 values 
    return 8+crc%248

def makedef(indir, outdir, shred=True):
    infiles = defaultdict(list)
    sig = None
    # sanity checks and fill infiles dict
    for f in os.listdir(indir):
        m = re.match('(\d+)_([A-Za-z0-9_]+)_(\d\d)_(\d\d)_([A-Za-z0-9_]+)_(\d+)x(\d+)_(\d+)x(\d+).png', f)
        if not m:
            continue
        t,p,bid,j,fn,fw,fh,lm,tm = m.groups()
        t,bid,j,fw,fh,lm,tm = int(t),int(bid),int(j),int(fw),int(fh),int(lm),int(tm)
        im = Image.open(os.sep.join([indir,f]))
        w,h = im.size
        if im.mode != 'P':
            print "input images must have a palette"
            return False
        cursig =(t,p,im.getpalette())
        if not sig:
            sig = cursig
        else:
            if sig != cursig:
                print "sigs must match - got:"
                print sig
                print cursig
                return False
        if len(fn) > 9:
            print "filename can't be longer than 9 bytes"
            return False
        infiles[bid].append((im,t,p,j,fn,fw,fh,lm,tm))

    if len(infiles) == 0:
        print "no input files detected"
        return False

    # check if j values for all bids are correct and sort them in j order in the process
    for bid in infiles:
        infiles[bid].sort(key=lambda t: t[3])
        for k,(_,_,_,j,_,_,_,_,_) in enumerate(infiles[bid]):
            if k != j:
                print "incorrect j value %d for bid %d should be %d"%(j,bid,k)

    t,p,pal = cursig
    outf = open(outdir+"/"+p+".def", "w+")

    # write the header
    # full width and height are not used and not the same for all frames
    # in some defs, so setting to zero
    outf.write(struct.pack("<IIII", t,0,0,len(infiles)))
    # write the palette
    outf.write(struct.pack("768B", *pal))

    # the bid table requires 16 bytes for each bid and 13+4 bytes for each entry
    bidtablesize = 16*len(infiles)+sum(len(l)*(13+4) for l in infiles.values())
    # the position after the bid table is the header plus palette plus bid table size 
    curoffset = 16+768+bidtablesize

    for bid,l in infiles.items():
        # write bid and number of frames
        # the last two values have unknown meaning
        outf.write(struct.pack("<IIII",bid,len(l),0,0))
        # write filenames
        for _,_,_,_,fn,_,_,_,_ in l:
            outf.write(struct.pack("13s", fn+".pcx"))
        # write data offsets
        for im,_,_,_,_,_,_,_,_ in l:
            outf.write(struct.pack("<I",curoffset))
            w,h = im.size
            # every image occupies one byte per pixel plus 32 byte header
            curoffset += w*h+32

    for bid,l in infiles.items():
        for im,_,p,j,_,fw,fh,lm,tm in l:
            w,h = im.size
            outf.write(struct.pack("<IIIIIIii",w*h,0,fw,fh,w,h,lm,tm))
            if shred:
                im = Image.new("P", (w*3,h*3), get_color(p))
                draw = ImageDraw.Draw(im)
                draw.text((0,0),"%d%s"%(j,p),font=font)
                im = im.resize((w,h),Image.ANTIALIAS)
            buf = ''.join([chr(i) for i in list(im.getdata())])
            outf.write(buf)
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "usage: %s indir outdir"%sys.argv[0]
        exit(1)
    ret = makedef(sys.argv[1], sys.argv[2])
    exit(0 if ret else 1)
