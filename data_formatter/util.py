import os
from pathlib import Path



def make_dir(path):
    """
    check if a path is an existing folder. If not it creates it
    """
    if not os.path.isdir(path):
        make_dir(path.parent)
        os.mkdir(path)


def search_str(file_path: str, string: str) -> bool:
    """
    Check if string is in the file in file_path. Return True if string is in the file, otherwise return False
    """
    if not os.path.isfile(file_path):
        return False
    with open(file_path, 'r', encoding='utf-8') as file:
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
    string = string.encode('utf-8', 'replace').decode('utf-8')
    if not os.path.isfile(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(string)
            f.write('\n')
    else:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(string)
            f.write('\n')


def check_cache_file(file_path: str) -> bool:
    """
    Check if the file in file_path is a Thumbs.db file.
    Thumbs.db files are cache files automatically generated by Microsoft to load faster image previews.

    Return False if the file is not a .db file, otherwise return True.
    """
    filename = get_directory_name(file_path)
    if filename == 'Thumbs.db':
        return True
    return False


def make_file(file_path):
    dir_path = get_root(file_path)
    make_dir(Path(dir_path))
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('')


def get_root(path):
    """
    Return the root of the path, which is considered as the path minus the directory name
    """
    i = len(path) - 1
    char = path[-i]
    while char != "\\" and i >= 0:
        i -= 1
        char = path[i]
    return path[:i]


def get_directory_name(path):
    """
    Return the directory name of the path, which is considered as the path minus the root
    """
    i = len(path) - 1
    char = path[-i]
    while char != "\\" and i >= 0:
        i -= 1
        char = path[i]
    return path[i + 1:]


def get_format(file_pat):
    """
    Return the data format of the file. Will be considered as data format the substring after the rightmost dot in
    the file_path
    """
    i = 1
    while i < len(file_pat):
        if file_pat[-i] == '.':
            return file_pat[-i + 1:]
        i += 1
    return None, file_pat


def remove_data_format(file_pat):
    """
    Return the substring on the left of the rightmost dot in the file_path
    """
    i = 1
    while i < len(file_pat):
        if file_pat[-i] == '.':
            return file_pat[:-i]
        i += 1
    return file_pat
