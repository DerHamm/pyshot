import os
import lightshot_logger


from pathlib import Path





LOGGER = lightshot_logger.get_logger()




def safe_open(path, mode, *args, **kwargs):

    if type(path) == str:
        path_object = Path(path)
    else:
        path_object = path

    handle = None
    try:
        handle = open(path_object, mode, *args, **kwargs)
    except Exception as e:
        LOGGER.error(e)

    return handle


