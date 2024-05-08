import os


def clean_imports(file, temp_file):
    with open(file, "r") as f:
        lines = f.readlines()

    imp_map = {}
    line_num = -1
    for line in lines:
        line_num += 1
        if (idx := line.find("as")) >= 0:
            imp = line[idx + len("as") + 1 :].rstrip("\n")
            imp_map[imp] = [line_num, 0]
        elif (idx := line.find("import")) >= 0:
            imp = line[idx + len("import") + 1 :].rstrip("\n")
            imp_map[imp] = [line_num, 0]
        else:
            break

    for line in lines[line_num:]:
        for imp in imp_map:
            if imp in line:
                imp_map[imp][1] += 1

    with open(temp_file, "w") as f:
        for i, line in enumerate(lines[:line_num]):
            for ln, cnt in imp_map.values():
                if i == ln and cnt > 0:
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
        os.remove(temp_file)
    else:
        os.replace(temp_file, file)
