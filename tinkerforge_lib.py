#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from datetime import datetime as dt
from datetime import timedelta
import tinkerforge as tf
import tinkerforge.ip_connection

from tinkerforge.bricklet_thermocouple_v2 import BrickletThermocoupleV2
from tinkerforge.bricklet_industrial_digital_out_4_v2 import BrickletIndustrialDigitalOut4V2
from tinkerforge.bricklet_industrial_analog_out_v2 import BrickletIndustrialAnalogOutV2
from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3
from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3
from tinkerforge.bricklet_industrial_dual_analog_in_v2 import BrickletIndustrialDualAnalogInV2
from tinkerforge.bricklet_industrial_dual_0_20ma_v2 import BrickletIndustrialDual020mAV2
import json

from time import sleep

# unused imports just keeping them around for now

# from tinkerforge.bricklet_industrial_dual_relay import BrickletIndustrialDualRelay
# import tkinter as tk
# from PIL import Image,ImageTk
# import time
from tinkerforge.ip_connection import IPConnection

from threading import Thread

'''
make a listing of linked devices in case of connection loss for failsafes?
dict vs lists vs classes to save on input and dict callups

disconnects: the disconnects of the master brick gets detected the others fails siltently 

 * Calibration? is this something to be done on startup? or manually from brickviewer?
 
 what to do when an output fails?
 @TODO check json failure handling
 
'''

# @todo Integrate this more neatly
device_identifier_types = {
    13: "Master Brick",
    19: "Silent Stepper",
    284: "Industrial Dual Relay",
    2100: "Industrial Digital In 4 Bricklet 2.0",
    2109: "Thermocouple",
    2120: "Industrial Dual 0-20mA 2.0",
    2124: "Industrial Digital Out 4 Bricklet 2.0",
    2121: "Industrial Dual Analog In Bricklet 2.0",
    2116: "Industrial Analog Out Bricklet 2.0",

}
default_timeout = timedelta(milliseconds=1000)


def get_config(config_name):
    if config_name:
        try:
            with open('./json_files/' + config_name + '.json', 'r') as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            print("missing config file")
        except json.decoder.JSONDecodeError as err:
            print(f"Config error:\n{err} \ncannot open config")
        exit()
    else:
        try:
            import testing.json_files.config as cfg
            return cfg.config
        except ModuleNotFoundError:
            exit("no backup python config present, exiting")


