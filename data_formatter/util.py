import os
from pathlib import Path

#break the path into format and filename without format
def get_format(path):
    i = 1
    while i < len(path):
        if path[-i] == '.':
            return path[-i+1:], path[:-i]
        i += 1
    return None, path

# From the absolute path, get the folder name and the root
def break_path(path):
    i = len(path) - 1
    char = path[-i]
    while char != "\\" and i >= 0:
        i -= 1
        char = path[i]
    return path[i + 1:], path[:i]

    #check if a path is an existing folder. If not it creates it

def make_dir(path):
    if not os.path.isdir(path):
        make_dir(path.parent)
        os.mkdir(path)


def search_str(file_path: str, string: str) -> bool:
    """
    Check if string is in the file in file_path. Return True if string is in the file, otherwise return False
    """
    if not os.path.isfile(file_path):
        return False
    with open(file_path, 'r') as file:
        # read all content of a file
        content = file.read()
        # check if string present in a file
        if string in content:
            return True
        else:
            return False


def append_str(file_path: str, string: str) -> None:
    """
    Append string to the file in file_path.

    :param file_path:
    :param string:
    :return:
    """
    if not os.path.isfile(file_path):
        with open(file_path, 'w') as f:
            f.write(string)
            f.write('\n')
    else:
        with open(file_path, 'a') as f:
            f.write(string)
            f.write('\n')


def check_cache_file(file_path: str) -> bool:
    """
    Check if the file in file_path is a Thumbs.db file.
    Thumbs.db files are cache files automatically generated by Microsoft to load faster image previews.

    Return False if the file is not a .db file, otherwise return True.
    """
    filename, _ = break_path(file_path)
    if filename == 'Thumbs.db':
        return True
    return False


def make_file(file_path):
    _, dir_path = break_path(file_path)
    make_dir(Path(dir_path))
    with open(file_path, 'w') as f:
        f.write('')