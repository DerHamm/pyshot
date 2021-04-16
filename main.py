import lightshot_logger
import argparse
LOGGER = lightshot_logger.get_logger()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pyshot commandline tool')

    parser.add_argument('-g', '--generate', help='generate link files', action='store_true')
    parser.add_argument('-d', '--download', help='start to download from link files, pass number to start from', metavar='NUM')
    args = parser.parse_args().__dict__
    if args['generate']:
        # ignore -d flag
        from lightshot_gendb import run_main
        run_main()
    elif args['download'] is not None:
        try:
            download_number = int(args['download'])
        except:
            download_number = 1
        from lightshot_proxies import run_main
        run_main(download_number)
    else:
        print('you have to pass arguments, moron')



