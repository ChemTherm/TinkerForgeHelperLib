
from tinkerforge_lib import TFH
from time import sleep


# from .ChemTherm_library.tinkerforge_lib import *


def main():
    # t0 = time.time()
    json_name = "MFC_Settings"
    tfh_obj = TFH("localhost", 4223, json_name)

    try:
        sleep(250)
    except (KeyboardInterrupt, SystemExit):
        tfh_obj.cleanup()
    exit()


if __name__ == "__main__":
    main()
