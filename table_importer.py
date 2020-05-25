import sys
import os
import argparse
import csv
import re
import json
import random
import string

#Counter for labelling unnamed tables
TABLE_COUNT=1    

#Pre-compile all our regexes
range_regex = re.compile(r"(\d{1,4})([\u2013\u2014-](\d{1,4}))?|([\u2013\u2014-])|(Coins)")
dice_regex = re.compile(r"(\d{1,4})d\d{1,4}")
roll_regex = re.compile(r"Roll (((\d{1,4}d\d{1,4}.*?) times)|(once)) on ([A-Za-z0-9 ]+?)( and (((\d{1,4}d\d{1,4}.*?) times)|(once)) on (.+?))?\.?$")
spell_regex = re.compile(r"[Ss]pell [Ss]croll \(?(((\d[a-z]{2}) [Ll]evel)|([Cc]antrip))\)?")
remove_average_regex = re.compile(r"(.*?) \([\d,]*\) ?(.*?)$")


#Format treasure titles to the format better-rolltables expects
# - Links to tables based on DMG's 'Roll X times on Table' format
# - Removes average rolls "1d6 (3)" -> "1d6"
def format_treasure(text):
    match = roll_regex.match(text)
    if match:
        groups = match.groups()
        roll_1 = "1" if groups[3] is not None else groups[2]
        text = "{} [{}]".format(roll_1, groups[4])

        if groups[5] is not None:
            roll_2 = "1" if groups[10] is not None else groups[8]
            text += " | {} [{}]".format(roll_2, groups[10])

    if dice_regex.search(text):
        while remove_average_regex.search(text):
            groups = remove_average_regex.search(text).groups()
            text = groups[0] + " "
            if groups[1]:
                text += " " + groups[1]
    
    text = text.replace(u"\u00d7", "*")
    return text

#Change spell scrolls to better-rolltables format
def format_spells(text):
    match = spell_regex.match(text)
    if match:
        groups = match.groups()
        if groups[2] is not None:
            return "Spell Scroll {} Level".format(groups[2])
        else:
            return "Spell Scoll Cantrip Level"
    else:
        return text

#Map coin tables (like those at the start of the DMG's treasure chapter) to better-rolltables format
def format_coins(headers, row):
    amounts = []
    for amount,coin in zip(row, headers):
        if amount and amount not in ["-", u"\u2013", u"\u2014"]:
            #Remove average amount from rolls (e.g. '1d6 (20)' )
            match = remove_average_regex.match(amount)
            if match:
                if len(match.group(2)) > 0:
                    amount = match.group(1) + " " + match.group(2)
                else:
                    amount = match.group(1)
            amount = amount.replace(u"\u00d7", "*")
            amounts.append(amount + "[{}]".format(coin.lower()))
    return "{{{}}}".format(",".join(amounts))

def merge_columns(headers, row, do_coin_syntax):
    #Basically check if this is a Treasure Hoard table
    if do_coin_syntax and "GP" in headers and len(headers) == 5:
        return format_coins(headers, row)         
        
    #Otherwise just join everything up
    row = [r for r in row if r is not None and r != "" and r not in ["-", u"\u2013", u"\u2014"]]
    return " | ".join(row)


# Wrap formulas in [[]] 
def wrap_rolls(text):
    tokens = text.split(" ")
    wrapped = wrap_inc_dice = in_curly_braces = False
    wrapped_text = []
    new_tokens = []

    for t in tokens:
        if t == "":
            continue 

        #Special case ignore for btr's coin syntax
        if t[0] == "{":
            in_curly_braces = True
        elif t[-1] == "}":
            in_curly_braces = False

        if not in_curly_braces and t.isnumeric() or t in ["+","-","*","/"]:
            wrapped = True
            wrapped_text.append(t)
            continue

        dr = dice_regex.match(t)
        if not in_curly_braces and dr is not None:
            wrapped = True
            wrapped_text.append(t)
            wrap_inc_dice = True
        else:
            wrapped = False
            if len(wrapped_text) > 0:
                if wrap_inc_dice:
                    new_tokens.append("[[{}]]".format(" ".join(wrapped_text)))
                    wrap_inc_dice = False
                else:
                    new_tokens.append(" ".join(wrapped_text))
                wrapped_text = []
            new_tokens.append(t)

    return " ".join(new_tokens)