class TFH:
    # Industrial Analog Out Bricklet 2.0     2116  25si
    # Industrial Dual Analog In Bricklet 2.0 2121  23Uf

    class Control:
        def __init__(self):
            self.last_deviation = False

    class InputDevice:
        def __init__(self, uid, device_type, timeout=default_timeout):
            self.uid = uid
            # @Todo: need to define the input count since we cannot assign value in process without defining prior
            self.values = [0, 0]
            self.activity_timestamp = dt.now()
            self.operational = True
            self.type = device_type
            self.timeout = timeout

        def collect_inputs(self, _args):
            for i, value in enumerate(_args):
                # print(f"reading input on device {self.uid} - {i} {value}")
                self.values[i] = value
            # @Todo: is there a less costly check?
            self.activity_timestamp = dt.now()

    class OutputDevice:
        def __init__(self, uid, device_type, dev_obj):
            self.uid = uid
            self.device_type = device_type
            self.obj = dev_obj
            self.val = [0, 0]

    def __init__(self, ip, port, config_name=False, debug=False):
        self.conn = IPConnection()
        self.conn.connect(ip, port)
        self.conn.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)
        self.devices_present = {}
        self.debugMode = debug
        self.config = get_config(config_name)
        self.inputs = {}
        self.outputs = {}
        self.controls = {}
        self.verify_config_devices()
        # self.setup_devices()
        self.run = True
        self.operation_mode = True
        self.main_loop = Thread(target=self.__loop)
        self.main_loop.start()

        # @Todo create flags for this with different fail safe and operational mode
    def cleanup(self):
        # @TODO: defenitely an argument to set values to something like a defined failsafe/shutdown state
        self.run = False

    def __loop(self):
        print("starting main loop")
        while self.run:
            self.__manage_inputs()
            self.__run_controls()
            self.__manage_outputs()
            sleep(0.1)  # sleeps are not ideal iirc

    def __run_controls(self):
        for control_name, control_rule in self.config.items():
            # presence of these is already checked in verify_config_devices, not the value type
            input_channel = control_rule.get("input_channel")
            input_device_uid = control_rule.get("input_device")
            output_channel = control_rule.get("output_channel")
            output_device_uid = control_rule.get("output_device")

            gradient = control_rule.get("gradient")
            x = control_rule.get("x")
            y = control_rule.get("y")

            # @TODO: needs to be neater
            for element in [gradient, x, y]:
                if element is None:
                    print("missing control config")
                    exit()

            # print(self.inputs[input_device_uid].values[input_channel])
            input_val = self.inputs[input_device_uid].values[input_channel]
            converted_value = (input_val - y) * gradient
            print(f"{control_name}: in - {input_val} - {converted_value}")

            soll_input = 0
            self.outputs[output_device_uid].val[output_channel] = input_val

            # a 0 value is technically False but ... not a sensible value either
            permissable_deviation = control_rule.get("permissible_deviation", False)
            if permissable_deviation:
                delta = abs(input_val - self.outputs[output_device_uid].val[output_channel])
                if delta > permissable_deviation * soll_input:
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
        self.operation_mode = True

        for uid, input_dev in self.inputs.items():
            input_dev.operational = True
            delta = now - input_dev.activity_timestamp
            if delta > input_dev.timeout:
                self.operation_mode = False
                input_dev.operational = False
                print(f"timeout detected from uid {uid}, going failsafe")

    def __manage_outputs(self):
        """
        A simple function that just sets the given value, the rules and value are handled by Control classes
        """
        # @ TODO implement failsafe modes somewhere maybe here?
        for uid, output_dev in self.outputs.items():
            # @Todo: this only works for this specific device
            try:
                _ = output_dev.obj.get_enabled()
            except tinkerforge.ip_connection.Error as exp:
                print(f"connection to output {uid} - "
                      f"{device_identifier_types.get(output_dev.device_type, 'unknown device type')} has been lost")
            try:
                output_dev.obj.set_voltage(output_dev.val[0])
                # @TODO there needs to be a check on the channels and device specific fncs/class or whatever
                # output_dev.obj.set_voltage(output_dev.val[1])
            except Exception as exp:
                print(exp)

    def verify_config_devices(self):
        print("listing devices present: \n")
        # @todo define required and optional device from parsing
        """
        collects the UIDs of the connected device and checks against the listing of UIDs given from the config
        If not every required device is given an Error is given
        """
        self.conn.enumerate()
        sleep(0.2)
        # self.conn.disconnect()

        # found no obvious way to check the main connection lets throw an error when no devices are found
        if not len(self.devices_present):
            raise ConnectionError("No Tinkerforge module found, check connection to master brick")

        devices_required = set()
        channels_required = {}
        for device_key, value in self.config.items():
            print(device_key)
            # @TODO: this will become device specific at some point
            if not all(key in value for key in ("input_device", "input_channel", "output_device", "output_channel")):
                print(f"invalid config for device {device_key} due to missing parameter")
                exit()

            self.controls[device_key] = self.Control()
            input_uid = value.get("input_device")
            output_uid = value.get("output_device")
            used_input_channels = channels_required.get(input_uid, [])
            used_output_channels = channels_required.get(output_uid, [])
            req_input_chann = value.get("input_channel")
            req_output_chann = value.get("input_channel")
            if req_input_chann in used_input_channels or req_output_chann in used_output_channels:
                print(f"invalid config: {device_key} has overlapping channels with previous configured devices")
                exit()
            used_output_channels.append(req_output_chann)
            used_input_channels.append(req_input_chann)
            channels_required[input_uid] = used_input_channels
            channels_required[output_uid] = used_output_channels

            print("VALID config!")
            devices_required.add(input_uid)
            devices_required.add(output_uid)

        self.setup_devices(devices_required)

        for uid in devices_required:
            if uid not in self.devices_present:
                raise ModuleNotFoundError(f"Missing Tinkerforge Element: {uid}")
        print("\nvalid setup for configured initialisation detected \n")
        # maybe make a secondary list for optional, and then throw a warning
        # do we need a device identifier check? what happen to TF elements if we go wrong?

    def cb_enumerate(self, uid, connected_uid, _, hardware_version, firmware_version,
                     device_identifier, enumeration_type):

        # print("Enumeration Type triggered:  " + str(enumeration_type))

        # This only triggers when the master brick disconnects it seems
        if enumeration_type == IPConnection.ENUMERATION_TYPE_DISCONNECTED:
            # @Todo: device identifier is already known, catch it from devices_present
            print(f"Disconnect detected from device: {uid} - "
                  f"{device_identifier_types.get(device_identifier, 'unknown device type')}")
            return

        if uid not in self.devices_present.keys():
            self.devices_present[uid] = {"device_identifier": device_identifier, "parent_uid": connected_uid}
            print("UID:               " + uid)
            print("Connected UID:     " + connected_uid)
            # print("Position:          " + _)
            print("Hardware Version:  " + str(hardware_version))
            print("Firmware Version:  " + str(firmware_version))
            print("Device Identifier: " + str(device_identifier))
            print(device_identifier_types.get(device_identifier, "unknown"))
            print("")
        else:
            print(f"reconnect detected from device: {uid} - "
                  f"{device_identifier_types.get(device_identifier, 'unknown device type')}")
            # @Todo now reengage the devices
            self.setup_device(uid)

    def get_index(self, uid):
        return list(self.devices_present).index(uid)

    def setup_device(self, uid):
        """
        @Todo: prime candidate to be listed in a separate file
        """
        device_entry = self.devices_present.get(uid)
        if device_entry is None:
            print(f"Setup of not present device requested {uid}")
            return

        device_identifier = device_entry.get("device_identifier")
        '''
            self.obj.register_callback(self.obj.CALLBACK_TEMPERATURE, self.cb_read_t)
            self.obj.set_temperature_callback_configuration(200, False, "
        '''

        match device_identifier:
            case 2121:
                dev = self.devices_present[uid]["obj"] = BrickletIndustrialDualAnalogInV2(uid, self.conn)
                input_obj = self.InputDevice(uid, device_identifier)
                # This self needs to be an own instance
                dev.register_callback(dev.CALLBACK_ALL_VOLTAGES, input_obj.collect_inputs)
                self.inputs[uid] = input_obj
                dev.set_all_voltages_callback_configuration(500, False)
            case 2116:
                dev = self.devices_present[uid]["obj"] = BrickletIndustrialAnalogOutV2(uid, self.conn)
                dev.set_voltage(0)
                dev.set_enabled(True)
                dev.set_out_led_status_config(0, 5000, 1)
                output_obj = self.OutputDevice(uid, device_identifier, dev)
                self.outputs[uid] = output_obj
            case _:
                print(f"{uid} failed to setup device due to unkown device type {device_identifier}")
                return
        print(f"successfully setup device {uid} - "
              f"{device_identifier_types.get(device_identifier, 'unknown device type')}")

    def setup_devices(self, devices_present):
        print()
        for key in devices_present:
            self.setup_device(key)
        print()
