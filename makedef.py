#!/usr/bin/env python
#
# Copyright (C) 2014  Johannes Schauer <j.schauer@email.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import struct
import json
from collections import defaultdict
from PIL import Image
import numpy as np

ushrtmax = (1<<16)-1

def encode0(im):
    data = ''.join([chr(i) for i in list(im.getdata())])
    size = len(data)
    return data,size

# greedy RLE
# for each pixel, test which encoding manages to encode most data, then apply
# that encoding and look at the next pixel after the encoded chunk
def encode1(im):
    pixels = im.load()
    w,h = im.size
    data = []
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
        data.append(r)
    # 4*height bytes for lineoffsets
    size = 4*h+sum([len(d) for d in data])
    return data,size

def encode23chunk(s,e,pixels,y):
    r = ''
    if pixels[s,y] < 8:
        colors = pixels[s,y]
        count = 1
    else:
        colors = [pixels[s,y]]
        count = 0
    for x in range(s+1,e):
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
    return r

# this is like encode3 but a line is not split into 32 pixel chuncks
# the reason for this might just be that format 2 images are always 32 pixel wide
def encode2(im):
    pixels = im.load()
    w,h = im.size
    data = []
    for y in range(h):
        data.append(encode23chunk(0,w,pixels,y))
    # 2*height bytes for lineoffsets plus two unknown bytes
    size = 2*h+2+sum(len(d) for d in data)
    return data,size

# this is like encode2 but limited to only encoding blocks of 32 pixels at a time
def encode3(im):
    pixels = im.load()
    w,h = im.size
    data = []
    for y in range(h):
        res = []
        # encode each row in 32 pixel blocks
        for i in range(w/32):
            res.append(encode23chunk(i*32, (i+1)*32, pixels, y))
        data.append(res)
    # width/16 bytes per line as offset header
    size = (w/16)*h+sum(sum([len(e) for e in d]) for d in data)
    return data,size

fmtencoders = [encode0,encode1,encode2,encode3]

