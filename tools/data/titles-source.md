# Where the game title database comes from

`titles.json` maps PlayStation 1 serial numbers to game titles — 10,937
entries. It is a table of facts about commercial releases: a disc serial
and the name printed on the box.

The data originates from **[redump.org](http://redump.org/)**, the disc
preservation project, and was collected from there by
[GDX-X/Title-Database-Scrapper](https://github.com/GDX-X/Title-Database-Scrapper).
It reached this project through
[Kyuu-Ji/sd2psx-save-converter](https://github.com/Kyuu-Ji/sd2psx-save-converter),
which ships it as `TitlesDB_PS1_English.txt`.

Neither of those repositories states a licence. The file here is a
transformed copy — the plain-text list turned into JSON by
`tools/psxexport.py`, with disc-number suffixes stripped, since a
multi-disc game writes its save under the serial of the first disc.

If you maintain any of these sources and would rather this copy were not
distributed, write to dktgsitu@gmail.com and it will be removed. Nothing
here depends on it: without the file the app simply shows "Unknown game".
