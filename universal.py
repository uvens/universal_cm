import csv
import gzip
from collections import deque
import logging
from logging.handlers import RotatingFileHandler
import os
import yaml
from lxml import etree

logger = logging.getLogger(__name__)

schema_filename = 'mini_cm_parser_schema.csv'
path_to_object = deque()
report = []
find_tag = ['lbpsStartTimeHour', 'lbpsDuration', 'lbpsDayOfWeek', 'lbpsStartTimeMinute', 'lbpsSuspended', 'lnCelId',
            'lbpsCellSOOrder', 'lbpsMaxLoad',
            'lbpsMinLoad', 'lbpsPdcchLoadOffset', 'lbpsLastCellRTXMinLoad', 'lbpsLastCellMinLoad', 'lbpsRTXMinLoad',
            'lbpsRTXMaxLoad', 'lbpsCSONCtlEnabled',
            'lbpsLastCellSOEnabled', 'lbpsRTXCellCapOffset', 'ulCacIgnore', 'energySavingState', 'actOnlineTXSwitch',
            'actLBRTXPowerSaving', 'actLBPowerSaving']
find_number = ['M8020C6', 'M40002C2', 'M40002C1', 'M40002C0', 'M8020C10', 'M8020C9', 'M8020C8', 'M8020C7', 'M8011C96',
               'M8011C97',
               'M8011C98', 'M8011C99', 'M8011C100', 'M8011C101', 'M8011C102', 'M8011C103', 'M8011C104',
               'M8011C105', 'M8011C106', 'M8011C107', 'M8011C90', 'M8011C91', 'M8011C92', 'M8011C93', 'M8011C94',
               'M8011C95']
fieldnames = ['path_to_object', 'mo_name', 'Parametr_id', 'value']


# DONE: add gz support
# DONE: report filename based on input filename
# DONE: add support of files list as input argument
# DONE: add name of file to report
# DONE: fix bug with path identification

# TODO: add managed element as a column in the report
# TODO: add cell name into report
# 	    vsDataEUtranCellTDD
# 	    vsDataEUtranCellFDD

# TODO: add multiprocessing
# TODO: big files support
# TODO: add expected value for each policy in schema
# TODO: add policy id for each line of report
# TODO: add filter for path_to_object
# TODO: add default None values for target attributes (don't care if it was found or not)
# TODO: remove duplicates in schema on schema load
# TODO: add app_name into schema and report
# TODO: support filter of  shcema by app_name for script to collect specific app data only


def init_my_logging():
    """
    Configuring logging for a SON-like appearance when running locally
    """
    logger.setLevel(logging.DEBUG)
    log_file_name = os.path.splitext(os.path.realpath(__file__))[0] + '.log'
    handler = RotatingFileHandler(log_file_name, maxBytes=10 * pow(1024, 2), backupCount=3)
    log_format = "%(asctime)-15s [{}:%(name)s:%(lineno)s:%(funcName)s:%(levelname)s] %(message)s".format(
        os.getpid())
    handler.setLevel(logging.DEBUG)
    try:
        from colorlog import ColoredFormatter
        formatter = ColoredFormatter(log_format)
    except ImportError:
        formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logger.addHandler(console)


def get_tag_without_schema(elem):
    tag = elem.tag.split('}')[-1]
    return tag


def open_yaml():
    with open("config.yaml", 'r') as stream:
        data_loaded = yaml.safe_load(stream)
        file_name = data_loaded['open_file']
        write_directory = data_loaded['write_directory']
        return file_name, write_directory


if __name__ == '__main__':
    init_my_logging()


    def add_data(data, elem):
        lst = []
        for e in elem.attrib:
            if elem.attrib.get('class') not in data:
                data[elem.attrib.get('class')] = []
            attribute = elem.attrib.get(e)
            if e == 'class':
                continue
            lst.append((e, attribute))
        data[elem.attrib.get('class')].append(lst)


    def add_data_list(data, elem, attribute, class_file):
        text = []
        for el in elem:
            if get_tag_without_schema(el):
                if el.text is None:
                    continue
                text.append(el.text)
        if text:
            text = ';'.join(text)
        else:
            text = ''
        data[class_file][-1].append((attribute, text))


    def add_data_class(data, elem, class_file):
        for e in elem.attrib:
            attribute = elem.attrib.get(e)
            if elem.text == 'name':
                continue
            if get_tag_without_schema(elem) == 'list':
                add_data_list(data, elem, attribute, class_file)
                continue
            data[class_file][-1].append((attribute, elem.text))


    def read_xml(xml_filename, write_directory):
        lst = []
        if xml_filename.split('.')[-1] == 'gz':
            xml_filename = gzip.open(xml_filename)
        data = {}
        logger.info(f'Working on {xml_filename}...')
        context = etree.iterparse(xml_filename, events=("start", "end"))
        file_name = xml_filename.split('/')[-1]
        class_file = None
        date_time = None
        logger.info(f'start context')
        for event, elem in context:
            tag = get_tag_without_schema(elem)
            if event == 'start':
                if elem.attrib:
                    class_file = class_file if elem.attrib.get('class') is None else elem.attrib.get('class')
                    date_time = date_time if elem.attrib.get('dateTime') is None else elem.attrib.get('dateTime')
                    if class_file is None:
                        continue
                    if 'class' in elem.attrib:
                        add_data(data, elem)

                    else:
                        add_data_class(data, elem, class_file)

            if event == 'end':
                if len(data) > 1:
                    for n, k in enumerate(data):
                        if n == 0:
                            fieldnames = ['FileName', 'dateTime'] + get_fieldnames(data[k])
                            if not check_file(k):
                                initialize_output(
                                    f'{write_directory}/{k}.csv',
                                    fieldnames)
                            add_to_data_file_name(data[k], file_name, date_time)
                            add_data_to_csv(data[k],
                                            f'{write_directory}/{k}.csv',
                                            fieldnames)
                            del data[k]
                            break
                elem.clear()

        return data


    def add_to_data_file_name(data, file_name, date_time):
        for d in data:
            d.insert(0, ('dateTime', date_time))
            d.insert(0, ('FileName', file_name))


    def check_file(file_name):
        directory = '/home/uventus/Works/NSN/Huawei-20230710T102516Z-001/Huawei_test_pm'
        filepath = os.path.join(directory, file_name + '.csv')
        if os.path.isfile(filepath):
            return True
        else:
            return False


    def get_fieldnames(spisok):
        lst = []
        for name in spisok:
            name = [i[0] for i in name]
            lst.extend(name)
        return sorted(list(set(lst)))


    def initialize_output(report_filename, fieldnames):
        with open(report_filename, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()


    def add_data_to_csv(path, report_filename, fieldnames):
        with open(report_filename, "a", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            for p in path:
                p = dict(p)
                writer.writerow(p)
            logger.info(f"Added row {len(path)} records to csv")


    # def process_directory(directory):
    #     for root, dirs, files in os.walk(directory):
    #         for file in files:
    #             file_path = os.path.join(root, file)
    #             lst = read_xml(file_path)
    #             file_name = file + '.csv'
    #             # initialize_output(file_name)
    #             # add_data_to_csv(lst, file_name)
    #
    #         for folder in dirs:
    #             folder_path = os.path.join(root, folder)
    #             process_directory(folder_path)

    def run():
        file_name, write_directory = open_yaml()
        read_xml(file_name, write_directory)


    run()
