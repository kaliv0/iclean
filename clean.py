import argparse
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum, auto
from pprint import pprint


__version__ = "0.0.1"


# ### constants ###
LOG_FORMAT = "%(levelname)s: %(message)s"
IMPORT_PATTERN = r" {imported}[.(]"
TEMP_TEMPLATE = "{file}.swap"

BAD_PRACTICE_ERROR = "Bad practice using import *"
CLEANUP_FAILED_ERROR = "Something went wrong while cleaning up unused imports:"
CLEANUP_SUCCESSFUL = "Cleaned up {file}"
NON_EXISTENT_PATH = "{path} doesn't exist"
SKIP_PATH = "{path} is in skip list"
NOT_PY_FILE = "{path} is not a python file"

COMMENT = "#"
WILDCARD = "*"
ALIAS = " as "
IMPORT = "import "
IMPORT_LEN = len(IMPORT)
ALIAS_LEN = len(ALIAS)
NEW_LINE = "\n"
DELIMITER = ","
CWD = "."
PY_EXT = ".py"

# based on .gitignore
DEFAULT_SKIP_LIST = {
    "build",
    "develop-eggs",
    "dist",
    "downloads",
    "eggs",
    "lib",
    "lib64",
    "parts",
    "sdist",
    "var",
    "wheels",
    "share/python-wheels",
    "htmlcov",
    "cover",
    "instance",
    "docs/_build",
    "target",
    "profile_default",
    "site",
    "venv",
    "env",
    ".venv",
    ".env",
    "ENV",
}


# ### helper classes ###
@dataclass
class ImportData:
    name: str
    count: int


class ImportLineType(Enum):
    REGULAR = auto()
    ALIAS = auto()
    MULTI_IMPORT = auto()
    COMMENT = auto()
    NEW_LINE = auto()


@dataclass
class ImportLine:
    literal: str
    import_data: list[ImportData]
    import_list: list[str]
    type: ImportLineType


class Cleaner:
    # ### settings ###
    def __init__(self, skip_list):
        self.logger = self._get_logger()
        self.file = None
        self.temp_file = None
        self.lines = None
        self.line_num = None
        self.import_lines: list[ImportLine] = []
        self.skip_list = DEFAULT_SKIP_LIST.union(skip_list)

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
    def process_paths(self, path_list, dir_level):
        print(self.skip_list)
        for path in path_list:
            if path != CWD:
                path = os.path.join(dir_level, path)

            if os.path.exists(path) is False:
                self.logger.info(NON_EXISTENT_PATH.format(path=path))
                continue
            if self._should_skip_path(os.path.basename(path)):
                # TODO: log only in user-defined skip list or not at all??
                self.logger.info(SKIP_PATH.format(path=path))
                continue
            if os.path.isdir(path):
                print(path)
                nested_paths = os.listdir(path)
                self.process_paths(nested_paths, dir_level=path)
                continue
            if path.endswith(PY_EXT) is False:
                self.logger.info(NOT_PY_FILE.format(path=path))
                continue

            self.set_up(path)
            self.clean_imports()

    def _should_skip_path(self, path):
        # f_pattern = r"[\w-]+"
        return (
            path in self.skip_list
            or re.search(rf"^[.][\w-]+$", path)
            or re.search(rf"^__[\w-]+__$", path)
            or path.endswith(".egg-info")
            or path.endswith(".bak")
        )

    def clean_imports(self):
        # try:
        self.read_imports()
        self.read_rest_of_file()
        pprint(self.import_lines)
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
                self._handle_non_analysed_imports(line, ImportLineType.NEW_LINE)
            elif line.startswith(COMMENT):
                self._handle_non_analysed_imports(line, ImportLineType.COMMENT)
            elif (idx := line.find(ALIAS)) >= 0:
                import_boundary = idx + ALIAS_LEN
                imported = line[import_boundary:]
                print(f"{line=}, {imported=}")
                self._handle_aliases(line, imported)
            elif (idx := line.find(IMPORT)) >= 0:
                import_boundary = idx + IMPORT_LEN
                header = line[:import_boundary]
                imported = line[import_boundary:]
                print(f"{header=}, {imported=}")
                self._handle_regular_imports(header, imported)
            else:
                break

    def _handle_non_analysed_imports(self, line_literal, line_type):
        self.import_lines.append(
            ImportLine(literal=line_literal, import_data=[], import_list=[], type=line_type)
        )

    def _handle_aliases(self, line_literal, imported):
        import_name = imported.strip()
        import_data = ImportData(name=import_name, count=0)
        import_line = ImportLine(
            literal=line_literal,
            import_data=[import_data],
            import_list=[],
            type=ImportLineType.ALIAS,
        )
        self.import_lines.append(import_line)

    def _handle_regular_imports(self, line_literal, imported):
        import_names = imported.strip()
        if import_names.startswith(WILDCARD):
            raise ValueError(BAD_PRACTICE_ERROR)

        import_list = import_names.split(DELIMITER)
        import_line = ImportLine(
            literal=line_literal,
            import_data=[],
            import_list=[],
            type=ImportLineType.MULTI_IMPORT if len(import_list) > 1 else ImportLineType.REGULAR,
        )

        for import_literal in import_list:
            import_data = ImportData(name=import_literal.strip(), count=0)
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
                        imported.count += 1

    # ### clean up file ###
    def write_to_temp_file(self):
        with open(self.temp_file, "w") as f:
            self.write_imports(f)
            self.write_rest_of_file(f)

    def write_imports(self, file_writer):
        lines_count = 0
        for line in self.import_lines:
            should_write = self._build_multiple_import_list(line)
            if should_write:
                self._write_import_line(file_writer, line)
                lines_count += 1

        # write emtpy lines after import block if present
        if lines_count > 0:
            file_writer.write("\n\n")

    @staticmethod
    def _build_multiple_import_list(line):
        should_write = True
        for data in line.import_data:
            if data.count == 0 and line.type != ImportLineType.MULTI_IMPORT:
                should_write = False
                break
            elif data.count > 0:
                line.import_list.append(data.name)
        return should_write

    def _write_import_line(self, file_writer, line):
        if line.import_list or self._should_write_import_line(line):
            if line.type in (ImportLineType.ALIAS, ImportLineType.COMMENT):
                file_writer.write(line.literal)
            else:
                file_writer.write(self._prepare_import_line(line.literal, line.import_list))

    @staticmethod
    def _should_write_import_line(line):
        return line.type == ImportLineType.MULTI_IMPORT or line.type not in (
            ImportLineType.MULTI_IMPORT,
            ImportLineType.NEW_LINE,
        )

    @staticmethod
    def _prepare_import_line(line_literal, import_list):
        return line_literal + f"{DELIMITER} ".join(import_list) + NEW_LINE

    def write_rest_of_file(self, file_writer):
        for line in self.lines[self.line_num :]:
            file_writer.write(line)


def main():
    path_list, skip_list = read_input()
    Cleaner(skip_list).process_paths(path_list, dir_level=CWD)


def read_input():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="+")
    parser.add_argument("--skip", nargs="*", default=())
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()
    path_list = args.target
    skip_list = args.skip
    return path_list, skip_list


if __name__ == "__main__":
    main()
