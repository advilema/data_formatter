import os

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
