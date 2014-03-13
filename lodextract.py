#!/usr/bin/env python

import zlib
import struct
import os
from PIL import Image, ImageDraw

from common import crc24_func, get_complement, font

def is_pcx(data):
    size,width,height = struct.unpack("<III",data[:12])
    return size == width*height or size == width*height*3

def read_pcx(data):
    size,width,height = struct.unpack("<III",data[:12])
    if size == width*height:
        im = Image.fromstring('P', (width,height),data[12:12+width*height])
        palette = []
        for i in range(256):
            offset=12+width*height+i*3
            r,g,b = struct.unpack("<BBB",data[offset:offset+3])
            palette.extend((r,g,b))
        im.putpalette(palette)
        return im
    elif size == width*height*3:
        return Image.fromstring('RGB', (width,height),data[12:])
    else:
        return None

def unpack_lod(infile,outdir,shred=True):
    f = open(infile)

    if f.read(4) != 'LOD\0':
        print "not LOD file"
        return False

    f.seek(8)
    total, = struct.unpack("<I", f.read(4))
    f.seek(92)

    files=[]
    for i in range(total):
        filename, = struct.unpack("16s", f.read(16))
        filename = filename[:filename.index('\0')]
        offset,size,_,csize = struct.unpack("<IIII", f.read(16))
        files.append((filename,offset,size,csize))

    for filename,offset,size,csize in files:
        filename=os.path.join(outdir,filename)
        print filename
        f.seek(offset)
        if csize != 0:
            data = zlib.decompress(f.read(csize))
        else:
            data = f.read(size)
        if is_pcx(data):
            im = read_pcx(data)
            if im:
                if shred:
                    crc = crc24_func(filename)
                    r = crc>>16
                    g = (crc&0xff00)>>8
                    b = crc&0xff
                    w,h = im.size
                    im = Image.new("RGB", (w*3,h*3), (r,g,b))
                    draw = ImageDraw.Draw(im)
                    draw.text((0,0),os.path.basename(filename),get_complement(r,g,b),font=font)
                    im = im.resize((w,h),Image.ANTIALIAS)
                im.save(filename, "PNG")
            else:
                return False
        else:
            o = open(filename,"w+")
            o.write(data)
            o.close()

    return True

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "usage: %s infile.lod ./outdir"%sys.argv[0]
        print ""
        print "usually after installing the normal way:"
        print "    %s .vcmi/Data/H3bitmap.lod .vcmi/Mods/vcmi/Data/"
        print "    rm .vcmi/Data/H3bitmap.lod"
        print "    %s .vcmi/Data/H3sprite.lod .vcmi/Mods/vcmi/Data/"
        print "    rm .vcmi/Data/H3sprite.lod"
    ret = unpack_lod(sys.argv[1], sys.argv[2])
    exit(0 if ret else 1)
