#!/usr/bin/env python
# Requires SMBus but uses I2C support in the kernel
from smbus import SMBus

#	ADS1115 i2C register addresses (abbreviated)
adc_address = 0x48
kConversionReg = 0
kConfigReg = 1
ADS1115_MODE_bit = 0x0100   #	bitmasks for config register fields
ADS1115_PGA_bits = 0x0E00
ADS1115_MUX_bits = 0x7000
ADS1115_OS_bit = 0x8000
ADS1115_OS_BIT_LE = 0x0080	    # little endian version
ADS1115_DR_860 = 0x00E0         # data rate values in Samples Per Second
ADS1115_GAIN_6144 = 0x0000      # +/- full scale gain ranges in mv
ADS1115_MUX_Single0 = 0x4000    # single ended channel address constants
ADS1115_MUX_Single1 = 0x5000
ADS1115_MUX_Single2 = 0x6000
ADS1115_MUX_Single3 = 0x7000
ADS1115_MODE_SingleShot = 0x0100 #mode and start bits
ADS1115_START_Single = 0x8000
ADS1115_MODE_NO_CMP = 0x0003    # value to turn off comparator!!!

#	value chosen to allow or'ing in gain value and channel without masking them
ADS1115_BASIC_CONFIG = (ADS1115_START_Single
                        | ADS1115_MODE_SingleShot 
                        | ADS1115_DR_860
                        | ADS1115_GAIN_6144
                        | ADS1115_MODE_NO_CMP)

byteswap = lambda a: ((a & 0x0FF00) >> 8) | ((a & 0x0FF) << 8)

readcommand = byteswap(ADS1115_BASIC_CONFIG)

bus = SMBus(1)

# wait for idle, then read specified single ended channel and get result
def readADC(channel):
    while not (bus.read_word_data(adc_address, kConfigReg) & ADS1115_OS_BIT_LE):
        pass
    bus.write_word_data(adc_address, kConfigReg, readcommand | ((channel + 4) << 4))
    while not (bus.read_word_data(adc_address, kConfigReg) & ADS1115_OS_BIT_LE):
        pass
    return byteswap(bus.read_word_data(adc_address, kConversionReg))

#   vswr calculation constants
kPwrCalibration = 1	    # fudge factor
cDirCoupling = 13.0	    # fractional coupler turns ratio loss factor
cDiodeDrop = 0.390	    # specified schottky diode voltage offset
cLSBSize = 0.0001875    # for lowest gain setting
cNoise = cLSBSize * 3   # ignore this much jitter

def readVSWR():
    rev_raw = (cLSBSize * readADC(0))
    fwd_raw = (cLSBSize * readADC(2))
    
    #   VSWR calculation will fail if signals are too weak
    #   but note that we ignore schottky diode offset for vswr
    fwd = (fwd_raw + cDiodeDrop) * cDirCoupling if (fwd_raw > cDiodeDrop) else 0
    rev = (rev_raw + cDiodeDrop) * cDirCoupling if (rev_raw > cDiodeDrop) else 0  
    if ((fwd_raw < cNoise) or (rev_raw < cNoise)) or (fwd_raw <= rev_raw):
        vswr = 1
    else:
        vswr = (fwd_raw + rev_raw) / (fwd_raw - rev_raw)

    #   signals below diode vf value are ignored and cannot be measured
    #   without changing turns ratio of transformers
    pwr = fwd / 1.414                     # convert to rms power at 50 ohms
    pwr = ((pwr * pwr) / 50.0) * kPwrCalibration

    return pwr, vswr

#   read the battery level and compensate for voltage divider
def readVoltage():
    return (cLSBSize * readADC(1)) * 10


#################### very simple TK UI interface

from tkinter import *
from tkinter import ttk
from time import sleep

class VSWRMeter:

    def __init__(self, root):
        root.title("Status")
        root.geometry('400x35+0+0')
        mainframe = ttk.Frame(root, padding="5 5 6 6")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        
        self.Power = StringVar()
        ttk.Label(mainframe, text="Power:").grid(column=1, row=1, sticky=W)
        ttk.Label(mainframe, textvariable=self.Power).grid(column=2, row=1, sticky=(W, E))
        
        self.VSWR = StringVar()
        ttk.Label(mainframe, text="VSWR:").grid(column=3, row=1, sticky=W)
        ttk.Label(mainframe, textvariable=self.VSWR).grid(column=4, row=1, sticky=(W, E))

        self.Batt = StringVar()
        ttk.Label(mainframe, text="Battery:").grid(column=5, row=1, sticky=W)
        ttk.Label(mainframe, textvariable=self.Batt).grid(column=6, row=1, sticky=(W, E))

        for child in mainframe.winfo_children(): 
            child.grid_configure(padx=5, pady=5)
        mainframe.focus()
        timer = root.after(200, self.calculate)
        
    def calculate(self):
        try:
            pwr,vswr = readVSWR()
            battery = readVoltage()
            self.Power.set(str(round(pwr,1)) + ' Watts')
            self.VSWR.set(str(round(vswr,2)) + ':1')
            self.Batt.set(str(round(battery,1)) + ' Volts')
            timer = root.after(200, self.calculate )
        except ValueError:
            pass

#
#   mainline code resumes here
#
root = Tk()
VSWRMeter(root)
root.mainloop()
