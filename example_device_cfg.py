from devices import Devices

config = {
    {
        "mfc_2": {
            "type": "mfc",
            "input_device": "23S1",
            "input_channel": 0,
            "output_device": "TkW",
            "output_channel": 1,
            "output_param": Devices.IndustrialDigitalOut4.mode_pwm,
            "gradient": 0.2,
            "x": 50,
            "y": 20
        },
        "mfc_3": {
            "type": "mfc",
            "input_device": "23S1",
            "input_channel": 1,
            "output_device": "TkW",
            "output_channel": 3,
            "output_param": Devices.IndustrialDigitalOut4.mode_digital,
            "gradient": 0.2,
            "x": 50,
            "y": 20
        }
    }
}
