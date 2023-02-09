import os
from pathlib import Path
import re
import csv
from dateutil.parser import parse as date_parse
from datetime import date
from tqdm import tqdm
from pdf2image import convert_from_path
from PIL import Image, ImageFont, ImageDraw
from PyPDF2 import PdfMerger
from data_formatter.util import get_format, make_dir, search_str, append_str, check_cache_file, make_file, get_root, get_directory_name, remove_data_format
from data_formatter.pdf_converter import file_to_pdf, jpg_to_pdf

invalid_folders = ['Arch', 'Stoma', 'Wund', 'Patientenunterlagen']


def extract_patient_data(patient: str) -> list[str, str, str, str]:
    """
    Extract first_name, last_name, birthday, case_nr from the patient folder name.


    :param patient: patient folder name
    :return: first_name, last_name, birthday, case_nr
    """
    # TODO: Invertire first_name con last_name
    first_name = None
    last_name = None
    birthday = None
    case_nr = None

    skip_words = ['', '-', 'geb', 'fallnr', 'fall-nr', 'fr', 'frau', 'hr', 'herr', 'der', 'auf',
                  'zim', 'nf', 'unbekannt', 'tumorwunde', 'hausarzt']

    patient_data = patient.split(' ')
    # remove geb. in front of the date
    patient_data = [datum.replace('geb.', '') for datum in patient_data]

    # remove ',' and '-' from beginning and end of words
    patient_data = [datum.strip(' ,-.') for datum in patient_data]

    # remove words in the skip_words list
    patient_data = [datum for datum in patient_data if not datum.lower() in skip_words]

    # first find the birthday, and remove it from the list patient_data.
    prov_patient_data = []
    for datum in patient_data:
        try:
            if date_parse(datum):
                birthday = datum
                prov_patient_data.append('birthday')  # put a mark to remember the position where the birthday was
                continue
        except:
            pass
        prov_patient_data.append(datum)
    patient_data = prov_patient_data

    # split words if that are separated with a comma or a dot
    prov_patient_data = []
    for datum in patient_data:
        prov = []
        splitted = datum.split(',')
        for word in splitted:
            prov.extend(word.split('.'))
        for word in prov:
            if word != '':
                prov_patient_data.append(word)
    patient_data = prov_patient_data

    # here we remove the doctor name and we isolate the fall_nr
    skip_doctor = False
    prov_patient_data = []
    for datum in patient_data:
        if skip_doctor:
            if len(datum) > 1:
                skip_doctor = False
            continue
        if datum.lower() == 'dr' or datum.lower() == 'prof' or datum.lower() == 'd':
            skip_doctor = True
            continue
        # remove nf-zentrum, nf-arzt
        if 'nf-' in datum.lower():
            continue
        if datum.isnumeric() and len(datum) > 5:
            case_nr = datum
            continue
        prov_patient_data.append(datum)
    patient_data = prov_patient_data

    # delete all remaining numeric data
    prov_patient_data = []
    for datum in patient_data:
        if datum.isnumeric():
            continue
        prov_patient_data.append(datum)
    patient_data = prov_patient_data

    if patient_data:
        first_name = patient_data[0]
        if len(patient_data) > 1:
            if patient_data[1] != 'birthday':
                last_name = patient_data[1]
                if len(patient_data) > 2:
                    for i in range(2, len(patient_data)):
                        if patient_data[i] == 'birthday':
                            break
                        last_name += ' ' + patient_data[i]

    return [first_name, last_name, birthday, case_nr]


def get_patient_folder(root, patient_folder):
    """
    Given the root, and the previous patient_folder, return the new patient_folder
    """
    # in this case our current folder is inside the patient_folder, so we simply return the patient_folder
    if patient_folder is not None and patient_folder in root:
        return patient_folder

    current_folder = get_directory_name(root)
    [_, _, _, case_nr] = extract_patient_data(current_folder)

    # if the current_folder has a case_nr is a patient_folder. So return the path
    if case_nr is not None:
        return root

    # if the current folder does not have a case_nr, can't be a patient folder
    return None


