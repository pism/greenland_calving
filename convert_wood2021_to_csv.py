import openpyxl
import xlsxwriter
import sys
import csv
import os

## Converts the various tabs of the Wood 2021 dataset to CSV, for further processing.

def cell_str(cell):
    obj = cell.value
    if obj is None:
        return ''
    if cell.number_format == 'General':
        return str(cell.value)

    return str(cell.value)

def xlsx_to_csv(ifname, sheet_ofnames):
    """
    sheet_ofnames: [(sheetname, ofname), ...]
        Name of each sheet to export, and file to export to
    """

    # Open the xlsx file
    xlsx = openpyxl.load_workbook(ifname, read_only=True, data_only=True)    # data_only=True: Read values, not formulas
    sheet_ixs = {name:ix for ix,name in enumerate(xlsx.sheetnames)}

    # Write each specified sheet to CSV
    for name, ofname in sheet_ofnames:
        sheet = xlsx.worksheets[sheet_ixs[name]]
        data = sheet.rows

        with open(ofname, 'w') as out:
            ocsv = csv.writer(out)
            for row in data:
                ocsv.writerow([cell_str(cell) for cell in row])

def main():
    odir = 'data/wood2021'
    xls = os.path.join(odir, 'aba7282_Table_S1.xlsx')

    xlsx_to_csv(xls, [
        ('CE', os.path.join(odir, 'CE.csv')),
        ('CW', os.path.join(odir, 'CW.csv')),
        ('N', os.path.join(odir, 'N.csv')),
        ('NE', os.path.join(odir, 'NE.csv')),
        ('NW', os.path.join(odir, 'NW.csv')),
        ('SE', os.path.join(odir, 'SE.csv')),
        ('NW', os.path.join(odir, 'NW.csv')),
        ('SW', os.path.join(odir, 'SW.csv')),
])

main()
