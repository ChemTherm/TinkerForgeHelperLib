#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import tinkerforge as tf

from tinkerforge.bricklet_thermocouple_v2 import BrickletThermocoupleV2
from tinkerforge.bricklet_industrial_digital_out_4_v2 import BrickletIndustrialDigitalOut4V2
from tinkerforge.bricklet_industrial_analog_out_v2 import BrickletIndustrialAnalogOutV2
from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3
from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3
from tinkerforge.bricklet_industrial_dual_analog_in_v2 import BrickletIndustrialDualAnalogInV2
from tinkerforge.bricklet_industrial_dual_0_20ma_v2 import BrickletIndustrialDual020mAV2

from time import sleep

# unused imports just keeping them around for now

# from tinkerforge.bricklet_industrial_dual_relay import BrickletIndustrialDualRelay
# import tkinter as tk
# from PIL import Image,ImageTk
# import time
from tinkerforge.ip_connection import IPConnection

device_identifier_types = {
    13: "Master Brick",
    2121: "Industrial Dual Analog In Bricklet 2.0",
    2116: "Industrial Analog Out Bricklet 2.0",
}


class TFH:

    #	Industrial Analog Out Bricklet 2.0     2116  25si
    #   Industrial Dual Analog In Bricklet 2.0 2121  23Uf

    def __init__(self, ip, port, config: dict, debug=False):
        self.conn = IPConnection()
        self.conn.connect(ip, port)
        self.conn.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)
        self.devices_present = {}
        self.debugMode = debug
        self.config = config
        self.verify_config_devices()
        self.test_vals = 1

    def verify_config_devices(self):
        print("verify devices")
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

        # devices_required = ["25si", "23Uf"]
        devices_required = ["Yee", "27A7"]
        if len(self.config):
            print("this is work in progress, first implemting automatic setup for basic MFCs")
            exit()
            # for device in self.config.get()
        for uid in devices_required:
            if uid not in self.devices_present:
                raise ModuleNotFoundError("Missing Tinkerforge Element")

        # maybe make a secondary list for optional, and then throw a warning
        # do we need a device identifier check? what happen to TF elements if we go wrong?

    def cb_enumerate(self, uid, connected_uid, _, hardware_version, firmware_version,
                     device_identifier, enumeration_type):

        # print("Enumeration Type:  " + str(enumeration_type))

        if enumeration_type == IPConnection.ENUMERATION_TYPE_DISCONNECTED:
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

    def setup_devices(self):
        for key, value in self.config:
            print()


# ‼️ there is no passing of arguments here
def setup_devices(config, ipcon):
    ABB_list = {}
    do_list = [BrickletIndustrialDigitalOut4V2(UID, ipcon) for UID in config['CONTROL']['DigitalOut']]
    dual_AI_list = [TF_IndustrialDualAnalogIn(UID, ipcon) for UID in config['CONTROL']['DualAnalogIn']]
    dual_AI_mA_list = [TF_IndustrialDualAnalogIn_mA(UID, ipcon) for UID in config['CONTROL']['DualAnalogIn4-20']]

    # unused
    # pressure_list = {}
    # module_list = {'DO': do_list, 'Dual-AI': dual_AI_list, 'Dual-AImA': dual_AI_mA_list}
    device_list = {}

    tc_list = []

    for device_name in ['Tc-R', 'TcExtra']:
        for UID in config['CONTROL'][device_name]:
            try:
                tc = Tc(ipcon, UID, typ='N')
                tc_list.append(tc)
            except tf.ip_connection.Error as err:
                print(f"TC timed out: {err}")
                pass
    device_list['T'] = tc_list

    # ❗ only if get all the defined TCs here can we iterate the tc_list
    """
    hp_list = [regler(do_list[i_DO], config['CONTROL']['Tc-DO_channel'][i_Tc], tc_list[i_Tc])
               for i_DO, DO_UID in enumerate(config['CONTROL']['DigitalOut'])
               for i_Tc, tc_UID in enumerate(config['CONTROL']['Tc-R']) if config['CONTROL']['Tc-DO_index'][i_Tc] == i_DO]
    [hp.start(-300) for hp in hp_list]
    device_list['HP'] = hp_list
    """

    mfc_list = [MFC(ipcon, config['CONTROL']['AnalogOut'][config['MFC']['AnalogOut_index'][i]],
                    dual_AI_list[config['MFC']['DualAnalogIn_index'][i]], config['MFC']['DualAnalogIn_channel'][i]) for
                i in range(config['MFC']['amount'])]
    [mfc.config(config['MFC']['gradient'][index], config['MFC']['y-axis'][index], config['MFC']['unit'][index]) for
     index, mfc in enumerate(mfc_list)]

    pressure_list = [AI_mA(dual_AI_mA_list[config['Pressure']['DualAnalogInmA_index'][i]],
                           config['Pressure']['DualAnalogInmA_channel'][i]) for i in
                     range(config['Pressure']['amount'])]
    [psc.config(config['Pressure']['gradient'][index], config['Pressure']['y-axis'][index],
                config['Pressure']['unit'][index]) for index, psc in enumerate(pressure_list)]

    device_list = {'MFC': mfc_list, 'P': pressure_list, 'ABB': ABB_list}
    return device_list