def merge_pdfs(txt_path):
    """
    Given a txt file with a list of PDF files and their creation times, merge these files in a single PDF according to
    the files creation times
    """
    txt_path_root = get_root(txt_path)
    patient = get_directory_name(txt_path_root)
    with open(txt_path, encoding='utf-8') as f:
        lines = f.readlines()
    files = []
    for i in range(len(lines) // 2):
        path = re.sub('\n', '', lines[2 * i])
        time = float(re.sub('\n', '', lines[2 * i + 1]))
        files.append([path, time])
    files = sorted(files, key=lambda x: x[1])
    paths = [file[0] for file in files]

    merger = PdfMerger()

    for pdf in paths:
        merger.append(pdf)

    root = get_root(txt_path)
    [first_name, last_name, birthday, case_nr] = extract_patient_data(patient)
    filename = first_name + ', ' + last_name + ' Fall-Nr ' + case_nr + '.pdf'
    merge_path = os.path.join(root, filename)
    merger.write(merge_path)
    merger.close()

    # remove pdfs and txt file
    os.remove(txt_path)
    for pdf in paths:
        os.remove(pdf)


class DataFormatter:
    def __init__(self, input_folder, output_folder, time_order='creation', print_folders=False,
                 log_path=None, err_path=None, record_path=None):
        """

        :param input_folder: input folder, either as a relatve path or as an absolute path
        :param output_folder: output folder, either as a relatve path or as an absolute path
        :param time_order: either 'creation' or 'modification' time. the file ordering will be done according to this parameter
        :param verbose:
        :param log_path:
        :param err_path:
        :param record_path:
        """
        cwd = os.getcwd()

        # absolute path to input folder
        if not os.path.isabs(input_folder):
            self.abs_in_path = os.path.join(cwd, input_folder)
        else:
            self.abs_in_path = input_folder
        # absolute path to output folder
        if not os.path.isabs(output_folder):
            self.abs_out_path = os.path.join(cwd, output_folder)
        else:
            self.abs_out_path = output_folder

        self.print_folders = print_folders
        self.time_order = time_order

        if log_path is None:
            self.log_path = os.path.join(self.abs_out_path, 'log.txt')
        else:
            # make sure log_path is an absolute path
            if os.path.isabs(log_path):
                self.log_path = log_path
            else:
                self.log_path = os.path.join(cwd, log_path)

        if err_path is None:
            self.err_path = os.path.join(self.abs_out_path, 'err.txt')
        else:
            # make sure err_path is an absolute path
            if os.path.isabs(err_path):
                self.err_path = err_path
            else:
                self.err_path = os.path.join(cwd, err_path)

        if record_path is None:
            self.record_path = os.path.join(self.abs_out_path, 'files_record.txt')
        else:
            # make sure record_path is an absolute path
            if os.path.isabs(record_path):
                self.record_path = record_path
            else:
                self.record_path = os.path.join(cwd, record_path)

    def format(self):
        """
        Format the files into the patient folders in the self.abs_in_path folder, and save the formatted file in the
        abs_out_path folder
        """
        # count the files in the folders
        print('Counting the files in the folder ...')
        self.tot_files = self._count_files()
        
        # initialize the log file and the err file
        make_file(self.log_path)
        make_file(self.err_path)

        self.n_files = 0  # set the count of the files that have already been processed to 0
        not_converted_files = []  # these will be the files that was not possible to convert to PDF because of some error
        ignored_files = []  # These will be the files that have already been processed in a previous run of the algorithm, and therefore skipped this time
        patient_folder = None  # the current patient folder

        # txt_path is the path where to store the temporary txt file that keeps track of all the files converted to PDF
        # for a given patient. Once all the PDF files for a given patient have been merged, this temporary file is
        # deleted
        txt_path = None
        txt_path_previous = None  # txt_path of the previous round

        if self.print_folders:
            print('A total of {} files will be processed.\n'.format(self.tot_files))
        else:
            # initialize the charging bar if we are not going to print the folders
            self.charge_bar = tqdm(total=self.tot_files)

        for root, _, files in os.walk(self.abs_in_path):
            patient_folder = get_patient_folder(root, patient_folder)

            if patient_folder is None:
                # the current folder is not under a patient_folder, so we skip it
                continue

            if self.print_folders:
                print('--\ncurrent folder: ' + root)

            for file in files:
                # if the file it's a Thumbs.db cache file, skip it
                if check_cache_file(file):
                    continue

                # check if the file has already been processed in another run, if yes skip it
                if search_str(self.record_path, os.path.join(root, file)):
                    # add the file to the list of ignored files since we are not going to process it in this run
                    ignored_files.append(os.path.join(root, file))
                    # show info in the log
                    self._show_info(file, skipping=True)
                    continue

                # show info in the log
                self._show_info(file)

                # out_path_file is the path where we are going to convert our file to pdf, out_path_dir is the
                # new patient folder in the self.abs_out_path folder
                out_path_file, out_path_dir = self._make_output_path(patient_folder, file)
                in_path_file = os.path.join(root, file) # the path where the file is currently stored
                # convert the file to pdf and save the pdf in the out_path_file, generate an error message
                error_msg = file_to_pdf(in_path_file, out_path_file, verbose=self.print_folders)
                if error_msg is None:
                    # if error_msg is None means that the file has been converted to pdf successfully, therefore we add
                    # the file to a temporary txt_file that keep track of all the converted pdf files for a given patient
                    txt_path = self._update_info_txt(in_path_file, out_path_file, out_path_dir)
                    if txt_path_previous is None:
                        txt_path_previous = txt_path
                else:
                    # if there is an error message it means that the conversion of the file didn't happen. We save the
                    # error message in the err_path file, and we add the file to the list of the non_converted_files
                    append_str(self.err_path, error_msg)
                    not_converted_files.append([in_path_file, error_msg])

                # The file has been processed, so add it to the self.record_path file
                append_str(self.record_path, os.path.join(root, file))

            # merge all the PDF files of the previous patient (in fact, if txt_path_previous != txt_path it means that
            # the current patient is different from the previous one, which means that all the files of the previous
            # patient have been already processed, and the PDFs can be merged)
            if txt_path_previous != txt_path:
                try:
                    merge_pdfs(txt_path_previous)
                    self._make_metadata(txt_path_previous)
                except Exception as e:
                    # handle errors in the merging process
                    append_str(self.err_path, str(e))
                txt_path_previous = txt_path

        # remember to merge all the files of the last patient as well
        try:
            merge_pdfs(txt_path)
            self._make_metadata(txt_path)
        except Exception as e:
            # handle errors in the merging process
            append_str(self.err_path, str(e))

        if not self.print_folders:
            # terminate the charge_bar once the formatting is complete
            self.charge_bar.close()

        # save the not_converted_files and the ignored_files in the log
        self._save_log(not_converted_files, ignored_files)

    def extract_csv(self):
        """
        Create a CSV file with all the patients in the folder, where the columns are 'Vorname', 'Nachname',
        'Geburtstag', 'Fall-nr'
        """
        print('\nExtracting patients information from the folders ...')
        csv_path = os.path.join(self.abs_out_path, 'csv_file.csv')
        header = ['Vorname', 'Nachname', 'Geburtstag', 'Fall-nr']
        patients_data = self._extract_patients_data()

        print('Creating the csv file ...')
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for patient_data in patients_data:
                # if the case id is None we don't save the patient
                if patient_data[3] is None:
                    continue
                writer.writerow(patient_data)
        print('Done!')

    def extract_patient_folders(self):
        """
        Extract all the patient folders and save them in the log file
        """
        log_dir = get_root(self.log_path)
        make_dir(Path(log_dir))
        # clear the log file if there exist already one
        with open(self.log_path, 'w', encoding='utf-8') as f:
            f.write('')

        patient_folder = None
        previous_patient_folder = None

        for root, subdirs, files in os.walk(self.abs_in_path):
            patient_folder = get_patient_folder(root, patient_folder)
            if patient_folder is not None and previous_patient_folder != patient_folder:
                patient = get_directory_name(patient_folder)
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(patient + '\n')
                previous_patient_folder = patient_folder

    def _count_files(self):
        """
        Count all the files inside the self.abs_in_path that are inside a valid patient folder (with existing case_nr)
        and that are not cache files
        """
        count = 0
        patient_folder = None
        for root, _, files in os.walk(self.abs_in_path):
            patient_folder = get_patient_folder(root, patient_folder)
            # if the current root is not inside a patient_folder, continue
            if patient_folder is None:
                continue
            for file in files:
                # if it's a cache file skip it
                if check_cache_file(file):
                    continue
                count += 1
        return count

    def _extract_patients_data(self):
        """
        Exctract all the patients data from their patient folder name (first name, last name, birthday, case nr), and
        return them into a vector
        """
        patient_folder = None
        previous_patient_folder = None
        patients_data = []

        for root, subdirs, files in os.walk(self.abs_in_path):
            patient_folder = get_patient_folder(root, patient_folder)
            if patient_folder is not None and previous_patient_folder != patient_folder:
                patient = get_directory_name(patient_folder)
                patient_data = extract_patient_data(patient)
                patients_data.append(patient_data)
                previous_patient_folder = patient_folder

        return patients_data

    def _make_metadata(self, txt_path):
        """
        Create the metadata .jpl file
        """
        txt_path_root = get_root(txt_path)
        patient = get_directory_name(txt_path_root)
        [first_name, last_name, birthday, case_nr] = extract_patient_data(patient)
        filename = first_name + ', ' + last_name + ' Fall-Nr ' + case_nr + '.jpl'
        metadata_path = os.path.join(txt_path_root, filename)
        metadata_dir = get_root(metadata_path)
        make_dir(Path(metadata_dir))  # create the metadata dir if it has not been created yet

        first_name, last_name, birthday, case_nr = extract_patient_data(patient)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write('dokuart = "DMDOK"\n')
            f.write('logi_verzeichnis = "Freigabe"\n')
            print('***********herererere******************')
            print(self.abs_in_path.lower())
            documentation = 'Wunddokumentation' if 'wunddoku' in self.abs_in_path.lower() else 'Stomadokumentation'
            print(documentation)
            f.write('dok_dat_feld[3] = "MCC AA ' + documentation + ' Migration"\n')
            f.write('dok_dat_feld[5] = "' + documentation + '"\n')
            f.write('dok_dat_feld[7] = "' + case_nr + '"\n')
            if first_name is not None:
                f.write('dok_dat_feld[11] = "' + first_name + '"\n')
            else:
                print('WARNING: was not possible to extract the first name in patient: {}'.format(patient))
            if last_name is not None:
                f.write('dok_dat_feld[12] = "' + last_name + '"\n')
            else:
                print('WARNING: was not possible to extract the last name in patient: {}'.format(patient))
            f.write('dok_dat_feld[14] = "Migrationsdokument"\n')
            f.write('dok_dat_feld[15] = "2080"\n')
            f.write('dok_dat_feld[16] = "MCC HLT"\n')
            today = date.today()
            today_str = today.strftime("%d.%m.%Y")
            f.write('dok_dat_feld[50] = "' + today_str + '"\n')
            f.write('dok_dat_feld[52] = "' + today_str + '"\n')
            if birthday is not None:
                f.write('dok_dat_feld[53] = "' + birthday + '"\n')
            else:
                print('WARNING: was not possible to extract the birthday in patient: {}'.format(patient))

    # given the input_folder (e.g. 'test_data'), the output_folder (e.g. 'results'), the absolute path of the patient folder
    # and the filename, create the output_path_dir if it doesn't exis yet, and output the dir_path and file_path
    def _make_output_path(self, patient_folder, filename):
        """
        given the input_folder (e.g. 'test_data'), the output_folder (e.g. 'results'), the absolute path of the patient folder
        and the filename, create the output_path_dir if it doesn't exist yet, and return the dir_path and file_path
        """
        output_path_dir = self.abs_out_path + patient_folder[len(self.abs_in_path):]
        make_dir(Path(output_path_dir))
        file = remove_data_format(filename)  # file is filename without '.format'

        # make sure that all the files have a distinct name
        idx = 0
        while True:
            out_filename = file + str(idx) + '.pdf'
            output_path_file = os.path.join(output_path_dir, out_filename)
            if Path(output_path_file).is_file():
                idx += 1
            else:
                break
        return output_path_file, output_path_dir

    def _save_log(self, not_converted_files, ignored_files, verbose=True):

        # save in the log ignored and not converted files
        with open(self.log_path, 'a', encoding='utf-8') as f:
            tot_files = self.tot_files
            if ignored_files:
                f.write(
                    'The following {} files out of the total {} files have been ignored since they have been already '
                    'processed in a previous run:\n\n'.format(len(ignored_files), self.tot_files))
                for path in ignored_files:
                    f.write('Path: {}\n\n'.format(path))
                f.write('\n')
                tot_files = self.tot_files - len(ignored_files)
            if not_converted_files:
                if ignored_files:
                    f.write('Out of the remaining {} files, was not possible to convert the following {} files\n\n'
                            .format(tot_files - len(ignored_files), len(not_converted_files)))
                else:
                    f.write('It was not possible to convert the following {} files out of the total {} files:\n\n'
                            .format(len(not_converted_files), tot_files))
                for path, err in not_converted_files:
                    f.write('Error: {}\nPath: {}\n\n'.format(err, path))

            if not ignored_files and not_converted_files:
                f.write('All the {} files have been successfully converted.'.format(self.tot_files))

        # print the log
        if verbose:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print('\n\n\n')
                for line in lines:
                    print(line, end='')

    def _update_info_txt(self, in_path_file, out_path_file, out_path_dir):
        """
        update (create, if doesn't exist yet) the txt file with the time creation of the in_path_file
        """
        txt_path = os.path.join(out_path_dir, 'info.txt')
        with open(txt_path, "a+", encoding='utf-8') as file:
            if self.time_order == 'creation':
                path_time = str(os.path.getctime(in_path_file))
            else:
                path_time = str(os.path.getmtime(in_path_file))
            file_info = out_path_file + '\n' + path_time + '\n'
            file_info = file_info.encode('utf-8', 'replace').decode('utf-8')
            file.write(out_path_file + '\n' + path_time + '\n', )
        return txt_path

    def _show_info(self, file, skipping=False):
        skipping_text = ''
        if skipping:
            skipping_text = 'skipped because already processed in a previous run '
        if self.print_folders:
            # update the file counter
            self.n_files += 1
            # print infos about the file
            print('\t[{}/{} files processed ({:.1f}%)] - file {}{} '
                  .format(self.n_files, self.tot_files, 100 * self.n_files / self.tot_files, skipping_text, file))
        else:
            # update the charging bar
            self.charge_bar.update(n=1)
