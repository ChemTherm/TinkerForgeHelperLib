#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime as dt
from datetime import timedelta
from enum import IntEnum
import json
from time import sleep

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
from tinkerforge.bricklet_industrial_quad_relay_v2 import BrickletIndustrialQuadRelayV2

from tinkerforge.ip_connection import IPConnection
from tinkerforge.ip_connection import Error as IPConnError
from threading import Thread
from .control_types import Controls
import inspect
import itertools

'''
@ TODO: 🔲 ✅
 🔲 check the super init bevhiour in regards to setting a value after before super
 ✅ master brick reconnect handling 
 ✅make a listing of linked devices in case of connection loss for failsafes?
 🔲 making Inputdevice and Outputdevice based on a baseclass 
'''

default_timeout = timedelta(milliseconds=1000)


def get_config(config_name):
    """
    Lädt die Konfiguration entweder aus einer JSON-Datei oder aus dem config-Modul
    und filtert dabei alle Einträge heraus, die den String "Modbus" (oder "Mobus") enthalten.
    
    :param config_name: Name der JSON-Datei (ohne Endung) oder False, um das config-Modul zu verwenden.
    :return: Gefiltertes Konfigurationsdictionary oder None bei Fehler.
    """
    def contains_modbus(item):
        """
        Rekursive Hilfsfunktion, die prüft, ob im übergebenen Objekt (String, Liste, Dict)
        der Substring "modbus" (oder "mobus") enthalten ist.
        """
        if isinstance(item, str):
            # Prüft in Kleinbuchstaben, ob "modbus" oder "mobus" vorkommt
            return "modbus" in item.lower() or "mobus" in item.lower()
        elif isinstance(item, dict):
            return any(contains_modbus(value) for value in item.values())
        elif isinstance(item, list):
            return any(contains_modbus(elem) for elem in item)
        else:
            return False

    try:
        # Konfiguration laden: entweder aus einer JSON-Datei oder aus dem config-Modul
        if config_name:
            with open(f'./json_files/{config_name}.json', 'r') as config_file:
                config_data = json.load(config_file)
        else:
            import config as cfg
            config_data = cfg.config  # Hier wird cfg.config verwendet

        # Filtere alle Einträge, bei denen der Substring "Modbus" (oder "Mobus") irgendwo vorkommt
        filtered_config = {k: v for k, v in config_data.items() if not contains_modbus(v)}
        return filtered_config

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config: {e}")
        return None