#Build entry result
def make_entry(args, range_text, text, collection=None):
    range_re = range_regex.match(range_text)
    #Failed to parse
    if not range_re:
        print("ERROR: failed to parse range in row {}:{}".format(range_text,text))
        exit(1)

    groups = range_re.groups()
    #Empty range
    if groups[3] is not None:
        range_data = [1, 0]
        weight = 0

    elif groups[4]:
        return None #Should be handled as special case in the main table loop

    #Standard case
    else:
        low = int(groups[0], base=10)
        high = groups[2]
        if high:
            if high == "00":
                high = 100
            else:
                high = int(high, base=10)
            range_data = [low, high]
            weight = (high - low) + 1
        else:
            weight = 1
            range_data = [low, low]

    #Bring everything together into the json structure
    entry = {
        "flags":{},
        "type":0,
        "resultId": "",
        "text":text if args.better_treasure else wrap_rolls(text),
        "img":"icons/svg/d20-black.svg",
        "weight":weight,
        "range":range_data,
        "drawn":False
    }

    #Currently just used to link to subtables
    if collection:
        entry["collection"] = collection

    return entry

def make_table(title, headers, rows, args):
    out_dir = args.dir
    return_tables = []

    #Remove invisible whitespace from title
    title = title.replace(u"\ufeff", "")

    #Autogenerate table name if we don't have one
    global TABLE_COUNT
    print("Making table {}".format(title))
    if not title:
        title = "Table {}".format(TABLE_COUNT)
        TABLE_COUNT+=1

    ##Apply any string formatting strings
    if args.better_treasure or args.better_spells:
        for i, rs in enumerate(rows):
            if args.better_treasure:
                rows[i] = [format_treasure(r) for r in rows[i]]
            if args.better_spells:
                rows[i] = [format_spells(r) for r in rows[i]]
    
    #Merge columns into single table (includes generating BRT's coin syntax)
    coin_row = None
    if args.combined and len(rows[0]) > 2:
        for i, rs in enumerate(rows):
            if rows[i][0] == "Coins" and args.better_treasure:
                #This is rolled per-table rather than as an entry so we ignore it later
                coin_row = [rows[i][0], format_coins(["CP", "SP", "EP", "GP", "PP"], rows[i][1:])]
            else:
                rows[i] = [rows[i][0], merge_columns(headers, rows[i][1:], args.better_treasure)]
    
    #...or split columns into several tables
    elif len(rows[0]) > 2:
        row_sets = [[] for i in range(len(rows[0]) - 1)]

        #Two types of multi-col table [range, item1, item2, ...]
        if range_regex.match(rows[min(2, len(rows))][0]):
            for r in rows:
                for i in range(len(r) - 1):
                    row_sets[i].append((r[0], r[i + 1]))
        # Or [item, range1, range2, ...]
        else:
            for r in rows:
                for i in range(len(r) - 1):
                    row_sets[i].append((r[i + 1], r[0]))

        #Get title from headers if possible
        if len(headers) == len(row_sets):
            titles = ["{} - {}".format(title, h) for h in headers]
        else:
            titles = ["{} - {}".format(title, i) for i in range(len(row_sets))]

        #Create tables
        for t,h,rs in zip(titles, headers, row_sets):
            return_tables += make_table(t, [], rs, args)
        return return_tables

    ### Generate the table ###
    table = {
        "name":title,
        "description":"",
        "results":[],
        "displayRoll":True
    }

    #Add coin rolls if present
    if args.better_treasure and coin_row is not None:
        table["flags"] = {
            "better-rolltables": {
                "table-type":"loot",
                "table-currency-string":coin_row[1][1:-1], #strip {}
            }
        }

    #Tracking variables for any potential subtables
    in_subtable = False
    subtable_rows = []
    subtable_title = ""

    for i,r in enumerate(rows):
        if not in_subtable:
            print(rows[i])
            match = range_regex.match(r[0])
            if match is None or len(r) == 1:
                in_subtable = True #N.b. subtable 'parent' is the PREVIOUS item

                #Remove an annoying bit of the title and update previous item
                print(rows[i-1])
                roll_text_index = rows[i - 1][1].find("(roll")
                if roll_text_inde >= 0:
                    subtable_title = rows[i - 1][1][:roll_text_index].strip()
                else:
                    subtable_title = rows[i - 1][1]
                table["results"][i - 1] = make_entry(args, rows[i - 1][0], subtable_title, collection="RollTable")

                #Start building subtable data
                print("Found subtable:", subtable_title)
                
                #Get roll range from start of entry
                tokens = r[min(len(r) - 1, 1)].split(" ")
                subtable_rows = [((tokens[0], " ".join(tokens[1:])))]

            #Handle "Coins"
            elif match.groups()[4] is not None:
                continue

            else:
                table["results"].append(make_entry(args, *r))
        else:
            #Exit subtable if ended
            if len(r) > 1:
                table["results"].append(make_entry(args, *r))
                return_tables += make_table(subtable_title, [], subtable_rows, args)
                in_subtable = False
            else:
                tokens = r[0].split(" ")
                subtable_rows.append((tokens[0], " ".join(tokens[1:])))


    #Calculate and print die for table - useful for checking everything is included
    roll = sum(r["weight"] for r in table["results"])
    print("With {} entries".format(roll))
    table["formula"] = "1d{}".format(roll)
    #Write to disk if required
    print(out_dir, args.dir)
    if out_dir:
        #Sanitise filename
        filename = title.lower().replace(" ", "_").replace("/","_").replace(":","") + ".json"
        filename = filename.encode("utf-8").decode("ascii", "ignore")
        print(filename)
        with open(os.path.join(out_dir, filename), 'w') as out:
            json.dump(table, out)
    
    return_tables += [table]
    return return_tables


