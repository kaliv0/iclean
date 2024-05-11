import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass

__version__ = "0.0.1"

from pprint import pprint

# ### constants ###
LOG_FORMAT = "%(levelname)s: %(message)s"
IMPORT_PATTERN = " {imported}[.(]"
TEMP_TEMPLATE = "{file}.swap"

BAD_PRACTICE_ERROR = "Bad practice using import *"
CLEANUP_FAILED_ERROR = "Something went wrong while cleaning up unused imports:"
CLEANUP_SUCCESSFUL = "Cleaned up {file}"
NON_EXISTENT_PATH = "{path} doesn't exist"
SKIP_PATH = "{path} is in skip list"
NOT_PY_FILE = "{path} is not a python file"

IMPORT_KEYWORD_LEN = len("import") + 1
COMMENT = "#"
WILDCARD = "*"
ALIAS = "as"
IMPORT = "import"
NEW_LINE = "\n"
DELIMITER = ","
CWD = "."
PY_EXT = ".py"  # TODO:??


# ### helper classes ###
@dataclass
class ImportData:
    name: str
    count: int


@dataclass
class ImportLine:
    literal: str
    import_data: list[ImportData]
    is_multi_import_line: bool  # ??


class Cleaner:
    # ### settings ###
    def __init__(self):
        self.logger = self._get_logger()
        self.file = None
        self.temp_file = None
        self.lines = None
        self.line_num = None
        self.import_lines: list[ImportLine] = []

    @staticmethod
    def _get_logger():
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        return logger

    def set_up(self, file):
        self.file = file
        self.temp_file = TEMP_TEMPLATE.format(file=file)
        # load file in memory
        with open(file, "r") as f:
            self.lines = f.readlines()
        self.line_num = -1
        self.import_lines = []

    # ### main logic ###
    def process_paths(self, path_list, skip_list, dir_level):
        for path in path_list:
            if path != CWD:
                path = os.path.join(dir_level, path)

            if os.path.exists(path) is False:
                self.logger.info(NON_EXISTENT_PATH.format(path=path))
                continue
            if skip_list and path in skip_list:
                self.logger.info(SKIP_PATH.format(path=path))
                continue
            if os.path.isdir(path):
                nested_paths = os.listdir(path)
                self.process_paths(nested_paths, skip_list, dir_level=path)
                continue
            if path.endswith(PY_EXT) is False:
                self.logger.info(NOT_PY_FILE.format(path=path))
                continue

            self.set_up(path)
            self.clean_imports()

    def clean_imports(self):
        # try:
        self.read_imports()
        self.read_rest_of_file()
        pprint(self.import_lines)
        sys.exit()
        self.write_to_temp_file()
        # except (ValueError, Exception) as e:
        #     self.logger.error(CLEANUP_FAILED_ERROR)
        #     self.logger.error(e)
        #     if os.path.exists(self.temp_file):
        #         os.remove(self.temp_file)
        # else:
        #     os.replace(self.temp_file, self.file)
        #     self.logger.info(CLEANUP_SUCCESSFUL.format(file=self.file))

    # ### parse file ###
    def read_imports(self):
        for line_num, line in enumerate(self.lines):
            self.line_num += 1
            if line.startswith(NEW_LINE):
                continue
            # FIXME
            if line.startswith(COMMENT):
                self.import_lines.append(
                    ImportLine(literal=line, import_data=[], is_multi_import_line=False)
                )
            elif len(imported := line.split(ALIAS)) > 1:
                self._handle_aliases(line, imported[1])
            elif len(imported := line.split(IMPORT)) > 1:
                self._handle_imports(line, imported[1])
            else:
                break

    def _handle_aliases(self, line_literal, imported):
        # line_literal = imported[0].strip()  # FIXME
        import_name = imported.strip()
        import_data = ImportData(name=import_name, count=0)
        import_line = ImportLine(
            literal=line_literal, import_data=[import_data], is_multi_import_line=False
        )
        self.import_lines.append(import_line)

    def _handle_imports(self, line_literal, imported):
        # line_literal = imported[0].strip() + " import "  # FIXME
        import_name = imported.strip()

        if import_name.startswith(WILDCARD):
            raise ValueError(BAD_PRACTICE_ERROR)

        import_list = import_name.split(DELIMITER)
        is_multi_import_line = len(import_list) > 1
        import_line = ImportLine(
            literal=line_literal, import_data=[], is_multi_import_line=is_multi_import_line
        )

        for import_literal in import_list:
            import_data = ImportData(name=import_literal, count=0)
            import_line.import_data.append(import_data)

        self.import_lines.append(import_line)

    def read_rest_of_file(self):
        for line in self.lines[self.line_num :]:
            if line.strip().startswith(COMMENT):
                continue

            for imp_line in self.import_lines:
                for imported in imp_line.import_data:
                    if re.search(IMPORT_PATTERN.format(imported=imported.name), line):
                        # track import usage
                        # NB: since it uses pointers to objects in loop we increment count directly
                        imported.count += 1

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
            if ALIAS in line or COMMENT in line:
                file_writer.write(line)
            else:
                file_writer.write(self._prepare_import_line(import_list, line))

    @staticmethod
    def _should_write_import_line(line):
        is_commented_import = line.startswith(COMMENT)
        is_unused_multi_imports = DELIMITER in line
        is_blank = line == NEW_LINE
        return is_commented_import or not (is_unused_multi_imports or is_blank)

    @staticmethod
    def _prepare_import_line(import_list, line):
        return (
            line[: line.find(IMPORT) + IMPORT_KEYWORD_LEN]
            + f"{DELIMITER} ".join(import_list)
            + NEW_LINE
        )

    def write_rest_of_file(self, file_writer):
        for line in self.lines[self.line_num :]:
            file_writer.write(line)


def main():
    path_list, skip_list = read_input()
    Cleaner().process_paths(path_list, skip_list, dir_level=CWD)


def read_input():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="+")
    parser.add_argument("--skip", nargs="*")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()
    path_list = args.target
    skip_list = args.skip
    return path_list, skip_list


if __name__ == "__main__":
    main()