def makedef(infile, outdir):
    infiles = defaultdict(list)
    sig = None

    with open(infile) as f:
        in_json = json.load(f)

    t = in_json["type"]
    fmt = in_json["format"]
    p = os.path.basename(infile)
    p = os.path.splitext(p)[0].lower()
    d = os.path.dirname(infile)

    outname = os.path.join(outdir,p)+".def"
    print "writing to %s"%outname

    # sanity checks and fill infiles dict
    for seq in in_json["sequences"]:
        bid = seq["group"]
        for f in seq["frames"]:
            im = Image.open(os.path.join(d,f))
            fw,fh = im.size
            if fmt == 2 and (fw != 32 or fh != 32):
                print "format 2 must have width and height 32"
                return False
            lm,tm,rm,bm = im.getbbox() or (0,0,0,0)
            # format 3 has to have width and lm divisible by 32
            if fmt == 3 and lm%32 != 0:
                # shrink lm to the previous multiple of 32
                lm = (lm/32)*32
            w,h = rm-lm,bm-tm
            if fmt == 3 and w%32 != 0:
                # grow rm to the next multiple of 32
                w = (((w-1)>>5)+1)<<5
                rm = lm+w
            im = im.crop((lm,tm,rm,bm))
            if im.mode == 'P':
                cursig =(fw,fh,im.getpalette())
            elif im.mode == 'RGBA':
                cursig =(fw,fh,None)
            else:
                print "input images must be rgba or palette based"
                return False
            if not sig:
                sig = cursig
            else:
                if sig != cursig:
                    print "sigs must match - got:"
                    print sig
                    print cursig
                    return False
            infiles[bid].append((lm,tm,im))

    if len(infiles) == 0:
        print "no input files detected"
        return False

    fw,fh,pal = cursig
    numframes = sum(len(l) for l in infiles.values())

    # input images were RGB, find a good common palette
    if not pal:
        # create a concatenation of all images to create a good common palette
        concatim = Image.new("RGB",(fw,fh*numframes))
        num = 0
        for _,l in infiles.items():
            for _,_,im in l:
                concatim.paste(im, (0,fh*num))
                num+=1
        # convert that concatenation to a palette image to obtain a good common palette
        concatim = concatim.convert("P", dither=None, colors=248, palette=Image.ADAPTIVE)
        # concatenate the 248 colors to the 8 special ones
        pal = [0x00, 0xff, 0xff, # full transparency
               0xff, 0x96, 0xff, # shadow border
               0xff, 0x64, 0xff, # ???
               0xff, 0x32, 0xff, # ???
               0xff, 0x00, 0xff, # shadow body
               0xff, 0xff, 0x00, # selection highlight
               0xb4, 0x00, 0xff, # shadow body below selection
               0x00, 0xff, 0x00, # shadow border below selection
               ] + concatim.getpalette()[:744]
        # convert RGBA images to P images with the common palette
        for bid,l in infiles.items():
            newl = []
            for lm,tm,im in l:
                w,h = im.size
                if w == 0 or h == 0:
                    imp = None
                else:
                    # must convert to RGB first for quantize() to work
                    imrgb = im.convert("RGB")
                    imp = imrgb.quantize(palette=concatim)
                    # now shift the colors by 8
                    pix = np.array(imp)
                    pix += 8
                    imp = Image.fromarray(pix)
                    # now replace full transparency in the original RGBA image with index 0
                    pixrgba = np.array(im)
                    alpha = pixrgba[:,:,3]
                    pix[alpha == 0] = 0
                    # now replace any half-transpareny with shadow body (index 4)
                    pix[(alpha > 0) & (alpha < 0xff)] = 4
                    # TODO: calculate shadow border
                    # now put the palette with the special colors
                    imp.putpalette(pal)
                newl.append((lm,tm,imp))
            infiles[bid] = newl

    # encode all images according to the required format
    for bid,l in infiles.items():
        newl = []
        for lm,tm,im in l:
            if im:
                w,h = im.size
                data,size = fmtencoders[fmt](im)
            else:
                w,h = 0,0
                data,size = '',0
            newl.append((w,h,lm,tm,data,size))
        infiles[bid] = newl

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
        for i,_ in enumerate(l):
            fn = "%02d_%03d.pcx"%(bid,i)
            outf.write(struct.pack("13s", fn))
        # write data offsets
        for w,h,_,_,data,size in l:
            outf.write(struct.pack("<I",curoffset))
            # every image occupies size depending on its format plus 32 byte header
            curoffset += 32+size

    for bid,l in infiles.items():
        for w,h,lm,tm,data,size in l:
            # size
            # format
            # full width and full height
            # width and height
            # left and top margin
            if fmt == 0:
                outf.write(struct.pack("<IIIIIIii",size,fmt,fw,fh,w,h,lm,tm))
                outf.write(data)
            elif fmt == 1:
                outf.write(struct.pack("<IIIIIIii",size,fmt,fw,fh,w,h,lm,tm))
                lineoffs = []
                acc = 4*h
                for d in data:
                    lineoffs.append(acc)
                    acc += len(d)
                outf.write(struct.pack("<"+"I"*h, *lineoffs))
                for i in data:
                    outf.write(i)
            elif fmt == 2:
                outf.write(struct.pack("<IIIIIIii",size,fmt,fw,fh,w,h,lm,tm))
                lineoffs = []
                acc = 0
                for d in data:
                    offs = acc+2*h+2
                    if offs > ushrtmax: 
                        print "exceeding max ushort value: %d"%offs
                        return False
                    lineoffs.append(offs)
                    acc += len(d)
                outf.write(struct.pack("<%dH"%h, *lineoffs))
                outf.write(struct.pack("<BB", 0, 0)) # unknown meaning
                for i in data:
                    outf.write(i)
            elif fmt == 3:
                outf.write(struct.pack("<IIIIIIii",size,fmt,fw,fh,w,h,lm,tm))
                # store the offsets for all 32 pixel blocks
                acc = 0
                lineoffs = []
                for d in data:
                    for e in d:
                        offs = acc+(w/16)*h
                        if offs > ushrtmax:
                            print "exceeding max ushort value: %d"%offs
                            return False
                        lineoffs.append(offs)
                        acc += len(e)
                outf.write(struct.pack("<"+"H"*(w/32)*h, *lineoffs))
                for d in data: # line
                    for e in d: # 32 pixel block
                        outf.write(e)
    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "usage: %s infile.json outdir"%sys.argv[0]
        exit(1)
    ret = makedef(sys.argv[1], sys.argv[2])
    exit(0 if ret else 1)
