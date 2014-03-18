This is a set of scripts which shows how to unpack all bitmaps and animations
of Heroes of Might and Magic 3 into PNG images and then back into the formats
understood by VCMI.

These scripts are probably the first open source implementation of a writer for
the Heroes of Might and Magic 3 animation format called DEF. They are meant to
make it possible for artists to create a free replacement for the proprietary
assets VCMI currently needs.

Install VCMI and then install original game files via any of the following methods:

	vcmibuilder --cd1 /path/to/iso/or/cd --cd2 /path/to/second/cd --download
	vcmibuilder --gog /path/to/gog.com/installer --download
	vcmibuilder --data /path/to/h3/data --download

Symlink sprites to Data directory

	ln -s Data ~/.vcmi/Sprites

Backup original archives:

	mkdir ~/lods
	for f in H3ab_bmp.lod H3ab_spr.lod H3bitmap.lod H3sprite.lod; do mv ~/.vcmi/Data/$f ~/lods; done
	for f in hmm35wog.pac "wog - animated objects.pac" "wog - animated trees.pac" "wog - battle decorations.pac"; do mv ~/.vcmi/Mods/WoG/Data/"$f" ~/lods; done

Extract archives:

	for f in H3bitmap.lod H3sprite.lod H3ab_bmp.lod H3ab_spr.lod hmm35wog.pac "wog - animated objects.pac" "wog - animated trees.pac" "wog - battle decorations.pac"; do python lodextract.py ~/lods/"$f" ~/.vcmi/Data/; done

Backup original DEFs:

	mkdir ~/defs
	mv ~/.vcmi/Data/*.def ~/defs
	rm ~/defs/sgtwmta.def ~/defs/sgtwmtb.def # these are having higher offsets than size

Extract all DEFs into JSON files and directories with PNG images:

	for f in ~/defs/*; do python defextract.py $f ~/.vcmi/Data || break; done

(optional) modify all frames:

	for d in ~/.vcmi/Data/*.dir; do python shred.py $d || break; done

(optional) modify all bitmaps:
	for f in ~/.vcmi/Data/*.png; do python shred.py $f || break; done

Repack all JSON:

	for f in ~/.vcmi/Data/*.json; do python makedef.py $f ~/.vcmi/Data || break; done

In case you followed the optional steps, enjoy your LSD infused game now :)

After above steps you will have a mixture of DEF files as well as JSON
files and their *.dir data directories. All parts of vcmi that support it will
read the animations from the JSON files now. All others will fall back to
reading the DEF files.

You can now make changes to either the PNG images in the Data directory or in
the *.dir subdirectories. If you make changes to PNG images in *.dir
subdirectories you might have to repack them into DEF files for all animations
which do not support JSON animations yet.

I only tested these scripts on Linux because I do not own a license for Windows
or MacOS. Patches welcome.
