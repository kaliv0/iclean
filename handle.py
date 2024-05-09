import argparse
import logging
import os
import re
from dataclasses import dataclass


LOG_FORMAT = "%(levelname)s: %(message)s"
IMPORT_PATTERN = " {imp}[.(]"
IMPORT_KEYWORD_LEN = len("import") + 1
BAD_PRACTICE_ERROR = "Bad practice using import *"
CLEANUP_FAILED_ERROR = "Something went wrong while cleaning up unused imports:"
CLEANUP_SUCCESSFUL = "{file} cleaned up successfully"
TEMP_TEMPLATE = "{file}.swap"


@dataclass
class ImportData:
    line_num: int
    count: int
    is_multiple: bool


class Cleaner:
    def __init__(self, file, skip_commented):
        self.file = file
        self.temp_file = TEMP_TEMPLATE.format(file=file)
        self.logger = self.setup_logger()
        # load file in memory
        with open(file, "r") as f:
            self.lines = f.readlines()
        self.skip_commented = skip_commented
        self.imp_map = {}
        self.line_num = -1

    @staticmethod
    def setup_logger():
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        return logger

    def read_imports(self):
        for line in self.lines:
            self.line_num += 1
            # skip commented out imports
            if line.startswith(("#", "\n")):
                continue

            if len(imp := line.split("as")) > 1:
                self.handle_aliases(imp[1].strip())
            elif len(imp := line.split("import")) > 1:
                self.handle_imports(imp[1])
            else:
                break

    def handle_aliases(self, imp):
        self.imp_map[imp] = ImportData(self.line_num, 0, False)

    def handle_imports(self, imp):
        imp_ = imp.strip()
        if imp_.startswith("*"):
            raise ValueError(BAD_PRACTICE_ERROR)

        imp_list = imp.split(",")
        for imp in imp_list:
            is_mult = len(imp_list) > 1
            self.imp_map[imp.strip()] = ImportData(self.line_num, 0, is_mult)

    def read_rest_of_file(self):
        for line in self.lines[self.line_num :]:
            if line.strip().startswith("#"):
                continue
            for imp in self.imp_map:
                if re.search(IMPORT_PATTERN.format(imp=imp), line):
                    # track import usage
                    self.imp_map[imp].count += 1

    def write_imports(self, f):
        for i, line in enumerate(self.lines[: self.line_num], 0):
            skip, imp_list = self.build_multiple_import_list(i)
            if skip is False:
                self.write_import_line(f, imp_list, line)
        # write emtpy lines after import block
        f.write("\n\n")

    def write_import_line(self, f, imp_list, line):
        if imp_list or self.should_write_import_line(line):
            if "as" not in line:
                line = self.prepare_import_line(imp_list, line)
            f.write(line)

    @staticmethod
    def prepare_import_line(imp_list, line):
        return line[: line.find("import") + IMPORT_KEYWORD_LEN] + ", ".join(imp_list) + "\n"

    def should_write_import_line(self, line):
        # TODO: pass as flag by user
        skip_commented_imports = line.startswith("#") and self.skip_commented
        skip_unused_multi_imports = "," in line
        skip_blanks = line == "\n"
        return not (skip_commented_imports or skip_unused_multi_imports or skip_blanks)

    def build_multiple_import_list(self, i):
        imp_list = []
        for imp, val in list(self.imp_map.items()):
            if val.line_num == i:
                if val.count == 0 and val.is_multiple is False:
                    return True, imp_list
                if val.count > 0:
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
        except (ValueError, Exception) as e:
            self.logger.error(CLEANUP_FAILED_ERROR)
            self.logger.error(e)
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
        else:
            os.replace(self.temp_file, self.file)
            self.logger.info(CLEANUP_SUCCESSFUL.format(file=self.file))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path")
    args = parser.parse_args()
    Cleaner(args.file_path, True).clean_imports()

    # Cleaner("foo.py", True).clean_imports()
