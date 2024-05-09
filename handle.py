import os
import re


def clean_imports(file, temp_file):
    # load file in memory
    with open(file, "r") as f:
        lines = f.readlines()

    # read imports
    imp_map = {}
    line_num = 0
    for line in lines:
        line_num += 1
        # skip commented out imports -> TODO: could be passed as flag by user
        if line.startswith("#"):
            continue
        # handle aliases
        if (idx := line.find("as")) >= 0:
            imp = line[idx + len("as") + 1 :].rstrip("\n")
            # TODO: turn to object -> line_number, usage_count, multiple_imports_line
            imp_map[imp] = [line_num, 0, 0]
        # handle standard imports (multiple, separated by comma on same line)
        elif (idx := line.find("import")) >= 0:
            if line[idx + len("import") + 1] == "*":
                raise ValueError("Bad practice using import *")
            imp_list = line[idx + len("import") + 1 :].rstrip("\n").split(",")
            for imp in imp_list:
                is_mult = 1 if len(imp_list) > 1 else 0
                imp_map[imp.strip()] = [line_num, 0, is_mult]
        elif not line.startswith(("\n", "#")):
            break

    print(imp_map)

    # read rest of file and track import usage
    for line in lines[line_num:]:
        if line.strip().startswith("#"):
            continue
        for imp in imp_map:
            pattern = f" {imp}[.(]"  # TODO: fix regex -> skips if similar substring is contained
            if re.search(pattern, line):
                imp_map[imp][1] += 1

    print(imp_map)

    # write content to temp_file skipping unused imports
    with open(temp_file, "w") as f:
        for i, line in enumerate(lines[:line_num], 1):
            skip = False
            for imp, val in list(imp_map.items()):
                ln = val[0]
                cnt = val[1]
                fl = val[2]  # flag if multiple imports on same line
                if not fl:
                    if ln == i and cnt == 0:
                        skip = True
                        break
                else:
                    if ln == i and cnt == 0:
                        line = line.replace(f"{imp}, ", "")
            if not skip:
                f.write(line)

        for line in lines[line_num:]:
            f.write(line)
    return temp_file


if __name__ == "__main__":
    file = "foo.py"
    temp_file = file + ".swap"
    try:
        temp_file = clean_imports(file, temp_file)
    except (RuntimeError, Exception) as e:
        print(e)
        if os.path.exists(temp_file):
            os.remove(temp_file)
    else:
        os.replace(temp_file, file)
