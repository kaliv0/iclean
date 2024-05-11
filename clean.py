import argparse
import logging
import os
import re
from dataclasses import dataclass

__version__ = "0.0.1"

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
    line_num: int
    count: int
    is_multi_import_line: bool


class Cleaner:
    # ### settings ###
    def __init__(self):
        self.logger = self._get_logger()
        self.file = None
        self.temp_file = None
        self.lines = None
        self.import_data = None
        self.line_num = None

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
        self.import_data = {}
        self.line_num = -1

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
            if line.startswith((COMMENT, NEW_LINE)):
                continue

            if len(imported := line.split(ALIAS)) > 1:
                self._handle_aliases(imported[1].strip())
            elif len(imported := line.split(IMPORT)) > 1:
                self._handle_imports(imported[1])
            else:
                break

    def _handle_aliases(self, imported):
        self.import_data[imported] = ImportData(self.line_num, 0, False)

    def _handle_imports(self, imported):
        if imported.strip().startswith(WILDCARD):
            raise ValueError(BAD_PRACTICE_ERROR)

        import_list = imported.split(DELIMITER)
        for imported in import_list:
            is_multi_import_line = len(import_list) > 1
            self.import_data[imported.strip()] = ImportData(self.line_num, 0, is_multi_import_line)

    def read_rest_of_file(self):
        for line in self.lines[self.line_num :]:
            if line.strip().startswith(COMMENT):
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
