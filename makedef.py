#!/usr/bin/env python

import os
import re
import struct
from collections import defaultdict
from PIL import Image
ushrtmax = (1<<16)-1

# greedy RLE
# for each pixel, test which encoding results in the smaller size, then apply
# that encoding and look at the next pixel after the encoded chunk
def encode1(im):
    pixels = im.load()
    w,h = im.size
    result = []
    # these function return a tuple of the compressed string and the amount of
    # pixels compressed
    def rle_comp(x,y):
        # find all pixels after the first one with the same color
        color = pixels[x,y]
        if color == 0xff:
            # this color can't be run length encoded
            return raw_comp(x,y)
        else:
            count = 1
            for x in range(x+1,w):
                if pixels[x,y] == color and count < 255:
                    count += 1
                else:
                    break
            return (struct.pack("<BB", color, count-1), count)
    def raw_comp(x,y):
        # read pixels until finding finding two consecutive ones with the same color
        data = [pixels[x,y]]
        for x in range(x+1,w):
            color = pixels[x,y]
            if color != data[-1] and len(data) < 255:
                data.append(color)
            else:
                break
        return (struct.pack("<BB%dB"%len(data), 0xff, len(data)-1, *data), len(data))
    for y in range(h):
        r = ''
        x = 0
        while x < w:
            rlec, rlel = rle_comp(x, y)
            rawc, rawl = raw_comp(x, y)
            # the message that managed to encode more is chosen 
            if rlel > rawl:
                r += rlec
                x += rlel
            else:
                r += rawc
                x += rawl
        result.append(r)
    return result

def encode3(im):
    pixels = im.load()
    w,h = im.size
    result = []
    for y in range(h):
        r = ''
        if pixels[0,y] < 8:
            colors = pixels[0,y]
            count = 1
        else:
            colors = [pixels[0,y]]
            count = 0
        for x in range(1,w):
            color = pixels[x,y]
            if count > 0:
                # rle was started
                if color == colors and count < 32:
                    # same color again, increase count
                    count+=1
                else:
                    # either new color or maximum length reached, so write current one
                    r+=struct.pack("<B", (colors<<5) | (count-1))
                    if color < 7:
                        # new rle color
                        colors = color
                        count = 1
                    else:
                        # new non rle color
                        colors = [color]
                        count = 0
            else:
                # non rle was started
                if color < 7 or len(colors) > 31:
                    # new rle color, or maximum length reached so write current non rle
                    r+=struct.pack("<B", (7<<5) | (len(colors)-1))
                    r+=struct.pack("<%dB"%len(colors), *colors)
                    if color < 7:
                        colors = color
                        count = 1
                    else:
                        colors = [color]
                        count = 0
                else:
                    # new non rle color, so append it to current
                    colors.append(color)
        # write last color
        if count > 0:
            # write rle
            r+=struct.pack("<B", (colors<<5) | (count-1))
        else:
            # write non rle
            r+=struct.pack("<B", (7<<5) | (len(colors)-1))
            r+=struct.pack("<%dB"%len(colors), *colors)
        result.append(r)
    return result

def makedef(indir, outdir):
    infiles = defaultdict(list)
    sig = None
    # sanity checks and fill infiles dict
    for f in os.listdir(indir):
        m = re.match('(\d+)_([a-z0-9_]+)_(\d\d)_(\d\d)_([A-Za-z0-9_]+)_(\d+)x(\d+)_(\d+)x(\d+)_([0-3]).png', f)
        if not m:
            continue
        t,p,bid,j,fn,fw,fh,lm,tm,fmt = m.groups()
        t,bid,j,fw,fh,lm,tm,fmt = int(t),int(bid),int(j),int(fw),int(fh),int(lm),int(tm),int(fmt)
        im = Image.open(os.sep.join([indir,f]))
        w,h = im.size
        if im.mode != 'P':
            print "input images must have a palette"
            return False
        cursig =(t,p,fw,fh,im.getpalette(),fmt)
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
        if fmt == 0:
            data = ''.join([chr(i) for i in list(im.getdata())])
        elif fmt == 1:
            data = encode1(im)
        elif fmt == 2:
            data = encode3(im)
        elif fmt == 3:
            if w < 16:
                print "width must not be less than 16 for format 3"
                return False
            data = encode3(im)
        else:
            print "unknown format: %d"%fmt
            return False
        infiles[bid].append((im,t,p,j,fn,lm,tm,fmt,data))

    if len(infiles) == 0:
        print "no input files detected"
        return False

    # check if j values for all bids are correct and sort them in j order in the process
    for bid in infiles:
        infiles[bid].sort(key=lambda t: t[3])
        for k,(_,_,_,j,_,_,_,_,_) in enumerate(infiles[bid]):
            if k != j:
                print "incorrect j value %d for bid %d should be %d"%(j,bid,k)

    t,p,fw,fh,pal,fmt = cursig
    outname = os.path.join(outdir,p)+".def"
    print "writing to %s"%outname
    outf = open(outname, "w+")

    # write the header
    # full width and height are not used and not the same for all frames
    # in some defs, so just putting the last known value
    outf.write(struct.pack("<IIII", t,fw,fh,len(infiles)))
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
        for im,_,_,_,_,_,_,fmt,data in l:
            outf.write(struct.pack("<I",curoffset))
            w,h = im.size
            # every image occupies size depending on its format plus 32 byte header
            if fmt == 0:
                curoffset += 32+len(data)
            elif fmt == 1:
                # 4*height bytes for lineoffsets
                curoffset += 32+4*h+sum(len(d) for d in data)
            elif fmt == 2:
                # two bytes for the header
                curoffset += 32+2+sum(len(d) for d in data)
            elif fmt == 3:
                # width/16 bytes per line as offset header
                curoffset += 32+(w/16)*h+sum(len(d) for d in data)

    for bid,l in infiles.items():
        for im,_,p,j,_,lm,tm,fmt,data in l:
            w,h = im.size
            # size
            # format
            # full width and full height
            # width and height
            # left and top margin 
            outf.write(struct.pack("<IIIIIIii",w*h,fmt,fw,fh,w,h,lm,tm))
            if fmt == 0:
                buf = ''.join([chr(i) for i in list(im.getdata())])
                outf.write(buf)
            elif fmt == 1:
                lineoffs = []
                acc = 4*h
                for d in data:
                    lineoffs.append(acc)
                    acc += len(d)
                outf.write(struct.pack("<"+"I"*h, *lineoffs))
                for i in data:
                    outf.write(i)
            elif fmt == 2:
                offs = outf.tell()-32+2
                if offs > ushrtmax: 
                    print "exceeding max ushort value: %d"%offs
                    return False
                outf.write(struct.pack("<H",offs))
                for i in data:
                    outf.write(i)
            elif fmt == 3:
                # store the same value in all w/16 blocks per line
                lineoffs = []
                acc = 0
                for d in data:
                    offs = acc+(w/16)*h
                    if offs > ushrtmax:
                        print "exceeding max ushort value: %d"%offs
                        return False
                    lineoffs.append(offs)
                    lineoffs.extend([0 for i in range(w/32-1)])
                    acc += len(d)
                outf.write(struct.pack("<"+"H"*(w/32)*h, *lineoffs))
                for i in data:
                    outf.write(i)
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "usage: %s indir outdir"%sys.argv[0]
        exit(1)
    ret = makedef(sys.argv[1], sys.argv[2])
    exit(0 if ret else 1)
