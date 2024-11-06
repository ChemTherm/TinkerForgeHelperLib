#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime as dt
from datetime import timedelta
from enum import IntEnum
import json
from time import sleep

from devices import Devices
from tinkerforge.ip_connection import IPConnection
from tinkerforge.ip_connection import Error as IPConnError
from threading import Thread
from control_types import Controls

import inspect
import itertools

'''
@ TODO: 🔲 ✅
 🔲 check the super init bevhiour in regards to setting a value after before super
 ✅ master brick reconnect handling 
 ✅make a listing of linked devices in case of connection loss for failsafes?
 🔲 making Inputdevice and Outputdevice based on a baseclass 
'''


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
            import config as cfg
            return cfg.config
        except ModuleNotFoundError:
            exit("no backup python config present, exiting")


class TFH:
    class OperationModes(IntEnum):
        normalMode = 0
        dummyMode = 1

    class WarningLevels(IntEnum):
        normal = 0
        failOperational = 1
        failSafe = 2
        shutdown = 4    # TBD

    class Control:
        def __init__(self):
            self.last_deviation = False

    def __init__(self, ip, port, config_name=False, debug_mode=OperationModes.normalMode):
        self.conn = IPConnection()
        self.conn.connect(ip, port)
        self.conn.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)

        self.devices_present = {}
        self.input_devices_required = set()
        self.output_devices_required = set()
        self.device_settings = {}
        self.operation_mode = debug_mode
        self.config = get_config(config_name)
        self.inputs = {}
        self.outputs = {}
        self.controls = {}
        self.verify_config_devices()

        self.run = True
        self.main_loop = Thread(target=self.__loop)
        self.main_loop.start()

    def get_brick_name(self, type_no):
        if type_no == 13:
            return "Master Brick"
        for name, obj in inspect.getmembers(Devices):
            if hasattr(obj, "__bases__") and any(_ in obj.__bases__ for _ in [Devices.InputDevice, Devices.OutputDevice]):
                if type_no == obj.device_type:
                    return name
        return "Unknown"

    def get_io_cls(self, parent_cls, device_identifier):
        """
        returns the child cls of a given device identifier, if none matches it returns None
        """
        for name, obj in inspect.getmembers(Devices):
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

            if self.operation_mode == 1 or input_device_uid is None or control_rule.get("type") == "easy_PI":
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
            if isinstance(input_dev, Devices.DummyDevice):
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

            if isinstance(output_dev, Devices.DummyDevice):
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
        for device_key, value in self.config.items():
            print(f"checking devices for {device_key}")
            type_requirements = Controls.types.get(value["type"], Controls.Entries.hasOutputs + Controls.Entries.hasInputs)
            # Überspringe externe Geräte, z.B. Modbus oder über andere Protokolle
            if "type" in value and "extern" in value["type"].lower():
                print(f"Skipping device {device_key} because its type is 'extern'")
                continue

            if type_requirements & Controls.Entries.hasOutputs:
                if not all(key in value for key in ("output_device", "output_channel")):
                    # @todo: make this optional if there is only one channel available like in a thermocouple
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

                device_setting = value.get("output_param", "default")
                if device_setting:
                    if output_uid in self.device_settings.keys():
                        self.device_settings[output_uid].append((req_output_chann, device_setting))
                    else:
                        self.device_settings[output_uid] = [(req_output_chann, device_setting)]
                self.output_devices_required.add(output_uid)

            if type_requirements & Controls.Entries.hasInputs:
                # Spezielle Behandlung für Thermoelemente
                if value["type"] == "thermocouple":
                    if "input_channel" not in value:
                        print(f"input_channel fehlt für Gerät {device_key}, wird auf 0 gesetzt")
                        value["input_channel"] = 0

                # Allgemeine Prüfung auf fehlende Parameter
                if not all(key in value for key in ("input_device", "input_channel")):
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

    def setup_device(self, uid):
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

        args = self.device_settings.get(uid)
        device_identifier = device_entry.get("device_identifier")

        try:
            old_values = self.outputs[uid].values
        except (KeyError, AttributeError):
            old_values = False

        cls = self.get_io_cls(Devices.InputDevice, device_identifier)
        if cls is not None:
            dev = self.inputs[uid] = cls(uid, self.conn, *(args,) if args is not None else ())
        else:
            cls = self.get_io_cls(Devices.OutputDevice, device_identifier)
            if cls is not None:
                dev = self.outputs[uid] = cls(uid, self.conn, *(args,) if args is not None else ())
            else:
                print(f"{uid} failed to setup device due to unknown device type {device_identifier}")
                exit()

        if old_values:
            dev.values = old_values
            
        print(f"successfully setup device {uid} - "
              f"{type(dev).__name__}")

    def setup_devices(self):
        print()
        for key in itertools.chain(self.input_devices_required, self.output_devices_required):
            self.setup_device(key)
        print()
