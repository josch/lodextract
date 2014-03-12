#!/usr/bin/env python

# http://aethra-cronicles-remake.googlecode.com/svn-history/r4/trunk/export/sergroj/RSDef.pas
# vcmi/client/CAnimation.cpp

import struct
from PIL import Image
from collections import defaultdict
import os

def extract_def(infile,outdir):
    f = open(infile)
    # t - type
    # blocks - # of blocks
    # the second and third entry are width and height which are not used
    t,_,_,blocks = struct.unpack("<IIII", f.read(16))

    palette = []
    for i in range(256):
        r,g,b = struct.unpack("<BBB", f.read(3))
        palette.extend((r,g,b))

    offsets = defaultdict(list)
    for i in range(blocks):
        # bid - block id
        # entries - number of images in this block
        # the third and fourth entry have unknown meaning
        bid,entries,_,_ = struct.unpack("<IIII", f.read(16))
        names=[]
        # a list of 13 character long filenames
        for j in range(entries):
            name, = struct.unpack("13s", f.read(13))
            name = name[:name.index('\0')]
            names.append(name)
        # a list of offsets
        for n in names:
            offs, = struct.unpack("<I", f.read(4))
            offsets[bid].append((n,offs))

    bn = os.path.basename(infile)
    bn = os.path.splitext(bn)[0]
    for bid,l in offsets.items():
        for n,offs in l:
            f.seek(offs)
            pixeldata = ""
            # first entry is the size which is unused
            # fmt - encoding format of image data
            # fw,fh - full width and height
            # w,h - width and height, w must be a multiple of 16
            # lm,tm - left and top margin
            _,fmt,fw,fh,w,h,lm,tm = struct.unpack("<IIIIIIii", f.read(32))
            n = os.path.splitext(n)[0]
            outname = "%s"%outdir+os.sep+"%s_%02d_%s_%dx%d_%dx%d.png"%(bn,bid,n,fw,fh,lm,tm)
            print "writing to %s"%outname
            if fmt == 0:
                # uncompressed, so the following *should* work but there is no
                # test data
                pixeldata = f.read(w*h)
            elif fmt == 1:
                # SGTWMTA.def and SGTWMTB.def fail here
                # they have inconsistent left and top margins
                # they seem to be unused
                if lm > fw or tm > fh:
                    print "margins (%dx%d) are higher than dimensions (%dx%d)"%(lm,tm,fw,fh)
                    return False
                lineoffs = struct.unpack("<"+"I"*h, f.read(4*h))
                for lineoff in lineoffs:
                    f.seek(offs+32+lineoff)
                    totalrowlength=0
                    while totalrowlength<w:
                        code,length = struct.unpack("<BB", f.read(2))
                        length+=1
                        if code == 0xff: #raw data
                            pixeldata += f.read(length)
                        else: # rle
                            pixeldata += length*chr(code)
                        totalrowlength+=length
            elif fmt == 2:
                coff, = struct.unpack("<H", f.read(2))
                coff += 32
                f.seek(coff)
                for i in range(h):
                    totalrowlength=0
                    while totalrowlength<w:
                        segment, = struct.unpack("<B", f.read(1))
                        code = segment/32
                        length = (segment&31)+1
                        if code == 7: # raw data
                            pixeldata += f.read(length)
                        else: # rle
                            pixeldata += length*chr(code)
                        totalrowlength+=length
            elif fmt == 3:
                # the first unsigned short in every w/16 byte block is the
                # offset we want - the others have an unknown function
                lineoffs = [struct.unpack("<"+"H"*(w/32), f.read(w/16))[0] for i in range(h)]

                for lineoff in lineoffs:
                    f.seek(offs+32+lineoff)
                    totalrowlength=0
                    while totalrowlength<w:
                        segment, = struct.unpack("<B", f.read(1))
                        code = segment/32
                        length = (segment&31)+1
                        if code == 7: # raw data
                            pixeldata += f.read(length)
                        else: # rle
                            pixeldata += length*chr(code)
                        totalrowlength+=length
            else:
                print "unknown format: %d"%fmt
                return False
            im = Image.fromstring('P', (w,h),pixeldata)
            im.putpalette(palette)
            im.save(outname)
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "usage: %s input.def ./outdir"%sys.argv[0]
        print "to process all files:"
        print "    for f in *.def; do n=`basename $f .def`; mkdir -p defs/$n; $s defextract.py $f defs/$n; done"%sys.argv[0]
        exit(1)
    ret = extract_def(sys.argv[1], sys.argv[2])
    exit(0 if ret else 1)
