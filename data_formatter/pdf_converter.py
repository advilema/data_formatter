import shutil
from data_formatter.util import get_format, get_root, get_directory_name, remove_data_format
from PIL import Image
import comtypes.client
from win32com import client
from fpdf import FPDF
import extract_msg
import os
from PyPDF2 import PdfMerger
from textwrap import TextWrapper
#XLSX vs XLS, DOC vs DOCX

def file_to_pdf(in_path, out_path, verbose=False):
    """
    Convert a file stored in in_path to PDF and store the new PDF file in out_path.
    The supported data formats are: docx, jpg, msg, pdf, png, pptx, txt, xlsx

    :param in_path: str. path to the file that you want to convert to PDF
    :param out_path: str. path where to store the new PDF file
    :param verbose: bool. If true print the error message
    :return: error_msg: str.
    """
    data_format = get_format(in_path)
    data_format = data_format.lower()  # This fix any upper/lower case problem (e.g. .JPG vs .jpg)
    if data_format == 'doc' or data_format == 'rtf':
        data_format = 'docx'
    elif data_format == 'xls':
        data_format = 'xlsx'
    elif data_format == 'jpeg':
        data_format = 'jpg'
    try:
        eval(data_format + '_to_pdf(in_path, out_path)')
        return None
    except NameError:
        error_msg = "Unrecognized data format: '.{}'. Was not possible to convert the file.".format(data_format)
        if verbose:
            print("\t" + error_msg)
        return error_msg
    except RuntimeError:
        error_msg = "The file conversion function timed out, so was not possible to convert the file."
        if verbose:
            print("\t" + error_msg)
    except Exception as e:
        #if data_format == 'msg':
        #    error_msg = "You don't have the permission to open the email."
        #else:
        error_msg = str(e)
        if verbose:
            print("\t" + error_msg)
        return error_msg


def docx_to_pdf(in_path, out_path):
    word = comtypes.client.CreateObject('Word.Application')
    word.Visible = 1
    doc = None
    try:
        doc = word.Documents.Open(in_path)
        doc.SaveAs(out_path, FileFormat=17)
    except Exception as error:
        raise error
    finally:
        if doc is not None:
            doc.Close()
        # word.Visible = False
        word.Quit()


def jpg_to_pdf(in_path, out_path):
    image = Image.open(in_path)
    
    x_len, y_len = image.size
    a4_x_len = 595
    new_x_len = min(x_len, a4_x_len)
    scale_factor = new_x_len/x_len
    new_y_len = int(scale_factor * y_len)
    image = image.resize((new_x_len,new_y_len), Image.ANTIALIAS)
    
    im = image.convert('RGB')
    im.save(out_path)
    image.close()


def msg_to_pdf(in_path, out_path):
    root_out_path = get_root(out_path)
    out_path_prov_dir = os.path.join(root_out_path, 'email')  # extract in this folder the email content

    msg = extract_msg.Message(in_path)  # This will create a local 'msg' object for each email in direcory
    
    # This will create a separate folder and save a text file with email body content, also it will download all
    # attachments inside this folder.
    msg.save(
        customPath=out_path_prov_dir, maxNameLength=150, customFilename='a')
    msg.close()

    # convert the email and the attachments to PDF
    for root, _, files in os.walk(out_path_prov_dir):
        for file in files:
            in_file_path = os.path.join(root, file)
            filename = get_directory_name(in_file_path)
            out_file_path = os.path.join(out_path_prov_dir, filename + '.pdf')
            idx = 0
            while os.path.isfile(out_file_path):
                out_file_path = os.path.join(out_path_prov_dir, filename + str(idx) + '.pdf')
                idx += 1
            err = file_to_pdf(in_file_path, out_file_path)
            os.remove(in_file_path)

    # merge the email and all the attachments
    paths = []
    for root, _, files in os.walk(out_path_prov_dir):
        # first put the text body of the email ...
        txt_files = []
        for file in files:
            if '.txt' in file:
                paths.append(os.path.join(root, file))
                txt_files.append(file)
        # ... and then all the other attachments
        for txt_file in txt_files:
            files.remove(txt_file)
        for file in files:
            file_path = os.path.join(root, file)
            paths.append(file_path)

    merger = PdfMerger()

    for pdf in paths:
        merger.append(pdf)

    merger.write(out_path)
    merger.close()

    # remove the folder with the email and the attachments and the copy of the email
    try:
        shutil.rmtree(out_path_prov_dir)
    except OSError:
        os.remove(out_path_prov_dir)


def pdf_to_pdf(in_path, out_path):
    shutil.copy(in_path, out_path)


def png_to_pdf(in_path, out_path):
    image = Image.open(in_path)
   
    x_len, y_len = image.size
    a4_x_len = 595
    new_x_len = min(x_len, a4_x_len)
    scale_factor = new_x_len/x_len
    new_y_len = int(scale_factor * y_len)
    image = image.resize((new_x_len,new_y_len), Image.ANTIALIAS)
    
    im = image.convert('RGB')
    im.save(out_path)
    image.close()


def pptx_to_pdf(in_path, out_path):
    powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
    powerpoint.Visible = 1
    deck = None
    try:
        deck = powerpoint.Presentations.Open(in_path)
        deck.SaveAs(out_path, 32)  # formatType = 32 for ppt to pdf
    except Exception as error:
        raise error
    finally:
        deck.Close()
        powerpoint.Quit()


def txt_to_pdf(in_path, out_path):
    pdf = FPDF()

    pdf.add_page()
    pdf.set_font("Arial", size=11)
    wrapper = TextWrapper(width=95, break_long_words=True)

    with open(in_path, "r", encoding='utf-8') as f:

        for line in f:
            line_no_special_chars = line.encode('latin-1', 'replace').decode('latin-1')
            short_lines = wrapper.wrap(text=line_no_special_chars)
            for short_line in short_lines:
                #print(line)
                pdf.cell(200, 10, txt=short_line, ln=1, align='L')
                
    pdf.output(out_path)


def xlsx_to_pdf(in_path, out_path):
    excel = client.Dispatch("Excel.Application")
    excel.Visible = True
    sheets = None
    try:
        sheets = excel.Workbooks.Open(in_path)
        work_sheets = sheets.Worksheets[0]
        work_sheets.ExportAsFixedFormat(0, out_path)
    except Exception as error:
        raise error
    finally:
        if sheets is not None:
            sheets.Close()
        excel.Visible = False
        excel.Quit()



