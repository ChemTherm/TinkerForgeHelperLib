#!/usr/bin/env python
# -*- coding: utf-8 -*-
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter.filedialog import asksaveasfilename
from datetime import datetime, timedelta
import time

save_timer = time.time()


def setdata(device_list, entry_list):
    
    hp_list = device_list['HP']
    mfc_list = device_list['MFC']
    T_entries = entry_list['T']
    MFC_entries = entry_list['MFC']
    
    for index, hp_instance in enumerate(hp_list):
        offset = 0 if index < 4 else  4
        if T_entries[index-offset].get() != '':
            hp_instance.set_t_soll(float(T_entries[index-offset].get()))
            
    for index, mfc_instance in enumerate(mfc_list):
        if MFC_entries[index].get() != '':
            mfc_instance.set(float(MFC_entries[index].get()))

def setup_gui(config, img):
    window = ctk.CTk()
    ctk.set_appearance_mode("light")
    scrW = window.winfo_screenwidth()
    scrH = window.winfo_screenheight()
    scrW = 1100
    scrH = 700
    window.geometry(f"{scrW}x{scrH}")
    window.title(config['CONTROL']['Name'])
    window.configure(bg=config['TKINTER']['background-color'])
   # window.attributes('-fullscreen', True)    

    bg_image = ctk.CTkImage(Image.open(img['Background']['name']), size=(int(img['Background']['width']), int(img['Background']['height'])))
    label_background = ctk.CTkLabel(window, image=bg_image, text="")
    label_background.place(x=img['Background']['x'], y=img['Background']['y'])
    label_background.lower()

    
    #----------- Frames ----------
    frames ={}
    frames['control'] = ctk.CTkFrame(window, fg_color = config['TKINTER']['background-color'], border_color = config['TKINTER']['border-color'], border_width=5)
    frames['control'].grid(column=0, row=1, padx=20, pady=20, ipadx = 20, ipady = 15)

    name_Frame = ctk.CTkLabel( frames['control'], font = ('Arial',20), text='Steuerung')
    name_Frame.grid(column=0, columnspan =2, row=0, ipadx=7, ipady=7, pady =7, padx = 7, sticky = "E")
    
    frames['mfc']=ctk.CTkFrame(window, fg_color = config['TKINTER']['background-color'], border_color = config['TKINTER']['border-color'], border_width=5)
    frames['mfc'].grid(column=0, row=3, padx=20, pady=20, ipadx = 20, ipady = 15)

    return window, frames

def create_tc_labels(window, tc_list, img):
    labels = {}
    x_offset = img['Background']['x']
    y_offset = img['Background']['y']
    for i, tc_instance in enumerate(tc_list):
        labels[i] = ctk.CTkLabel(window, font=('Arial', 16), text='0 °C')
        labels[i].place(x=x_offset + img['T-Reaktor']['x'][i], y=y_offset + img['T-Reaktor']['y'][i])
    return labels

def create_p_labels(window, pressure_list, config):
    labels = {}
    for i, pressure_instance in enumerate(pressure_list):
        labels[i] = ctk.CTkLabel(window, font=('Arial', 16), text='0 mV')
        labels[i].place(x = config['Pressure']['x'][i], y = config['Pressure']['y'][i])
    return labels

def create_hp_labels(window, hp_list, img):
    labels = {}
    x_offset = img['Background']['x']
    y_offset = img['Background']['y']
    for i, hp_instance in enumerate(hp_list):
        labels[i] = ctk.CTkLabel(window, font=('Arial', 16), text='0 %')
        labels[i].place(x=x_offset -1 + img['T-Reaktor']['x'][i], y=y_offset +20 + img['T-Reaktor']['y'][i])
    return labels

def create_ABB_labels(window, ABB_list, frames, config):
    labels = {}
    name_Frame = ctk.CTkLabel( frames['ABB'], font = ('Arial',20), text='ABB Gasanalyse')
    name_Frame.grid(column=0, columnspan =3, row=0, ipadx=7, ipady=7, pady =7, padx = 7, sticky = "E")
    
    name={}; 

    for i, ABB_instance in enumerate(ABB_list):
        name[i]= ctk.CTkLabel( frames['ABB'], font = ('Arial',16), text=config['ABB']['name'][i])
        name[i].grid(column=1, row=i+1, ipadx=5, ipady=7)

        labels[i] = ctk.CTkLabel(frames['ABB'], font = ('Arial',16), text='0 mA')
        labels[i].grid(column=3, row=i+1, ipadx=7, ipady=7)
    return labels

def create_mfc_labels(window, mfc_list, frames, config):
    labels = {}
    name_Frame = ctk.CTkLabel( frames['mfc'], font = ('Arial',20), text='MFC Steuerung')
    name_Frame.grid(column=0, columnspan =3, row=0, ipadx=7, ipady=7, pady =7, padx = 7, sticky = "E")
    
    name_MFC={};  unit_MFC={}; 

    for i, mfc_instance in enumerate(mfc_list):
        name_MFC[i]= ctk.CTkLabel( frames['mfc'], font = ('Arial',16), text=config['MFC']['name'][i])
        name_MFC[i].grid(column=1, row=i+1, ipadx=5, ipady=7)
        
        unit_MFC[i]= ctk.CTkLabel( frames['mfc'], font = ('Arial',16), text=' mV')
        unit_MFC[i].grid(column=3, row=i+1, ipadx=1, ipady=7)
        if mfc_instance.m > 0:
            unit_MFC[i].configure(text= mfc_instance.unit )

        labels[i] = ctk.CTkLabel(frames['mfc'], font = ('Arial',16), text='0 mV')
        labels[i].grid(column=4, row=i+1, ipadx=7, ipady=7)
    return labels


