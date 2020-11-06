from datetime import datetime
import pandas as pd


def message(message_text,
            mssgType='ENDC',
            tbl=None):
    colors = {'HEADER': '\033[95m',
              'TIMING': '\033[94m',
              'ADMIN': '\033[96m',
              'SUCCESS': '\033[92m',
              'WARNING': '\033[93m',
              'ERROR': '\033[91m',
              'ENDC': '\033[0m',
              'BOLD': '\033[1m',
              'UNDERLINE': '\033[4m'}

    timestamp = (F"{colors['BOLD']}"
                 F"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
                 F"{colors['ENDC']}")
    if tbl is not None:
        message = pd.DataFrame([{"Message": message_text[0],
                                 "Value": message_text[1]}])
        message.set_index("Message", inplace=True)
        tbl.add_rows(message)
    if type(message_text) is list:
        print(F"{timestamp} "
              F"{colors[mssgType]}{message_text[0]}{colors['ENDC']}"
              F"{message_text[1]}",
              flush=True)
    else:
        print(F"{timestamp} "
              F"{colors[mssgType]}{message_text}{colors['ENDC']}",
              flush=True)