def try_link(args, tables):
    links = {}
    if args.link_map:
        if not os.path.exists(args.link_map):
            print("ERROR: Link map does not exist")
        with open(args.link_map, 'r') as f:
            links = json.load(f)
        print("Loaded links {}".format(links))

    table_names = []
    for t in tables:
        table_names.append(t["name"])
    
    for t in tables:
        for r in t["results"]:
            text = r["text"]
            for tn in table_names:
                ind = text.lower().find(tn.lower())
                if ind > 0:
                    if text[ind-1] == "[":
                        continue
                    stop = ind+len(tn)
                    r["text"] = text[:ind-1] + "[" + tn + "]" + text[stop:]
            for ln in links:
                ind = text.lower().find(ln.lower())
                if ind > 0:
                    if text[ind-1] == "[":
                        continue
                    stop = ind+len(ln)
                    r["text"] = text[:ind-1] + "[" + links[ln] + "]" + text[stop:]
    return tables

def to_compendium(args, tables):
    if not args.overwrite and os.path.exists(args.compendium):
        with open(args.compendium, 'r') as f:
            existing_tables = json.load(f)
    else:
        existing_tables = None

    all_tables = tables
    if existing_tables:
        for et in existing_tables:
            if not any(et["name"] == t["name"] for t in all_tables):
                all_tables.append(et)

    if args.link:
        all_tables = try_link(args, all_tables)
        
    with open(args.compendium, "w") as f:
        json.dump(all_tables, f)

def process_csv(args):
    filename = args.input
    separator = args.separator
    out_dir = args.dir

    tables = []

    print("Reading {}".format(filename))
    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter=separator)
        next_title = ""
        headers = []
        table_rows = []
        for row in reader:
           
            num_entries = sum(1 for r in row if r)
            #Blank row is a separator between tables
            if num_entries == 0:
                print("new")
                if len(table_rows) > 0:
                    tables += make_table(next_title, headers, table_rows, args)
                    table_rows = []
                    headers = []
                    next_title = ""
            
            #Treat single entry as a separator and title for next table
            if num_entries == 1 and row[0].strip() != "":
                print("separator")
                if len(table_rows) > 0:
                    tables += make_table(next_title, headers, table_rows, args)
                    table_rows = []
                    headers = []
                for r in row:
                    if r:
                        next_title = r.strip()
                        break
            #This has to allow 1 entry row to enable subtables
            elif num_entries >= 1:
                print(row)
                if not any(range_regex.match(r.strip()) for r in row):
                    headers = [r.strip() for r in row[1:] if r]
                else:
                    table_rows.append([r.strip() for r in row if r])
            else:
                print("Skipping row {}".format(row))

        if len(table_rows) > 0:
            tables += make_table(next_title, headers, table_rows, args)

        if args.compendium:
            to_compendium(args, tables)
                        

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Turn a csv into a FoundryVTT-compatible roll-table format")
    parser.add_argument("input", type=str, help="The input csv")
    parser.add_argument("--separator", type=str, help="The separator character", default=",")
    parser.add_argument("--dir", type=str, help="Output directory to store files")
    parser.add_argument("--compendium", type=str, help="Compendium to insert new tables")
    parser.add_argument("--overwrite", action="store_true", default=False, help="Overwrite compendium instead of inserting")

    parser.add_argument("--better-spells", action="store_true", default=False, help="Use better-rolltables Spell Scoll syntax")
    parser.add_argument("--combined", action="store_true", default=False, help="Make all tables generate a single combined table instead of 1 table per column")
    parser.add_argument("--better-treasure", action="store_true", default=False, help="Attempt to link treasure rolls to their correct table in the better-rolltables syntax")
    parser.add_argument("--link", action="store_true", default=False, help="Cross-link all entries in compendium after creation")
    parser.add_argument("--link-map", type=str, help="Path to JSON dictionary of mappings from target text to table names")

    args = parser.parse_args()

    if args.dir:
        if not os.path.exists(args.dir):
            os.makedirs(args.dir)
        elif not os.path.isdir(args.dir):
            print("ERROR: target directory is not a directory")
            exit(1)

    TABLE_COUNT=1

    if not os.path.exists(args.input):
        print("Failed to find file {}".format(args.input))
        exit(1)

    if not args.compendium and args.dir is None:
        print("ERROR: require either compedium or output location")
        exit(1)

    process_csv(args)