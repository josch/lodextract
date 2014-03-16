#!/usr/bin/env python

# http://aethra-cronicles-remake.googlecode.com/svn-history/r4/trunk/export/sergroj/RSDef.pas
# vcmi/client/CAnimation.cpp

import struct
from PIL import Image, ImageDraw
from collections import defaultdict
import os
from common import crc24_func, font, sanitize_filename

def get_color(fname):
    crc = crc24_func(fname)
    # values 0-7 must not be used as they might represent transparency
    # so we are left with 248 values 
    return 8+crc%248

def extract_def(infile,outdir,shred=True):
    f = open(infile)
    bn = os.path.basename(infile)
    bn = os.path.splitext(bn)[0].lower()

    # t - type
    # blocks - # of blocks
    # the second and third entry are width and height which are not used
    t,_,_,blocks = struct.unpack("<IIII", f.read(16))

    palette = []
    for i in range(256):
        r,g,b = struct.unpack("<BBB", f.read(3))
        palette.extend((r,g,b))

    offsets = defaultdict(list)
    k = 0 # for naming bogus filename entries
    for i in range(blocks):
        # bid - block id
        # entries - number of images in this block
        # the third and fourth entry have unknown meaning
        bid,entries,_,_ = struct.unpack("<IIII", f.read(16))
        names=[]
        # a list of 13 character long filenames
        for j in range(entries):
            name, = struct.unpack("13s", f.read(13))
            name = sanitize_filename(name)
            # if nothing remains, create bogus name
            if len(name) == 0:
                num = "%02d"%k
                if len(bn)+len(num) > 9: # truncate name
                    name = bn[:9-len(num)]+num
                else:
                    name = bn+num
            k+=1
            names.append(name)
        # a list of offsets
        for n in names:
            offs, = struct.unpack("<I", f.read(4))
            offsets[bid].append((n,offs))

    for bid,l in offsets.items():
        for j,(n,offs) in enumerate(l):
            f.seek(offs)
            pixeldata = ""
            # first entry is the size which is unused
            # fmt - encoding format of image data
            # fw,fh - full width and height
            # w,h - width and height, w must be a multiple of 16
            # lm,tm - left and top margin
            _,fmt,fw,fh,w,h,lm,tm = struct.unpack("<IIIIIIii", f.read(32))
            n = os.path.splitext(n)[0]
            outname = "%s"%outdir+os.sep+"%02d_%s_%02d_%02d_%s_%d.png"%(t,bn,bid,j,n,fmt)
            print "writing to %s"%outname

            if w != 0 and h != 0:
                if fmt == 0:
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
                    lineoffs = struct.unpack("<%dH"%h, f.read(2*h))
                    # unknown 
                    _,_ = struct.unpack("<BB", f.read(2))
                    for lineoff in lineoffs:
                        if f.tell() != offs+32+lineoff:
                            print "unexpected offset: %d, expected %d"%(f.tell(),offs+32+lineoff)
                            f.seek(offs+32+lineoff)
                        totalrowlength=0
                        while totalrowlength<w:
                            segment, = struct.unpack("<B", f.read(1))
                            code = segment>>5
                            length = (segment&0x1f)+1
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
                        if f.tell() != offs+32+lineoff:
                            print "unexpected offset: %d, expected %d"%(f.tell(),offs+32+lineoff)
                            f.seek(offs+32+lineoff)
                        totalrowlength=0
                        while totalrowlength<w:
                            segment, = struct.unpack("<B", f.read(1))
                            code = segment>>5
                            length = (segment&0x1f)+1
                            if code == 7: # raw data
                                pixeldata += f.read(length)
                            else: # rle
                                pixeldata += length*chr(code)
                            totalrowlength+=length
                else:
                    print "unknown format: %d"%fmt
                    return False
                im = Image.fromstring('P', (w,h),pixeldata)
            else: # either width or height is zero
                if w == 0:
                    w = 1
                if h == 0:
                    h = 1
                # TODO: encode this information correctly and dont create a fake 1px image
                im = Image.new('P', (w,h))
            if shred:
                #im = Image.new("P", (w*3,h*3), get_color(bn))
                #draw = ImageDraw.Draw(im)
                #tw,th = draw.textsize("%d%s"%(j,bn),font=font)
                #draw.text(((w*3-tw)/2,(h*3-th)/2),"%d%s"%(j,bn),font=font)
                #im = im.resize((w,h),Image.ANTIALIAS)

                #pixels = im.load()
                #color = get_color(bn)
                #for i in range(w):
                #    for j in range(h):
                #        if pixels[i,j] > 7:
                #            pixels[i,j] = color

                color = get_color(bn)
                import numpy as np
                pixels = np.array(im)
                pixels[pixels > 7] = color
                im = Image.fromarray(pixels)
            imo = Image.new('P', (fw,fh))
            imo.putpalette(palette)
            imo.paste(im,(lm,tm))
            #draw = ImageDraw.Draw(imo)
            #tw,th = draw.textsize(bn,font=font)
            #draw.text(((fw-tw)/2,(fh-th)/2),bn,255,font=font)
            imo.save(outname)
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "usage: %s input.def ./outdir"%sys.argv[0]
        print "to process all files:"
        print "    for f in *.def; do n=`basename $f .def`; mkdir -p defs/$n; %s defextract.py $f defs/$n; done"%sys.argv[0]
        exit(1)
    ret = extract_def(sys.argv[1], sys.argv[2])
    exit(0 if ret else 1)
