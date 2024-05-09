import logging
import os
import pprint
import re


class Cleaner:
    def __init__(self, file, temp_file):
        # load file in memory
        with open(file, "r") as f:
            self.lines = f.readlines()
        self.temp_file = temp_file
        self.imp_map = {}
        self.line_num = 0

    def read_imports(self):
        for line in self.lines:
            self.line_num += 1
            # skip commented out imports -> TODO: pass as flag by user
            if line.startswith("#"):
                continue
            # handle aliases
            if (idx := line.find("as")) >= 0:
                self.handle_aliases(line, idx)
            # handle regular imports (multiple, separated by comma on same line)
            elif (idx := line.find("import")) >= 0:
                self.handle_imports(line, idx)
            elif line.startswith(("\n", "#")) is False:
                break

    def handle_aliases(self, line, idx):
        imp = line[idx + len("as") + 1 :].rstrip("\n")
        # TODO: turn to object -> line_number, usage_count, multiple_imports_line
        self.imp_map[imp] = [self.line_num, 0, 0]

    def handle_imports(self, line, idx):
        if line[idx + len("import") + 1] == "*":
            raise ValueError("Bad practice using import *")
        imp_list = line[idx + len("import") + 1 :].rstrip("\n").split(",")
        for imp in imp_list:
            is_mult = 1 if len(imp_list) > 1 else 0
            self.imp_map[imp.strip()] = [self.line_num, 0, is_mult]

    def read_rest_of_file(self):
        # read rest of file and track import usage
        for line in self.lines[self.line_num :]:
            if line.strip().startswith("#"):
                continue
            for imp in self.imp_map:
                # TODO: fix regex -> skips if similar substring is contained
                pattern = f" {imp}[.(]"
                if re.search(pattern, line):
                    self.imp_map[imp][1] += 1
        pprint.pprint(self.imp_map)

    def write_imports(self, f):
        # TODO: skip if initial lines are empty
        # write imports
        for i, line in enumerate(self.lines[: self.line_num], 1):
            skip = False
            for imp, val in list(self.imp_map.items()):
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
                        line = line.replace(f", {imp}", "")
                        line = line.replace(f"{imp}", "")
                        if line[line.find("import") + len("import") + 1] == "\n":
                            skip = True

            if not skip:
                f.write(line)

    def write_rest_of_file(self, f):
        # write rest of file
        for line in self.lines[self.line_num :]:
            f.write(line)

    def write_to_temp_file(self):
        # write content to temp_file skipping unused imports
        with open(self.temp_file, "w") as f:
            self.write_imports(f)
            self.write_rest_of_file(f)

    def clean_imports(self):
        try:
            self.read_imports()
            self.read_rest_of_file()
            self.write_to_temp_file()
        except (RuntimeError, Exception) as e:
            logging.error(e)
            if os.path.exists(temp_file):
                os.remove(temp_file)
        else:
            os.replace(temp_file, file)


if __name__ == "__main__":
    file = "foo.py"
    temp_file = file + ".swap"
    Cleaner(file, temp_file).clean_imports()