class regler:
    t_soll = 0
    ki = 0.000013
    kp = 0.018
    i = 0
    time_last_call = datetime.now()
    pwroutput = 0

    def __init__(self, ido_handle, channel, tc_handle, frequency=10) -> None:
        self.running = False
        self.tc = tc_handle
        self.channel = channel
        self.ido = ido_handle
        self.frequency = frequency
        self.ido.set_pwm_configuration(channel, self.frequency, 0)

    def config(self, ki, kp):
        self.ki = ki
        self.kp = kp

    def start(self, t_soll):
        self.t_soll = t_soll
        self.running = True
        self.time_last_call = datetime.now()

    def stop(self):
        self.running = False
        self.regeln()

    def set_t_soll(self, t_soll):
        self.t_soll = t_soll

    def regeln(self):
        if self.running:
            dT = self.t_soll - self.tc.t
            p = self.kp * dT
            now = datetime.now()
            dtime = (now - self.time_last_call).total_seconds()
            self.time_last_call = now
            self.i = self.i + dT * self.ki * dtime

            pi = p + self.i
            if pi > 1:
                pi = 1
                self.i = pi - p
            elif pi < 0:
                pi = 0
            if self.i < 0:
                self.i = 0
            duty = 10000 * pi
            self.pwroutput = duty / 10000
            self.ido.set_pwm_configuration(self.channel, self.frequency, duty)
            # print(self.channel)
            # print("duty = " + str(duty))
            # print("pi = " + str(pi))
        else:
            duty = 0
            self.ido.set_pwm_configuration(self.channel, self.frequency, duty)


class Tc:

    def __init__(self, ipcon, ID, typ='K') -> None:
        self.t = -300
        self.UID = ID
        self.obj = BrickletThermocoupleV2(ID, ipcon)

        type_dict = {'B': 0, 'E': 1, 'J': 2, 'K': 3, 'N': 4, 'R': 5, 'S': 6, 'T': 7}

        thermocouple_type = type_dict[typ]
        self.obj.set_configuration(16, thermocouple_type, 0)
        # 🔳 integrate to init unless there is a need for multiple excepts
        self.start()

    def start(self):
        self.obj.register_callback(self.obj.CALLBACK_TEMPERATURE, self.cb_read_t)
        self.obj.set_temperature_callback_configuration(200, False, "x", 0, 0)

    def cb_read_t(self, temperature):
        # print("Temperature: " + str(temperature/100.0) + " °C")
        # print(self.UID)

        if temperature < 0:
            temperature = 200000
        self.t = temperature / 100


