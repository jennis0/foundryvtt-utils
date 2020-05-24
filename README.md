# foundryvtt-utils
Collection of random scripts I use for FoundryVTT

## table_to_json.py
A python3 script to read tables copied from online sources into a FoundryVTT compatible JSON format. It has several particularly useful features:
- Auto subtable generation
- Auto generation of multiple tables from NxM arrays
- Dice roll formatting
- Output a single table as an importable RollTable json file
- Output many tables as a (nearly) nicely importable compendium format
- better-rolltables integration with:
  - Automatic table embedding
  - Smart handling of currency

The python script takes a file that can contain any number of tables as csv (or any other value separated format). I've typically just pasted an entire D&DBeyond page and deleted all the text between tables.

N.B. So far only tested on python3.8 on Ubuntu

Usage:
```
Create compendium:
python table_to_json.py treasure.csv --separator $'\t' --compendium treasure.json

Output Individual tables as json files in local directory
python table_to_json.py treasure.csv --separator $'\t' --dir .
```

The input csv files should contain tables with the format
```
[Title]
[range],[data]
[range],[data]
```
But in practice its quite flexible. The script also supports tables with multiple columns
```
Food Table
Roll,Poor,Rich
1-3,Bread,Steak
4-6,Soup,Truffles
```
will generate two tables, called Food Table - Poor and Food Table - Rich with each column's data

The opposite format is also supported
```
Drink Table
Roll,Poor,Rich
Water,1-5,1
Wine,6,2-6
```
Will also generate the two expected tables

Dice rolls and formula should be correctly wrapped in double square brackets

Subtables will be generated based on the format used on D&DBeyond
```
Item Table
1-3,Axe
3-6,Tool
 ,1 Rake
 ,2 Spade
 ,3 Trowel
```
This will generate two tables with the Tool entry in the Item Table correctly linked to its table

Additonal options
```
---better-spells : Rewrite spell scroll text to the "Spell Scroll X Level" format
---better-treasure: Use the better-rolltables syntax instead.
---combined: Merges all of the columns for each row with a "|" separator
---link: Proactively scan all tables and replaces text references to a table name with a better-rolltables link to that table
```
The better treasures mode will use the better-rolltables syntax instead of square brackets. This will also link tables when a description matches "Roll X times on table Y" (whether or not Y exists). Hoard tables, that have a "Coins" row are also handled
```
Example Hoard
Roll,CP,SP,EP,GP,PP
Coins,12, 2d6, 1d6+1,-,-
d2,Art,Magic Item
1,2d6 gems,Roll once on Magic Item Table A
2,3d6 gems,Spell scroll (2nd level)
```
Using the --better-treasures, --better-spells and --combined arguments will generate a loot table with the correct coin string and two entries
```
1, 2d6 gems | 1 [Magic Item Table A]
2, 3dg gems | Spell Scroll 2nd Level
```
Finally, if you pass the `--link` argument it will try to match table names to entry text and will replace matches with better-rolltables links. This ignores case but is otherwise exact. By default, it only nows about the tables it is processing from a single file but you can pass a json dictionary using `--link-map`. It will also look for any of the keys in that dictionary and replace those strings with the links to the table name stored as a value.

For clarity - I've mainly used this to fix the fact the gem tables in the DMGs aren't quite named the same as the references
```
{
    "10 gp gems":"10 gp Gemstones", #search key : table name
    "50 gp gems":"50 gp Gemstones",
    "100 gp gems":"100 gp Gemstones",
    "500 gp gems":"5000 gp Gemstones",
    "1,000 gp gems":"1,000 gp Gemstones",
    "5,000 gp gems":"5,000 gp Gemstones"
}
```

## upload_compendium.js
Currently I don't know of a good way to import compediums to your world. Copy the json file to somewhere under your world folder and run this script in your browser console, pointing it at a new or existing compedium (note - it will totally overwrite it!).
