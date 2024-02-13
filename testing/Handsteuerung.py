import json
from TinkerForgeHelperLib.tinkerforge_lib import *
from TinkerForgeHelperLib.tkinter_lib import *


# from .ChemTherm_library.tinkerforge_lib import *


def main():
    # t0 = time.time()
    json_name = "MFC_Settings"

    try:
        with open('./json_files/' + json_name + '.json', 'r') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        print("attempting automatic config")
        config = {}

    TFH("localhost", 4223, {})
    sleep(250)

    exit()

    # ipcon = IPConnection()
    # ipcon.connect("localhost", 4223)

    device_list = setup_devices(config, ipcon)
    window, frames = setup_gui(config, config)

    entry_list = {'File': config['PATH']['SaveFile'], 'T': create_set_temperature_entries(window, config, config['Background']['x'], config['Background']['y']), 'MFC': create_set_mfc_entries(window, device_list['MFC'], frames)}
    label_list = {'T':  create_tc_labels(window, device_list['T'], config), 'HP': create_hp_labels(window, device_list['HP'], config), 'MFC': create_mfc_labels(window, device_list['MFC'], frames, config), 'P': create_p_labels(window, device_list['P'], config)}
    entry_list['Save'] = setup_frames_labels_buttons(window, frames, config, device_list, entry_list, label_list)
    
    tk_loop(window, device_list, label_list, entry_list) 

    window.mainloop()
    print("shutting down...")

    [hp.stop() for hp in device_list['HP']]
    [mfc.stop() for mfc in device_list['MFC']]

    sleep(2)
    ipcon.disconnect()
    print("bye bye") 


if __name__ == "__main__":
    main()
