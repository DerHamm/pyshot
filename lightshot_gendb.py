from util_functions import safe_open
import pandas
import time
from pathlib import Path
from threading import Thread
import lightshot_logger
import os

LOGGER = lightshot_logger.get_logger()

# Generate the first possible ~ 2 000 000 000 url keys in ~100 MB CSVs for porting them one after one into the database

class Base36(object):

    ALPHABET = \
      "0123456789abcdefghijklmnopqrstuvwxyz"

    def encode(self, n):
        try:
            return self.ALPHABET[n]
        except IndexError:
            raise Exception("cannot encode: %s" % n)


    def dec_to_base(self, dec=0, base=len(ALPHABET)):
        if dec < base:
            return self.encode(dec)
        else:
            return self.dec_to_base(dec // base, base) + self.encode(dec % base)



def get_csv_path_list():
    path_list = list()

    for root, _, filenames in os.walk('data'):
        for file_name in filenames:
            path_list.append(os.path.join(root, file_name))
    return path_list


def consume_next_csv():
    # Populate a list of those csvs that are generated, but not consumed yet
    return_val = False
    path_list = get_csv_path_list()
    consumed_csvs_path = Path('data/consumed_csvs.txt')

    if os.path.exists(consumed_csvs_path):
        with safe_open(consumed_csvs_path, 'r') as f:
            content = f.readlines()
            f.close()
        for already_consumed_path in content:
            if already_consumed_path in path_list:
                path_list.remove(already_consumed_path)

    # consume the csv into the database

    if len(path_list) > 0:
        LOGGER.debug('Found {} not yet consumed lists of keys'.format(len(path_list)))
        # return_val = consume_into_database(path_list[0])
        return_val = True

        # update consumed_csvs.txt
        with safe_open(consumed_csvs_path, 'w') as f:
            f.writelines(path_list)
            f.close()

        LOGGER.debug('Consumed CSV {} into the database'.format(path_list[0]))

    return return_val


def generate_csv(path, loop_limit):

    then = time.time()
    base36 = Base36()
    LOGGER.debug('Beginning to generate CSV at: {}'.format(path))


    can_quit = False
    index = max(0, loop_limit - 12500000)
    csv_list = [str(base36.dec_to_base(i)).rjust(6, '0') for i in range(index, loop_limit)]

    if len(csv_list[-1]) > 6:
        LOGGER.debug('We are almost done, last frame is being generated now')
        can_quit = True
        while len(csv_list[-1]) > 6:
            del csv_list[-1]

    frame = pandas.DataFrame(csv_list, columns=['link_names'])
    frame.to_csv(path, sep=';', index=False, header=False)
    LOGGER.debug('CSV generated: {} Range: {} - {} Time: {}'.format(path, index, loop_limit, round(time.time()-then, 2)))
    del csv_list

    return can_quit


def run_main():

    data_path = Path('data')
    if not data_path.exists():
        data_path.mkdir()
    MAX_LIMIT = 2187500000
    # +[1] so that max(list) at least returns 1
    value_list = [int(os.path.splitext(os.path.split(csv_path)[1])[0][-3:]) for csv_path in get_csv_path_list()] + [1]
    index = max(value_list)
    limit = index * 12500000
    while limit < MAX_LIMIT:
        generate_csv('data/links{}.txt'.format(str(index).rjust(3, '0')), limit)
        limit += 12500000
        index += 1

    quit(0)


if __name__ == '__main__':
    run_main()