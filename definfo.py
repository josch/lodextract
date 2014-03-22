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

import struct
from collections import defaultdict

def sanitize_filename(fname):
    # find the first character outside range [32-126]
    for i,c in enumerate(fname):
        if ord(c) < 32 or ord(c) > 126:
            break
    return fname[:i]

def main(infile):
    f = open(infile)
    t,_x,_y,blocks = struct.unpack("<IIII", f.read(16))
    print "%d %d %d %d"%(t,_x,_y,blocks)
    palette = []
    for i in range(256):
        r,g,b = struct.unpack("<BBB", f.read(3))
        palette.append((r,g,b))
    print "palette: %s"%(' '.join(["#%02x%02x%02x"%(r,g,b) for r,g,b in palette]))
    offsets = defaultdict(list)
    for i in range(blocks):
        bid,entries,x_,y_ = struct.unpack("<IIII", f.read(16))
        print bid,entries,x_,y_
        names=[]
        for j in range(entries):
            name, = struct.unpack("13s", f.read(13))
            name = sanitize_filename(name)
            print j, name
            names.append(name)
        for n in names:
            offs, = struct.unpack("<I", f.read(4))
            offsets[bid].append((n,offs))
    print "#\tnum\tsize\tformat\tfwidth\tfheight\twidth\theight\tlmargin\ttmargin"
    for bid,l in offsets.items():
        for j,(n,offs) in enumerate(l):
            f.seek(offs)
            s,fmt,fw,fh,w,h,lm,tm = struct.unpack("<IIIIIIii", f.read(32))
            print "frame:\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d"%(j,s,fmt,fw,fh,w,h,lm,tm)

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print "usage: %s input.def"%sys.argv[0]
        exit(1)
    main(sys.argv[1])