class Pressure:
    def __init__(self, obj_in, channel) -> None:
        self.obj = obj_in
        self.channel = channel
        self.config(0, 0, 'None')

    def config(self, m, y, unit):
        self.m = m  # Steigung
        self.y = y  # Achsenabschnitt
        self.unit = unit

    def get(self):
        # self.Voltage = self.obj.Voltage[self.channel]
        self.obj.get_voltages(self.obj)
        self.Voltage = self.obj.Voltage[self.channel]
        if self.m > 0:
            self.value = (self.Voltage - self.y) * self.m


class AI_mA:
    def __init__(self, obj_in, channel) -> None:
        self.obj = obj_in
        self.channel = channel
        self.config(0, 0, 'None')

    def config(self, m, y, unit):
        self.m = m  # Steigung
        self.y = y  # Achsenabschnitt
        self.unit = unit

    def get(self):
        self.obj.get_current(self.obj)
        self.current = self.obj.current[self.channel]
        if self.m > 0:
            self.value = (self.current - self.y) * self.m


class TF_IndustrialDualAnalogIn:
    # ❓❓❓ not sure what happens here, trace why we pass an object to getcurrent otherwise do something sensible
    Voltage = [0, 0]

    # def cb_voltage(self,voltages):
    # self.Voltage[0] = voltages[0]/1000.0
    # self.Voltage[1] = voltages[1]/1000.0

    def __init__(self, ID_in, ipcon) -> None:
        self.obj = BrickletIndustrialDualAnalogInV2(ID_in, ipcon)
        self.ID = ID_in
        # self.start()

    # def start(self):
    # self.obj.register_callback(self.obj.CALLBACK_ALL_VOLTAGES, self.cb_voltage)
    # self.obj.set_all_voltages_callback_configuration(500, False)

    def get_voltages(self, TF_obj):
        self.Voltage = TF_obj.obj.get_all_voltages()


class TF_IndustrialDualAnalogIn_mA:
    # ❓❓❓ not sure what happens here, trace why we pass an object to getcurrent otherwise do something sensible
    current = [0, 0]

    def __init__(self, ID_in, ipcon) -> None:
        self.obj = BrickletIndustrialDual020mAV2(ID_in, ipcon)

    def get_current(self, TF_obj):
        self.current[0] = TF_obj.obj.get_current(0)
        self.current[1] = TF_obj.obj.get_current(1)


class MFC:
    def __init__(self, ipcon, ID_out, obj_in, channel) -> None:
        self.UID = ID_out
        self.Aout = BrickletIndustrialAnalogOutV2(ID_out, ipcon)
        self.Aout.set_voltage(0)
        self.Aout.set_enabled(True)
        self.Aout.set_out_led_status_config(0, 5000, 1)
        self.obj = obj_in
        self.channel = channel
        self.config(0, 0, 'None')

    def get(self):
        # self.Voltage = self.obj.Voltage[self.channel]
        self.obj.get_voltages(self.obj)
        self.Voltage = self.obj.Voltage[self.channel]
        self.value = 0
        if self.m > 0:
            self.value = (self.Voltage - self.y) * self.m

    def config(self, m, y, unit):
        self.m = m  # Steigung
        self.y = y  # Achsenabschnitt
        self.unit = unit

    def set(self, value):
        if self.m > 0:
            value = value / self.m + self.y
        self.Aout.set_voltage(value)

    def stop(self):
        self.Aout.set_voltage(0)
        self.Aout.set_enabled(False)


class MFC_AIO_30:
    def __init__(self, ipcon, ID_out, ID_in) -> None:
        self.UID = ID_out
        self.Aout = BrickletAnalogOutV3(ID_out, ipcon)
        self.Aout.set_output_voltage(0)
        self.Ain = BrickletAnalogInV3(ID_in, ipcon)  # Create device object
        self.Ain.register_callback(self.Ain.CALLBACK_VOLTAGE, self.cb_voltage)
        self.Ain.set_voltage_callback_configuration(1000, False, "x", 0, 0)

    def cb_voltage(self, voltage):
        self.voltage = voltage / 1000.0

    def get(self):
        self.Voltage = self.voltage

    def set(self, value):
        self.Aout.set_output_voltage(value)

    def stop(self):
        self.Aout.set_output_voltage(0)
        self.Aout.set_enabled(False)
