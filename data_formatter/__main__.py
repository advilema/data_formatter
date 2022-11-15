from data_formatter.arg_parse import parse
import warnings
from data_formatter.data_formatter import DataFormatter


def main() -> None:
    warnings.filterwarnings("ignore")
    args = parse()
    input_folder = args.input
    output_folder = args.output
    formatter = DataFormatter(input_folder, output_folder, print_folders=args.print_folders,log_path=args.log)

    if args.extract_csv:
        formatter.extract_csv()
        if args.extract_patients:
            formatter.extract_patient_folders()
    elif args.extract_patients:
        formatter.extract_patient_folders()
    else:
        formatter.format()
        formatter.extract_csv()


if __name__ == '__main__':
    main()
