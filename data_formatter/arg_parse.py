import argparse


def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='test_data')
    parser.add_argument('--output', type=str, default='results')
    parser.add_argument('--time', type=str, default='creation', help='choose between creation time and modification time')
    parser.add_argument('--extract_csv', action='store_true')
    parser.add_argument('--print_folders', action='store_true')
    args = parser.parse_args()
    return args
