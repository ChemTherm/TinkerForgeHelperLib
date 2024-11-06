from datetime import datetime as dt
from datetime import timedelta
from enum import IntEnum

from tinkerforge.brick_silent_stepper import BrickSilentStepper
from tinkerforge.bricklet_thermocouple_v2 import BrickletThermocoupleV2
from tinkerforge.bricklet_industrial_digital_out_4_v2 import BrickletIndustrialDigitalOut4V2
from tinkerforge.bricklet_industrial_analog_out_v2 import BrickletIndustrialAnalogOutV2
from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3
from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3
from tinkerforge.bricklet_industrial_dual_analog_in_v2 import BrickletIndustrialDualAnalogInV2
from tinkerforge.bricklet_industrial_dual_0_20ma_v2 import BrickletIndustrialDual020mAV2
from tinkerforge.bricklet_industrial_dual_relay import BrickletIndustrialDualRelay
from tinkerforge.bricklet_industrial_digital_in_4_v2 import BrickletIndustrialDigitalIn4V2

default_timeout = timedelta(milliseconds=1000)


class Devices:
    class IOtypes(IntEnum):
        inputType = 1
        outputType = 2

    class DummyDevice:
        def __init__(self, uid, channel_cnt=4):
            self.uid = uid
            self.values = [0] * channel_cnt

    class InputDevice:
        def __init__(self, uid, input_cnt, timeout=default_timeout):
            self.uid = uid
            self.input_cnt = input_cnt
            self.values = [0] * input_cnt
            self.activity_timestamp = dt.now()
            self.operational = True
            self.timeout = timeout
            # actually not used yet
            self.ioType = Devices.IOtypes.inputType

        def reset_activity(self):
            self.activity_timestamp = dt.now()

        def collect_all(self, _args):
            for i, value in enumerate(_args):
                # print(f"reading input on device {self.uid} - {i} {value}")
                self.values[i] = value
            # @Todo: is there a less costly check?
            self.reset_activity()

    class IndustrialDualAnalogInV2(InputDevice):
        device_type = 2121

        def __init__(self, uid, conn, args=None):
            super().__init__(uid, 2)
            self.dev = BrickletIndustrialDualAnalogInV2(uid, conn)
            self.dev.register_callback(self.dev.CALLBACK_ALL_VOLTAGES, self.collect_all)
            self.dev.set_all_voltages_callback_configuration(500, False)

    class IndustrialDual020mAV2(InputDevice):
        device_type = 2120

        def __init__(self, uid, conn, args=None):
            self.current_channel = 0
            super().__init__(uid, 2)
            self.dev = BrickletIndustrialDual020mAV2(uid, conn)
            for channel in range(self.input_cnt):
                self.dev.register_callback(self.dev.CALLBACK_CURRENT, self.collect_single_current)
                self.dev.set_current_callback_configuration(channel, 500,
                                                            False, "x", 0, 0)

        def collect_single_current(self, channel, value):
            self.values[channel] = value
            self.reset_activity()
            # print(f"reading input on device {self.uid} - {channel} {value}")


    class ThermoCouple(InputDevice):
        device_type = 2109

        def __init__(self, uid, conn, args=[(1, 'N')]):
            super().__init__(uid, 1)
            self.dev = BrickletThermocoupleV2(uid, conn)
            type_dict = {'B': 0, 'E': 1, 'J': 2, 'K': 3, 'N': 4, 'R': 5, 'S': 6, 'T': 7}
            print("thermocouple init")
            typ, *_ = args
            typ = typ[1]
            print(typ)
            try:
                thermocouple_type = type_dict[typ.upper()]
            except KeyError:
                print(f"invalid thermocouple config for {uid}, type not found {typ}")
                exit()
            self.dev.set_configuration(16, thermocouple_type, 0)
            self.dev.register_callback(self.dev.CALLBACK_TEMPERATURE, self.collect_temperature)
            self.dev.set_temperature_callback_configuration(100, False, "x", 0, 0)

        def collect_temperature(self, temperature):
            self.values[0] = temperature / 100
            self.reset_activity()


    # @TODO: split PWM and Boolean handling
    class IndustrialDigitalIn4(InputDevice):
        device_type = 2100

        def cb_value(self, channel, changed, value):
            self.values[channel] = value
            self.reset_activity()

        def __init__(self, uid, conn):
            super().__init__(uid, 4)
            self.dev = BrickletIndustrialDigitalIn4V2(uid, conn)
            self.dev.register_callback(self.dev.CALLBACK_VALUE, self.cb_value)
            self.dev.set_value_callback_configuration(0, 100, False)
            self.dev.set_value_callback_configuration(1, 100, False)
            self.dev.set_value_callback_configuration(2, 100, False)
            self.dev.set_value_callback_configuration(3, 100, False)
            # TODO: consider configurations
            # Configureing rising edge count (channel 3) with 10ms debounce
            # self.dev.set_edge_count_configuration(3, 0, 10)

    class OutputDevice:
        def __init__(self, uid, output_cnt):
            self.uid = uid
            self.dev = None
            self.output_cnt = output_cnt
            self.values = [0] * output_cnt
            self.ioType = Devices.IOtypes.outputType

    class DualRelay(OutputDevice):
        device_type = 284

        def __init__(self, uid, conn, args=None):
            super().__init__(uid, 2)
            self.values = [False] * 2
            self.dev = BrickletIndustrialDualRelay(uid, conn)

        def set_outputs(self):
            self.dev.set_value(*self.values)

    class IndustrialAnalogOutV2(OutputDevice):
        device_type = 2116
        voltage_channel = 0
        current_channel = 1

        def __init__(self, uid, conn, args=None):
            super().__init__(uid, 2)

            self.dev = BrickletIndustrialAnalogOutV2(uid, conn)
            self.dev.set_voltage(0)
            self.dev.set_current(0)
            self.dev.set_enabled(True)
            self.dev.set_out_led_status_config(0, 5000, 1)

        def set_outputs(self):
            self.dev.set_voltage(self.values[self.voltage_channel])
            self.dev.set_current(self.values[self.current_channel])

    class IndustrialDigitalOut4(OutputDevice):
        device_type = 2124
        mode_pwm = "PWM"
        mode_digital = "DIGITAL"

        def __init__(self, uid, conn, args=None):
            super().__init__(uid, 4)
            self.values = [False] * 4
            self.modes = [False] * 4
            self.dev = BrickletIndustrialDigitalOut4V2(uid, conn)
            self.frequency = 100
            for channel, mode in args:
                if not mode:
                    continue
                self.modes[channel] = mode
                if mode.upper() == self.mode_pwm:
                    self.dev.set_pwm_configuration(channel, self.frequency, 0)
                elif mode.upper() == self.mode_digital:
                    self.dev.set_selected_value(channel=channel, value=False)
                else:
                    exit(f"default parameter for device {uid} given, no default permitted, exiting")

        def set_outputs(self):
            for channel, mode in enumerate(self.values):
                if not mode:
                    continue
                if mode.upper() == self.mode_pwm:
                    self.dev.set_pwm_configuration(channel, self.values[channel], 0)
                elif mode.upper() == self.mode_digital:
                    self.dev.set_selected_value(channel=channel, value=self.values[channel])

    # @TODD: WIP
    class SilentStepper(OutputDevice):
        device_type = 19

        def __init__(self, uid, conn, args=None):
            super().__init__(uid, 1)
            self.dev = BrickSilentStepper(uid, conn)
            self.dev.enable()

        def stop(self):
            self.dev.stop()
