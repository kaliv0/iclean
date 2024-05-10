import argparse
import logging
import os
import re
from dataclasses import dataclass

__version__ = "0.0.1"

LOG_FORMAT = "%(levelname)s: %(message)s"
IMPORT_PATTERN = " {imported}[.(]"
IMPORT_KEYWORD_LEN = len("import") + 1
BAD_PRACTICE_ERROR = "Bad practice using import *"
CLEANUP_FAILED_ERROR = "Something went wrong while cleaning up unused imports:"
CLEANUP_SUCCESSFUL = "{file} cleaned up successfully"
TEMP_TEMPLATE = "{file}.swap"


@dataclass
class ImportData:
    line_num: int
    count: int
    is_multi_import_line: bool


class Cleaner:
    def __init__(self, file):
        self.file = file
        self.temp_file = TEMP_TEMPLATE.format(file=file)
        self.logger = self._setup_logger()
        # load file in memory
        with open(file, "r") as f:
            self.lines = f.readlines()
        self.import_data = {}
        self.line_num = -1

    @staticmethod
    def _setup_logger():
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        return logger

    # ### main logic ###
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

    # ### parse file ###
    def read_imports(self):
        for line in self.lines:
            self.line_num += 1
            # skip commented out imports
            if line.startswith(("#", "\n")):
                continue

            if len(imported := line.split("as")) > 1:
                self._handle_aliases(imported[1].strip())
            elif len(imported := line.split("import")) > 1:
                self._handle_imports(imported[1])
            else:
                break

    def _handle_aliases(self, imported):
        self.import_data[imported] = ImportData(self.line_num, 0, False)

    def _handle_imports(self, imported):
        if imported.strip().startswith("*"):
            raise ValueError(BAD_PRACTICE_ERROR)

        import_list = imported.split(",")
        for imported in import_list:
            is_multi_import_line = len(import_list) > 1
            self.import_data[imported.strip()] = ImportData(self.line_num, 0, is_multi_import_line)

    def read_rest_of_file(self):
        for line in self.lines[self.line_num:]:
            if line.strip().startswith("#"):
                continue
            for imported in self.import_data:
                if re.search(IMPORT_PATTERN.format(imported=imported), line):
                    # track import usage
                    self.import_data[imported].count += 1

    # ### clean up file ###
    def write_to_temp_file(self):
        with open(self.temp_file, "w") as f:
            self.write_imports(f)
            self.write_rest_of_file(f)

    def write_imports(self, file_writer):
        for line_num, line in enumerate(self.lines[: self.line_num], 0):
            should_write, import_list = self._build_multiple_import_list(line_num)
            if should_write:
                self._write_import_line(file_writer, import_list, line)
        # write emtpy lines after import block
        file_writer.write("\n\n")

    def _build_multiple_import_list(self, line_num):
        import_list = []
        should_write = True
        for imported, data in list(self.import_data.items()):
            if data.line_num == line_num:
                if data.count == 0 and data.is_multi_import_line is False:
                    should_write = False
                    break
                elif data.count > 0:
                    import_list.append(imported)
        return should_write, import_list

    def _write_import_line(self, file_writer, import_list, line):
        if import_list or self._should_write_import_line(line):
            if "as" in line or "#" in line:
                file_writer.write(line)
            else:
                file_writer.write(self._prepare_import_line(import_list, line))

    @staticmethod
    def _should_write_import_line(line):
        is_commented_import = line.startswith("#")
        is_unused_multi_imports = "," in line
        is_blank = line == "\n"
        return is_commented_import or not (is_unused_multi_imports or is_blank)

    @staticmethod
    def _prepare_import_line(import_list, line):
        return line[: line.find("import") + IMPORT_KEYWORD_LEN] + ", ".join(import_list) + "\n"

    def write_rest_of_file(self, file_writer):
        for line in self.lines[self.line_num:]:
            file_writer.write(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    Cleaner(args.path).clean_imports()


if __name__ == "__main__":
    main()
