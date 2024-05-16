import argparse
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TextIO

__version__ = "0.0.4"


# ### constants ###
@dataclass(frozen=True)
class Patterns:
    LOG_FORMAT = "%(levelname)s: %(message)s"
    TEMP = "{file}.swap"
    IMPORT = r"\b\@?{imported}[.(),\n]"
    DOT = r"^[.][\w-]+$"
    DUNDER = r"^__[\w-]+__$"


@dataclass(frozen=True)
class Messages:
    BAD_PRACTICE_ERROR = "Bad practice using import *"
    CLEANUP_FAILED_ERROR = "Something went wrong while cleaning up unused imports:"
    CLEANUP_SUCCESSFUL = "Cleaned up {file}"
    NON_EXISTENT_PATH = "{path} doesn't exist"
    SKIP_PATH = "Skipping {path}"
    NOT_PY_FILE = "{path} is not a python file"


@dataclass(frozen=True)
class Tokens:
    COMMENT = "#"
    WILDCARD = "*"
    ALIAS = " as "
    IMPORT = "import "
    NEW_LINE = "\n"
    LEFT_PAREN = "(\n"
    RIGHT_PAREN = ")\n"
    DELIMITER = ","
    CWD = "."
    PY_EXT = ".py"


IMPORT_LEN = len(Tokens.IMPORT)
ALIAS_LEN = len(Tokens.ALIAS)

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
    "share",
    "htmlcov",
    "cover",
    "instance",
    "docs",
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
    def __init__(self, skip_list: list[str]) -> None:
        self.logger = self._get_logger()
        self.file = None
        self.temp_file = None
        self.lines = None
        self.line_num = None
        self.import_lines: list[ImportLine] = []
        self.skip_list = DEFAULT_SKIP_LIST.union(skip_list)

    @staticmethod
    def _get_logger() -> logging.Logger:
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format=Patterns.LOG_FORMAT)
        return logger

    def set_up(self, file: str) -> None:
        self.file = file
        self.temp_file = Patterns.TEMP.format(file=file)
        # load file in memory
        with open(file, "r") as f:
            self.lines = f.readlines()
        self.line_num = -1
        self.import_lines = []

    # ### main logic ###
    def process_paths(
        self, path_list: list[str], dir_level: str, verbose: bool
    ) -> None:
        for path in path_list:
            if path != Tokens.CWD:
                path = os.path.join(dir_level, path)

            if os.path.exists(path) is False:
                self.logger.warning(Messages.NON_EXISTENT_PATH.format(path=path))
                continue
            if self._should_skip_path(os.path.basename(path)):
                if verbose:
                    self.logger.warning(Messages.SKIP_PATH.format(path=path))
                continue
            if os.path.isdir(path):
                nested_paths = os.listdir(path)
                self.process_paths(nested_paths, dir_level=path, verbose=verbose)
                continue
            if path.endswith(Tokens.PY_EXT) is False:
                self.logger.warning(Messages.NOT_PY_FILE.format(path=path))
                continue

            self.set_up(path)
            self.clean_imports()

    def _should_skip_path(self, path: str) -> re.Match[str] | bool:
        return (
            path in self.skip_list
            or re.search(Patterns.DOT, path)
            or re.search(Patterns.DUNDER, path)
            or path.endswith(".egg-info")
            or path.endswith(".bak")
        )

    def clean_imports(self) -> None:
        try:
            self.read_imports()
            self.read_rest_of_file()
            self.write_to_temp_file()
        except (ValueError, Exception) as e:
            self.logger.error(Messages.CLEANUP_FAILED_ERROR)
            self.logger.error(e)
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
        else:
            os.replace(self.temp_file, self.file)
            self.logger.info(Messages.CLEANUP_SUCCESSFUL.format(file=self.file))

    # ### parse file ###
    def read_imports(self) -> None:
        i = -1
        while i < len(self.lines):
            i += 1
            line = self.lines[i]
            if line.startswith(Tokens.NEW_LINE):
                self._handle_non_analysed_imports(line, ImportLineType.NEW_LINE)
            elif line.startswith(Tokens.COMMENT):
                self._handle_non_analysed_imports(line, ImportLineType.COMMENT)
            elif (idx := line.find(Tokens.ALIAS)) >= 0:
                import_boundary = idx + ALIAS_LEN
                imported = line[import_boundary:]
                self._handle_aliases(line, imported)
            elif (idx := line.find(Tokens.LEFT_PAREN)) >= 0:
                header = line[:idx]
                i, imported = self._get_multiline_imports(i)
                self._handle_import_line(header, imported)
            elif (idx := line.find(Tokens.IMPORT)) >= 0:
                import_boundary = idx + IMPORT_LEN
                header = line[:import_boundary]
                imported = line[import_boundary:]
                self._handle_regular_imports(header, imported)
            else:
                self.line_num = i
                break

    def _get_multiline_imports(self, i: int) -> tuple[int, list[str]]:
        imported = []
        i += 1
        while (line := self.lines[i]) != Tokens.RIGHT_PAREN:
            imported.append(line.strip().rstrip(","))
            i += 1
        return i, imported

    def _handle_non_analysed_imports(
        self, line_literal: str, line_type: ImportLineType
    ) -> None:
        self.import_lines.append(
            ImportLine(
                literal=line_literal,
                import_data=[],
                import_list=[],
                type=line_type,
            )
        )

    def _handle_aliases(self, line_literal: str, imported: str) -> None:
        import_name = imported.strip()
        import_data = ImportData(name=import_name, count=0)
        import_line = ImportLine(
            literal=line_literal,
            import_data=[import_data],
            import_list=[],
            type=ImportLineType.ALIAS,
        )
        self.import_lines.append(import_line)

    def _handle_regular_imports(self, line_literal: str, imported: str) -> None:
        import_names = imported.strip()
        if import_names.startswith(Tokens.WILDCARD):
            raise ValueError(Messages.BAD_PRACTICE_ERROR)

        import_list = import_names.split(Tokens.DELIMITER)
        self._handle_import_line(line_literal, import_list)

    def _handle_import_line(self, line_literal: str, import_list: list[str]) -> None:
        import_line = ImportLine(
            literal=line_literal,
            import_data=[],
            import_list=[],
            type=(
                ImportLineType.MULTI_IMPORT
                if len(import_list) > 1
                else ImportLineType.REGULAR
            ),
        )
        for import_literal in import_list:
            import_data = ImportData(name=import_literal.strip(), count=0)
            import_line.import_data.append(import_data)
        self.import_lines.append(import_line)

    def read_rest_of_file(self) -> None:
        for line in self.lines[self.line_num :]:
            if line.strip().startswith(Tokens.COMMENT):
                continue

            for imp_line in self.import_lines:
                for imported in imp_line.import_data:
                    if re.search(Patterns.IMPORT.format(imported=imported.name), line):
                        # track import usage
                        imported.count += 1

    # ### clean up file ###
    def write_to_temp_file(self) -> None:
        with open(self.temp_file, "w") as f:
            self.write_imports(f)
            self.write_rest_of_file(f)

    def write_imports(self, file_writer: TextIO) -> None:
        lines_count = 0
        for line in self.import_lines:
            should_process_line = self._build_multiple_import_list(line)
            if should_process_line:
                lines_count += self._write_import_line(file_writer, line)

        # write emtpy lines after import block if present
        if lines_count > 0:
            file_writer.write("\n\n")

    @staticmethod
    def _build_multiple_import_list(line: ImportLine) -> bool:
        should_process_line = True
        for data in line.import_data:
            if data.count == 0 and line.type != ImportLineType.MULTI_IMPORT:
                should_process_line = False
                break
            elif data.count > 0:
                line.import_list.append(data.name)
        return should_process_line

    def _write_import_line(self, file_writer: TextIO, line: ImportLine) -> int:
        if line.import_list or self._should_write_import_line(line):
            if line.type in (ImportLineType.ALIAS, ImportLineType.COMMENT):
                file_writer.write(line.literal)
            else:
                file_writer.write(
                    self._prepare_import_line(line.literal, line.import_list)
                )
            return 1  # returns number of written lines
        return 0

    @staticmethod
    def _should_write_import_line(line: ImportLine) -> bool:
        return line.type == ImportLineType.COMMENT or not (
            line.type == ImportLineType.MULTI_IMPORT
            or line.type == ImportLineType.NEW_LINE
        )

    @staticmethod
    def _prepare_import_line(line_literal: str, import_list: list[str]) -> str:
        return line_literal + f"{Tokens.DELIMITER} ".join(import_list) + Tokens.NEW_LINE

    def write_rest_of_file(self, file_writer: TextIO) -> None:
        for line in self.lines[self.line_num :]:
            file_writer.write(line)


def main() -> None:
    path_list, skip_list, verbose = read_input()
    Cleaner(skip_list).process_paths(path_list, dir_level=Tokens.CWD, verbose=verbose)


def read_input() -> tuple[list[str], list[str], bool]:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target", nargs="+", help="path or list of paths to file or directory to parse"
    )
    parser.add_argument(
        "--skip", nargs="*", default=(), help="target path or paths to skip"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="verbose output that includes skipping paths",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()
    path_list = args.target
    skip_list = args.skip
    verbose = args.verbose
    return path_list, skip_list, verbose


if __name__ == "__main__":
    main()
