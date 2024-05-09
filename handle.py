import logging
import os
import re
from dataclasses import dataclass


@dataclass
class ImportData:
    line_num: int
    count: int
    is_multiple: bool


class Cleaner:
    def __init__(self, file, temp_file, skip_commented):
        # load file in memory
        with open(file, "r") as f:
            self.lines = f.readlines()
        self.temp_file = temp_file
        self.skip_commented = skip_commented
        self.imp_map = {}
        self.line_num = -1

    def read_imports(self):
        for line in self.lines:
            self.line_num += 1
            # skip commented out imports
            if line.startswith(("#", "\n")):
                continue
            # handle aliases
            if len(imp := line.split("as")) > 1:
                self.handle_aliases(imp[1].rstrip("\n"))
            # handle regular imports (multiple, separated by comma on same line)
            elif len(imp := line.split("import")) > 1:
                self.handle_imports(imp[1].rstrip("\n"))
            else:
                break

    def handle_aliases(self, imp):
        self.imp_map[imp.strip()] = ImportData(self.line_num, 0, False)

    def handle_imports(self, imp):
        if "*" in imp:
            raise ValueError("Bad practice using import *")
        imp_list = imp.split(",")
        for imp in imp_list:
            is_mult = len(imp_list) > 1
            self.imp_map[imp.strip()] = ImportData(self.line_num, 0, is_mult)

    def read_rest_of_file(self):
        for line in self.lines[self.line_num :]:
            if line.strip().startswith("#"):
                continue
            for imp in self.imp_map:
                # TODO: extract regex as const
                if re.search(f" {imp}[.(]", line):
                    # track import usage
                    self.imp_map[imp].count += 1
        print(self.imp_map)

    def write_imports(self, f):
        for i, line in enumerate(self.lines[: self.line_num], 0):
            skip, imp_list = self.build_multiple_import_list(i)
            if skip is False:
                self.write_import_line(f, imp_list, line)
        # write emtpy lines between import block and rest of code
        f.write("\n\n")

    def write_import_line(self, f, imp_list, line):
        if imp_list or self.should_write_import_line(line):
            if "as" not in line:
                line = self.prepare_import_line(imp_list, line)
            f.write(line)

    def prepare_import_line(self, imp_list, line):
        return line[: line.find("import") + len("import") + 1] + ", ".join(imp_list) + "\n"

    def should_write_import_line(self, line):
        # TODO: pass as flag by user
        skip_commented_imports = line.startswith("#") and self.skip_commented
        skip_unused_multi_imports = "," in line
        skip_blanks = line == "\n"
        return not (skip_commented_imports or skip_unused_multi_imports or skip_blanks)

    def build_multiple_import_list(self, i):
        imp_list = []
        for imp, val in list(self.imp_map.items()):
            # TODO: fix if statements
            if val.line_num == i:
                if val.count == 0 and val.is_multiple is False:
                    return True, imp_list
                elif val.count > 0:
                    imp_list.append(imp)
        return False, imp_list

    def write_rest_of_file(self, f):
        for line in self.lines[self.line_num :]:
            f.write(line)

    def write_to_temp_file(self):
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
    Cleaner(file, temp_file, True).clean_imports()