def create_set_temperature_entries(window, img, x_offset, y_offset):
    entries = {}
    for i in range(1):
        entries[i] = tk.Entry(window, font=('Arial', 16), width=6, bg='light blue')
        entries[i].place(x=x_offset + img['T-Set']['x'][i], y=y_offset + img['T-Set']['y'][i])
    return entries

def create_set_mfc_entries(window, mfc_list, frames):
    entries = {}
    for i, hp_instance in enumerate(mfc_list):
        entries[i] = tk.Entry(frames['mfc'], font=('Arial', 16), width=6, bg='light blue')
        entries[i].grid(column=2, row=i+1, ipadx=0, ipady=7)
    return entries

def getfile(entry_list, label_list):
    entry_list['File'] = asksaveasfilename(defaultextension = ".dat", initialdir= "D:/Daten/")
    label_list['Save'].configure(text=entry_list['File'])

def setup_frames_labels_buttons(window, frames, img, device_list, entry_list, label_list):
    
    save_switch =  ctk.CTkSwitch(frames['control'], font=('Arial', 16), text="Speichern")
    save_switch.grid(column=2, row=2, ipadx=7, ipady=7)
    
    label_list['Save'] = ctk.CTkLabel(frames['control'], font = ('Arial',16), text=entry_list['File'])
    label_list['Save'].grid(column=0, columnspan = 4, row=3, ipadx=7, ipady=7)
    
    get_filename = ctk.CTkButton(frames['control'], text = 'Data File', command = lambda: getfile(entry_list, label_list), fg_color = 'brown')
    get_filename.grid(column= 3, row = 2, ipadx=7, ipady=7)

    set_button = ctk.CTkButton(frames['control'],text='Set Values', command = lambda: setdata(device_list, entry_list), fg_color = 'brown')
    set_button.grid(column=0 ,columnspan = 3, row=1, ipadx=8, ipady=8, padx = 7, pady = 7) 

    close_img = ctk.CTkImage(Image.open(img['Close']['name']), size=(80, 80))
    exit_button = ctk.CTkButton(master = window, text="", command=window.destroy, fg_color='transparent', hover_color='#F2F2F2', image=close_img)
    exit_button.place(x=img['Close']['x'], y=img['Close']['y'])
    
    return  save_switch 

def save_values(device_list, label_list, entry_list):
    tc_list = device_list['T']
    hp_list = device_list['HP']
    mfc_list = device_list['MFC']
    ABB_list = device_list['ABB']
    pressure_list = device_list['P']

    with open(entry_list['File'], 'a') as f:
        line = ' ' + datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f ")+ '\t'
        for index, tc_instance in enumerate(tc_list):
            line += str(tc_instance.t) + '\t'
        for index, hp_instance in enumerate(hp_list):
            line += str(hp_instance.pwroutput) + '\t'
        for index, mfc_instance in enumerate(mfc_list):
            if mfc_instance.m > 0:
                line += str(entry_list['MFC'][index].get()) + ' \t '+ str(mfc_instance.value) + ' \t '
            else:
                line += str(entry_list['MFC'][index].get()) + ' \t '+ str(mfc_instance.Voltage) + ' \t '
        for index, pressure_instance in enumerate(pressure_list):
            if pressure_instance.m > 0:
                line += str(pressure_instance.current) + '\t'
            else:
                line += str(pressure_instance.value) + '\t'
        line += ' \n'
        f.writelines(line)

def tk_loop(window, device_list, label_list, entry_list) :
    global save_timer
    
    label_T_ist = label_list['T']
    tc_list = device_list['T']
    label_HP_ist = label_list['HP']
    hp_list = device_list['HP']
    label_MFC = label_list['MFC']
    mfc_list = device_list['MFC']
    save_switch = entry_list['Save']
    pressure_list = device_list['P']
    label_pressure = label_list['P']


    for index, tc_instance in enumerate(tc_list):
        label_T_ist[index].configure(text=f"{round(tc_instance.t, 2)} °C")

    for index, hp_instance in enumerate(hp_list):
        label_HP_ist[index].configure(text=f"{round(hp_instance.pwroutput * 100, 2)} %")
        hp_instance.regeln()


    for index, pressure_instance in enumerate(pressure_list):
        pressure_instance.get()
        label_pressure[index].configure(text=f"{round(pressure_instance.current, 2)} mV")
        if pressure_instance.m > 0:
            label_pressure[index].configure(text=f"{round(pressure_instance.value, 2)} " + pressure_instance.unit )

    for index, mfc_instance in enumerate(mfc_list):
        mfc_instance.get()
        label_MFC[index].configure(text=f"{round(mfc_instance.Voltage, 2)} mV")
        if mfc_instance.m > 0:
            label_MFC[index].configure(text=f"{round(mfc_instance.value, 2)} " + mfc_instance.unit )

    if save_switch.get() == 1 and save_timer - time.time()< 0:
        save_values(device_list, label_list, entry_list)
        save_timer = time.time() + 1000/1000
    


    window.after(50, tk_loop, window, device_list, label_list, entry_list) 

