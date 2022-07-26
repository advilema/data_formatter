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
from data_formatter.util import break_path, get_format, make_dir
from data_formatter.pdf_converter import file_to_pdf, jpg_to_pdf

invalid_folders = ['Arch', 'Stomadoku', 'Wunddoku']


class DataFormatter:
    def __init__(self, input_folder, output_folder, time_order='creation',  print_folders=False, log_path=None, err_path=None):
        self.input_folder = input_folder
        self.output_folder = output_folder
        cwd = os.getcwd()
        if not os.path.isabs(input_folder):
            self.abs_in_path = os.path.join(cwd, input_folder)
        else:
            self.abs_in_path = input_folder
        if not os.path.isabs(output_folder):
            self.abs_out_path = os.path.join(cwd, output_folder)
        else:
            self.abs_out_path = output_folder
        self.print_folders = print_folders
        self.time_order = time_order
        if log_path is None:
            self.log_path = os.path.join(self.abs_out_path, 'log.txt')
        else:
            if os.path.isabs(log_path):
                self.log_path = log_path
            else:
                self.log_path = os.path.join(cwd, log_path)
        if err_path is None:
            self.err_path = os.path.join(self.abs_out_path, 'err.txt')
        else:
            if os.path.isabs(err_path):
                self.err_path = err_path
            else:
                self.err_path = os.path.join(cwd, err_path)
        self.tot_files = self._count_files()

    def clean_folder(self):
        # create the folder where the log will be saved, then create a new blank log file
        _, log_dir = break_path(self.log_path)
        make_dir(Path(log_dir))
        with open(self.log_path, 'w') as f:
            f.write('')
        # same as the log but with the err file
        _, err_dir = break_path(self.err_path)
        make_dir(Path(err_dir))
        with open(self.err_path, 'w') as f:
            f.write('')

        patient_folder = None
        not_converted_files = []
        ignored_files = []
        n_files = 0
        txt_path = None
        txt_path_previous = None
        patient = ''

        if self.print_folders:
            print('A total of {} files will be processed.\n'.format(self.tot_files))

        if not self.print_folders:
            charge_bar = tqdm(total=self.tot_files)
        for root, subdirs, files in os.walk(self.abs_in_path):
            if files and self.print_folders:
                print('--\ncurrent folder: ' + root)
            patient_folder = self._get_patient_folder(root, patient_folder)

            if patient_folder is None:
                continue
            patient, _ = break_path(patient_folder)
            _, _, _, case_nr = self._extract_patient_data(patient)
            if case_nr is None:
                true_files = [file for file in files if not self._check_cache_file(file)]
                n_files += len(true_files)
                [ignored_files.append([os.path.join(root, filename), patient]) for filename in files]
                if not self.print_folders:
                    charge_bar.update(n=len(files))
                else:
                    print("The following {} files have been skipped since the patient doesn't have an ID number".format(len(files)))
                    [print("\t{}".format(file)) for file in true_files]
                continue

            for filename in files:
                if self._check_cache_file(filename):
                    continue
                n_files += 1
                if self.print_folders:
                    print('\t[{}/{} files processed ({:.1f}%)] - file {} '.format(n_files, self.tot_files, 100 * n_files / self.tot_files, filename))
                out_path_file, out_path_dir = self._make_output_path(patient_folder,
                                                               filename)
                in_path_file = os.path.join(root, filename)
                error_msg = file_to_pdf(in_path_file, out_path_file, verbose=self.print_folders)
                if error_msg is None:
                    #file_relative_path_from_patient_folder = in_path_file[len(patient_folder)+2:]
                    #self._add_header(out_path_file, file_relative_path_from_patient_folder)
                    txt_path = self._update_info_txt(in_path_file, out_path_file, out_path_dir)
                    if txt_path_previous is None:
                        txt_path_previous = txt_path
                else:
                    not_converted_files.append([in_path_file, error_msg])

                if not self.print_folders:
                    charge_bar.update(n=1)

            if txt_path_previous != txt_path:
                try:
                    self._merge_pdfs(txt_path_previous)
                except Exception as e:
                    with open(self.err_path, 'a') as f:
                        f.write(str(e))
                        f.write('\n\n\n')
                self._make_metadata(txt_path_previous)
                txt_path_previous = txt_path

        try:
            self._merge_pdfs(txt_path)
        except Exception as e:
            with open(self.err_path, 'a') as f:
                f.write(str(e))
                f.write('\n\n\n')
        self._make_metadata(txt_path)
        if not self.print_folders:
            charge_bar.close()

        self._save_log(not_converted_files, ignored_files)

    def extract_csv(self):
        csv_path = os.path.join(self.abs_out_path, 'csv_file.csv')
        header = ['Vorname', 'Nachname', 'Geburtstag', 'Fall-nr']
        patients_data = self._extract_patients_data()

        with open(csv_path, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for patient_data in patients_data:
                #if the case id is None we don't save the patient
                if patient_data[3] is None:
                    continue
                writer.writerow(patient_data)

    def extract_patient_folders(self):
        """
        Extract all the patient folders and save them in the log file
        """
        patient_folder = None
        previous_patient_folder = None

        _, log_dir = break_path(self.log_path)
        make_dir(Path(log_dir))
        # clear the log file if there exist already one
        with open(self.log_path, 'w') as f:
            f.write('')

        for root, subdirs, files in os.walk(self.abs_in_path):
            patient_folder = self._get_patient_folder(root, patient_folder)
            if patient_folder is not None and previous_patient_folder != patient_folder:
                patient, _ = break_path(patient_folder)
                with open(self.log_path, 'a') as f:
                    f.write(patient + '\n')
                previous_patient_folder = patient_folder

    def _count_files(self):
        count = 0
        for _, _, files in os.walk(self.abs_in_path):
            for file in files:
                if not self._check_cache_file(file):
                    count += 1
        return count

    @staticmethod
    def _add_header(pdf_path, header):
        MAX_DIM = 2000 #2000 pixels for the longest dimension of a PDF page when converted to JPG

        images = convert_from_path(pdf_path)
        _, path = get_format(pdf_path)
        path += '_dummy_img'
        img_pdf_paths = []
        for i in range(len(images)):
            # save pdfs pages as images
            img_path = path + str(i) + '.jpg'
            img_pdf_path = path + str(i) + '.pdf'
            # edit the image by adding the header
            images[i].save(img_path, 'JPEG')
            img = Image.open(img_path)
            height, width = img.size
            new_height = height
            new_width = width
            if height > width and height > MAX_DIM:
                new_height = MAX_DIM
                new_width = int((MAX_DIM/height)*width)
            if width > height and width > MAX_DIM:
                new_width = MAX_DIM
                new_height = int((MAX_DIM/width) * height)
            img = img.resize((new_height, new_width))
            title_font = ImageFont.truetype("arial.ttf", 30, encoding="unic")
            img_editable = ImageDraw.Draw(img)
            img_editable.text((10, 10), header, (256, 0, 0), font=title_font)
            #save the edited image
            img.save(img_path)
            #convert it to pdf
            jpg_to_pdf(img_path, img_pdf_path)
            os.remove(img_path)
            img_pdf_paths.append(img_pdf_path)

        merger = PdfMerger()
        for pdf in img_pdf_paths:
            merger.append(pdf)
        merger.write(pdf_path)
        merger.close()
        for pdf in img_pdf_paths:
            os.remove(pdf)

    #Thumbs.db files are cache files generated to load faster image previews
    @staticmethod
    def _check_cache_file(file_path):
        filename, _ = break_path(file_path)
        if filename == 'Thumbs.db':
            return True
        return False

    def _get_patient_folder(self, root, patient_folder):
        if patient_folder is not None and patient_folder in root:
            return patient_folder

        # if I didn't traverse one of the invalid folders yet, the current folder can't be a patient folder
        check_parent_folders = [folder in root for folder in invalid_folders]
        if not any(check_parent_folders):
            return None

        # if the current folder is an invalid folder, can't be a patient folder
        current_folder, _ = break_path(root)
        check_current_folder = [folder in current_folder for folder in invalid_folders]
        if any(check_current_folder):
            return None

        return root

    @staticmethod
    def _extract_patient_data(patient):
        first_name = None
        last_name = None
        birthday = None
        case_nr = None

        skip_words = ['', '-', 'geb', 'dr', 'fallnr', 'fall-nr', 'fr', 'frau', 'hr', 'herr', 'der', 'auf', 'zim']

        patient_data = patient.split(' ')
        # remove geb. in front of the date
        patient_data = [datum.replace('geb.', '') for datum in patient_data]

        # remove ',' and '-' from beginning and end of words
        patient_data = [datum.strip(' ,-') for datum in patient_data]

        # remove words in the skip_words list
        patient_data = [datum for datum in patient_data if not datum.lower() in skip_words]

        # first find the birthday, and remove it from the list patient_data
        prov_patient_data = []
        for datum in patient_data:
            try:
                if date_parse(datum):
                    birthday = datum
                    continue
            except:
                pass
            prov_patient_data.append(datum)
        patient_data = prov_patient_data

        # separate words if they are separated with a comma or a dot
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
                skip_doctor = False
                continue
            if datum.lower() == 'dr' or datum.lower() == 'prof':
                skip_doctor = True
                continue
            if datum.isnumeric() and len(datum) > 5:
                case_nr = datum
                continue
            prov_patient_data.append(datum)
        patient_data = prov_patient_data

        if patient_data:
            first_name = patient_data[0]
            if len(patient_data) > 1:
                last_name = patient_data[1]

        return [first_name, last_name, birthday, case_nr]

    def _extract_patients_data(self):
        patient_folder = None
        previous_patient_folder = None
        patients_data = []

        for root, subdirs, files in os.walk(self.abs_in_path):
            patient_folder = self._get_patient_folder(root, patient_folder)
            if patient_folder is not None and previous_patient_folder != patient_folder:
                patient, _ = break_path(patient_folder)
                patient_data = self._extract_patient_data(patient)
                patients_data.append(patient_data)
                previous_patient_folder = patient_folder

        return patients_data

    def _make_metadata(self, txt_path):
        _, txt_path_root = break_path(txt_path)
        patient, _ = break_path(txt_path_root)
        metadata_path = os.path.join(txt_path_root, patient + '.jpl')
        first_name, last_name, birthday, case_nr = self._extract_patient_data(patient)
        with open(metadata_path, 'w') as f:
            f.write('dokuart = "DMDOK"\n')
            f.write('logi_verzeichnis = "Freigabe"\n')
            documentation = 'Wunddokumentation' if 'Wunddoku' in txt_path_root else 'Stomadokumentation'
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
            today_str = today.strftime("%d.%m.%y")
            f.write('dok_dat_feld[50] = "' + today_str + '"\n')
            f.write('dok_dat_feld[52] = "' + today_str + '"\n')
            if birthday is not None:
                f.write('dok_dat_feld[53] = "' + birthday + '"\n')
            else:
                print('WARNING: was not possible to extract the birthday in patient: {}'.format(patient))

    # given the input_folder (e.g. 'test_data'), the output_folder (e.g. 'results'), the absolute path of the patient folder
    # and the filename, create the output_path_dir if it doesn't exis yet, and output the dir_path and file_path
    #TODO use abs_in_path instead of input_folder
    def _make_output_path(self, patient_folder, filename):
        #idx = patient_folder.find(input_folder)
        #output_path_dir = patient_folder[:idx] + output_folder + patient_folder[idx+len(input_folder):]
        output_path_dir = self.abs_out_path + patient_folder[len(self.abs_in_path):]
        make_dir(Path(output_path_dir))
        _, file = get_format(filename) #file is filename without '.format'

        #make sure that all the files have a distinct name
        idx = 0
        while True:
            out_filename = file + str(idx) + '.pdf'
            output_path_file = os.path.join(output_path_dir, out_filename)
            if Path(output_path_file).is_file():
                idx += 1
            else:
                break
        return output_path_file, output_path_dir

    @staticmethod
    def _merge_pdfs(txt_path):
        _, txt_path_root = break_path(txt_path)
        patient, _ = break_path(txt_path_root)
        with open(txt_path) as f:
            lines = f.readlines()
        files = []
        for i in range(len(lines) // 2):
            path = re.sub('\n', '', lines[2 * i])
            time = float(re.sub('\n', '', lines[2 * i + 1]))
            files.append([path, time])
        key = lambda x: x[1]
        files = sorted(files, key=lambda x: x[1])
        paths = [file[0] for file in files]

        merger = PdfMerger()

        for pdf in paths:
            merger.append(pdf)

        _, root = break_path(txt_path)
        filename = patient + '.pdf'
        merge_path = os.path.join(root, filename)
        merger.write(merge_path)
        merger.close()

        # remove pdfs and txt file
        os.remove(txt_path)
        for pdf in paths:
            os.remove(pdf)

    def _save_log(self, not_converted_files, ignored_files, verbose=True):

        #save in the log ignored and not converted files
        with open(self.log_path, 'a') as f:
            if ignored_files:
                f.write('The following {} files out of the total {} files have been ignored since the patient folder was missing '
                        'the id number:\n\n'.format(len(ignored_files), self.tot_files))
                for path, patient in ignored_files:
                    f.write('Patient: {}\nPath: {}\n\n'.format(patient, path))
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
                f.write('All the {} files have been successfully converted.'.format(tot_files))

        #print the log
        if verbose:
            with open(self.log_path, 'r') as f:
                lines = f.readlines()
                print('\n\n\n')
                for line in lines:
                    print(line, end='')

    # update (create if doesn't exist yet) the txt file with the time creation of the in_path_file
    def _update_info_txt(self, in_path_file, out_path_file, out_path_dir):
        txt_path = os.path.join(out_path_dir, 'info.txt')
        with open(txt_path, "a+") as file:
            if self.time_order == 'creation':
                path_time = str(os.path.getctime(in_path_file))
            else:
                path_time = str(os.path.getmtime(in_path_file))
            file.write(out_path_file + '\n' + path_time + '\n')
        return txt_path



