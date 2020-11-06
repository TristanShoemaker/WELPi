import time
import pandas as pd


def message(message_text,
            color=None,
            tbl=None):
    class bcolors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKCYAN = '\033[96m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'

    timestamp = F"{time.strftime('%Y-%m-%d %H:%M:%S')}"
    if tbl is not None:
        message = pd.DataFrame([{"Message": message_text[0],
                                 "Value": message_text[1]}])
        message.set_index("Message", inplace=True)
        tbl.add_rows(message)
    if type(message_text) is list:
        print(F"[{timestamp}] {message_text[0]} {message_text[1]}", flush=True)
    else:
        print(F"[{timestamp}] {message_text}", flush=True)