class TFH:
    class OperationModes(IntEnum):
        normalMode = 0
        dummyMode = 1

    class WarningLevels(IntEnum):
        normal = 0
        failOperational = 1
        failSafe = 2
        shutdown = 4    # TBD

    class IOtypes(IntEnum):
        inputDevice = 1
        outputDevice = 2

    class Control:
        def __init__(self):
            self.last_deviation = False

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
            self.ioType = 0
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

        def __init__(self, uid, conn, args):
            super().__init__(uid, 2)
            self.dev = BrickletIndustrialDualAnalogInV2(uid, conn)
            self.dev.register_callback(self.dev.CALLBACK_ALL_VOLTAGES, self.collect_all)
            self.dev.set_all_voltages_callback_configuration(500, False)

    class IndustrialDual020mAV2(InputDevice):
        device_type = 2120

        def __init__(self, uid, conn, args):
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
            #print(f"reading input on device {self.uid} - {channel} {value}")
            

    class ThermoCouple(InputDevice):
        device_type = 2109
        
        def __init__(self, uid, conn, typ='N'):
            super().__init__(uid, 1)
            self.dev = BrickletThermocoupleV2(uid, conn)        
            type_dict = {'B': 0, 'E': 1, 'J': 2, 'K': 3, 'N': 4, 'R': 5, 'S': 6, 'T': 7}
            thermocouple_type = type_dict[typ] 
            #try:
            #    thermocouple_type = type_dict[typ.upper()]
            #except KeyError:
            #    print(f"invalid thermocouple config for {uid}, type not found {typ}")
            #    exit()
            self.dev.set_configuration(16, thermocouple_type, 0)
            self.dev.register_callback(self.dev.CALLBACK_TEMPERATURE, self.collect_temperature)
            self.dev.set_temperature_callback_configuration(100, False, "x", 0, 0)

        def collect_temperature(self, temperature):
            self.values[0] = temperature/100
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
            self.ioType = TFH.OutputDevice

    class DualRelay(OutputDevice):
        device_type = 284

        def __init__(self, uid, conn, args):
            super().__init__(uid, 2)
            self.values = [False] * 2
            self.dev = BrickletIndustrialDualRelay(uid, conn)

        def set_outputs(self):
            self.dev.set_value(*self.values)

    class QuadRelayV2(OutputDevice):
        device_type = 2102

        def __init__(self, uid, conn, args):
            super().__init__(uid, 2)
            self.values = [False, False, False , False]
            self.dev = BrickletIndustrialQuadRelayV2(uid, conn)

        def set_outputs(self):
            self.dev.set_value(self.values)

    class IndustrialAnalogOutV2(OutputDevice):
        device_type = 2116

        def __init__(self, uid, conn, args):
            super().__init__(uid, 2)
            self.dev = BrickletIndustrialAnalogOutV2(uid, conn)
            
            if uid == "27A7":
                self.dev.set_current(0)
            else:
                self.dev.set_voltage(0)
            self.dev.set_enabled(True)              
            self.dev.set_out_led_status_config(0, 5000, 1)



    class IndustrialDigitalOut4(OutputDevice):
        device_type = 2124

        def __init__(self, uid, conn, args):
            super().__init__(uid, 4)
            self.values = [False] * 4
            self.dev = BrickletIndustrialDigitalOut4V2(uid, conn)
            self.frequency = 10
            self.dev.set_pwm_configuration(0, self.frequency, 0)
            self.dev.set_pwm_configuration(1, self.frequency, 0)
            self.dev.set_pwm_configuration(2, self.frequency, 0)
            self.dev.set_pwm_configuration(3, self.frequency, 0) 

        def set_outputs(self):
            self.dev.set_value(self.values)
           #print(self.values)
            self.dev.set_pwm_configuration(0, self.frequency, self.values[0]* self.frequency*1000)
            self.dev.set_pwm_configuration(1, self.frequency, self.values[1]* self.frequency*1000)
            self.dev.set_pwm_configuration(2, self.frequency, self.values[2]* self.frequency*1000)
            self.dev.set_pwm_configuration(3, self.frequency, self.values[3]* self.frequency*1000)

    # @TODD: WIP
    class SilentStepper(OutputDevice):
        device_type = 19

        def __init__(self, uid, conn, args):
            super().__init__(uid, 1)
            self.dev = BrickSilentStepper(uid, conn)
            self.dev.enable()

        def stop(self):
            self.dev.stop()

    def __init__(self, ip, port, config_name=False, debug_mode=OperationModes.normalMode):
        self.conn = IPConnection()
        self.conn.connect(ip, port)
        self.conn.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)
        
        self.devices_present = {}
        self.input_devices_required = set()
        self.output_devices_required = set()
        self.operation_mode = debug_mode
        self.config = get_config(config_name)
        self.inputs = {}
        self.outputs = {}
        self.controls = {}
        self.args ={}
        self.verify_config_devices()

        self.run = True
        self.main_loop = Thread(target=self.__loop)
        self.main_loop.start()

    def get_brick_name(self, type_no):
        if type_no == 13:
            return "Master Brick"
        for name, obj in inspect.getmembers(self):
            if hasattr(obj, "__bases__") and any(_ in obj.__bases__ for _ in [self.InputDevice, self.OutputDevice]):
                if type_no == obj.device_type:
                    return name
        return "Unknown"

    def get_io_cls(self, parent_cls, device_identifier):
        """
        returns the child cls of a given device identifier, if none matches it returns None
        """
        for name, obj in inspect.getmembers(self):
            if hasattr(obj, "__bases__") and parent_cls in obj.__bases__:
                if obj.device_type == device_identifier:
                    return obj
        return None

    def cleanup(self):
        self.run = False
        sleep(0.2)
        if  self.operation_mode != self.OperationModes.dummyMode:
            for uid, output_dev in self.outputs.items():
                for index in range(output_dev.output_cnt):
                    output_dev.values[index] = 0
                try:
                    output_dev.stop()
                except AttributeError:
                    pass
            self.__manage_outputs()

    def __loop(self):
        print("starting main loop")
        while self.run:
            self.__manage_inputs()
            self.__run_controls()
            self.__manage_outputs()
            sleep(0.1)

    def __run_failsafe_control(self):
        pass

    def __run_controls(self):
        for control_name, control_rule in self.config.items():
            # presence of these is already checked in verify_config_devices, not the value type
            input_channel = control_rule.get("input_channel")
            input_device_uid = control_rule.get("input_device")
            output_channel = control_rule.get("output_channel")
            output_device_uid = control_rule.get("output_device")

            if self.operation_mode == 1 or input_device_uid is None or control_rule.get("type") == "easy_PI" or control_rule.get("type") == "direct_Heat" or "extern" in control_rule["type"].lower():
                continue
            if not self.inputs[input_device_uid].operational:
                self.__run_failsafe_control()
                continue

            input_val = self.inputs[input_device_uid].values[input_channel]

            # a 0 value is technically False but ... not a sensible value either
            permissible_deviation = control_rule.get("permissible_deviation", False)
            if permissible_deviation:
                delta = abs(input_val - self.outputs[output_device_uid].values[output_channel])
                if delta > permissible_deviation * soll_input:
                    last_deviation = self.controls[control_name].get("last_deviation")

                    if last_deviation and last_deviation - dt.now() > timedelta(seconds=30):
                        msg = f"device {control_name} is deviating more than the permissible amount"
                        # @todo: make this happen only once?
                        logging.warning(msg)
                        print(msg)
                    else:
                        self.controls[control_name].last_deviation = dt.now()
                else:
                    self.controls[control_name].last_deviation = False

    def __manage_inputs(self):
        """
        purely managing timeouts and failsafe, the reading of values is done by the callbacks
        """
        now = dt.now()

        for uid, input_dev in self.inputs.items():
            if isinstance(input_dev, self.DummyDevice):
                continue
            input_dev.operational = True
            delta = now - input_dev.activity_timestamp
            if delta > input_dev.timeout:
                input_dev.operational = False
                for i in range(input_dev.input_cnt):
                    input_dev.values[i] = "NAN"
                print(f"timeout detected from uid {uid} {input_dev.activity_timestamp}")

    def __manage_outputs(self):
        for uid, output_dev in self.outputs.items():

            if isinstance(output_dev, self.DummyDevice):
                continue

            try:
                _ = output_dev.dev.get_enabled()
            except AttributeError as _:
                # some devices like BrickletIndustrialDualRelay do not support this method
                pass
            except IPConnError as exp:
                print(f"connection to output {uid} - "
                      f"{type(output_dev).__name__} has been lost "
                      f"{exp}")
            try:
                output_dev.set_outputs()
                continue
            except AttributeError:
                pass

            try:
                if uid == "27A7":
                    output_dev.dev.set_current(output_dev.values[0])
                else:
                    output_dev.dev.set_voltage(output_dev.values[0])
                # @TODO there needs to be a check on the channels and device specific fncs/class or whatever
            except Exception as exp:
                print(exp)

    def verify_config_devices(self):
        """
        collects the UIDs of the connected device and checks against the listing of UIDs given from the config
        If not every required device is given an Error is given
        """

        print("listing devices present: \n")
        # @todo define required and optional device from parsing

        self.conn.enumerate()
        sleep(0.2)

        if not len(self.devices_present) and self.operation_mode != self.OperationModes.dummyMode:
            raise ConnectionError("No Tinkerforge module found, check connection to master brick")

        channels_required = {}
        self.uid_to_device_keys = {}  # UID → Liste von device_keys, falls mehrere Keys dasselbe Gerät verwenden

        for device_key, value in self.config.items():
            self.args[device_key] = " "
            print(f"checking devices for {device_key}")
            type_requirements = Controls.types.get(value["type"], Controls.Entries.hasOutputs + Controls.Entries.hasInputs)
             # Überspringe externe Geräte, z.B. Modbus oder über andere Protokolle
            if "type" in value and "extern" in value["type"].lower():
                print(f"Skipping device {device_key} because its type is 'extern'")
                continue
            if "type" in value and "modbus_pump" in value["type"].lower():
                print(f"Skipping device {device_key} because its type is 'Modbus_Pump'")
                continue
            if "input_device" in value and "modbus" in value["input_device"].lower() or "output_device" in value and "modbus" in value["output_device"].lower():
                print(f"Skipping device {device_key} because its type is 'Modbus_Pump'")
                continue

            if type_requirements & Controls.Entries.hasOutputs:
                if not all(key in value for key in ("output_device", "output_channel")):
                    print(f"invalid config for device {device_key} due to missing output parameter")
                    exit()
                output_uid = value.get("output_device")
                used_output_channels = channels_required.get(output_uid, [])
                req_output_chann = value.get("output_channel")
                if req_output_chann in used_output_channels:
                    print(f"invalid config: {device_key} has overlapping channels with previous configured devices")
                    exit()
                used_output_channels.append(req_output_chann)
                channels_required[output_uid] = used_output_channels
                self.output_devices_required.add(output_uid)
                # Zuordnung UID → device_key
                self.uid_to_device_keys.setdefault(output_uid, []).append(device_key)

            if type_requirements & Controls.Entries.hasInputs:
                # Spezielle Behandlung für Thermoelemente
                if value["type"] == "thermocouple":
                    if "tc_type" not in value:
                        print(f"tc_type fehlt für Gerät {device_key}, Programm wird beendet")
                        exit()
                    else:
                        self.args[device_key] = value.get("tc_type")

                # Allgemeine Prüfung auf fehlende Parameter
                if not all(key in value for key in ("input_device", "input_channel")) and not value["type"] == "thermocouple" :
                    print(f"invalid config for device {device_key} due to missing input parameter")
                    exit()
                input_uid = value.get("input_device")
                used_input_channels = channels_required.get(input_uid, [])
                req_input_chann = value.get("input_channel")
                if req_input_chann in used_input_channels:
                    print(f"invalid config: {device_key} has overlapping channels with previous configured devices")
                    exit()
                used_input_channels.append(req_input_chann)
                channels_required[input_uid] = used_input_channels
                self.input_devices_required.add(input_uid)
                 # Zuordnung UID → device_key
                self.uid_to_device_keys.setdefault(input_uid, []).append(device_key)

            self.controls[device_key] = self.Control()
            print("VALID config!")

        self.setup_devices()

        for uid in itertools.chain(self.input_devices_required, self.output_devices_required):
            if uid not in self.devices_present and self.operation_mode == 0:
                raise ModuleNotFoundError(f"Missing Tinkerforge Element: {uid}")
        print("\nvalid setup for configured initialisation detected \n")

    def cb_enumerate(self, uid, connected_uid, _, hardware_version, firmware_version,
                     device_identifier, enumeration_type):

        if enumeration_type == IPConnection.ENUMERATION_TYPE_DISCONNECTED:
            # in case of a master disconnect the device_type is listed as 0 for all lost devices
            try:
                dev = self.devices_present[uid]
                if dev.get("parent_uid", 0) == 0:
                    print(f"Disconnect detected from Master Brick: {uid} - along with following devices")
                else:
                    print(f"Disconnect detected from device: {uid} - "
                         f"{self.get_brick_name(dev.get('device_identifier', 0))}")
            except KeyError:
                pass
            return

        if uid not in self.devices_present.keys():
            self.devices_present[uid] = {"device_identifier": device_identifier, "parent_uid": connected_uid}
            print("UID:               " + uid)
            print("Connected UID:     " + connected_uid)
            # print("Position:          " + _)
            print("Hardware Version:  " + str(hardware_version))
            print("Firmware Version:  " + str(firmware_version))
            print("Device Identifier: " + str(device_identifier) + f" - {self.get_brick_name(device_identifier)}")
            print("")
        else:
            print(f"reconnect detected from device: {uid} - "
                  f"{self.get_brick_name(device_identifier)}")
            if uid in itertools.chain(self.input_devices_required, self.output_devices_required):
                self.setup_device(uid)

    def setup_device(self, uid, args=()):
        device_entry = self.devices_present.get(uid)
        if device_entry is None:
            print(f"Setup of not present device requested {uid}")
            if self.operation_mode == self.OperationModes.dummyMode:
                print(f"Setup device  {uid} as dummy")
                if uid in self.output_devices_required:
                    self.outputs[uid] = self.DummyDevice(uid)
                else:
                    self.inputs[uid] = self.DummyDevice(uid)
            return

        device_identifier = device_entry.get("device_identifier")

        try:
            old_values = self.outputs[uid].values
        except (KeyError, AttributeError):
            old_values = False
        cls = self.get_io_cls(TFH.InputDevice, device_identifier)
        if cls is not None:
            #print(args)
            dev = self.inputs[uid] = cls(uid, self.conn, args)
        else:
            cls = self.get_io_cls(TFH.OutputDevice, device_identifier)
            if cls is not None:
                dev = self.outputs[uid] = cls(uid, self.conn, args)
            else:
                print(f"{uid} failed to setup device due to unknown device type {device_identifier}")
                exit()

        if old_values:
            dev.values = old_values
            
        if any(str(arg).strip() for arg in args):
            print(f"successfully setup device {uid} - {type(dev).__name__} "
                  f"with argument(s): {', '.join(map(str, args))}")
        else:
            print(f"successfully setup device {uid} - {type(dev).__name__}")

    def setup_devices(self):
        for key in itertools.chain(self.input_devices_required, self.output_devices_required):
            device_keys = self.uid_to_device_keys.get(key, [])
            for dk in device_keys:
                args = self.args.get(dk, ())
                self.setup_device(key, args)
