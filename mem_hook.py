import frida
from aobscan import aob_scan
import pymem
import pymem.ressources.kernel32 as k32
from capstone import *
import time
import numpy as np
import json
import sys
import threading
import asyncio

# REMEMBER!!! PLAYER NEEDS TO INCREASE REPLAY TICK BEFORE IT WORKS
# with open("main.js") as f:
#     js_code = f.read()

aob_pattern_match = b"\x47\x0F\x11\x64\x25\x00\x4C\x8D\xA0\xE0\x03\x00\x00\x47\x0F\x11\x5C\x25\x00"

# aob_pattern_replay = b"\x43\x0F\x10\x4C\x25\x00\x4C\x8D\xA0\xB0\x02\x00\x00\x47\x0F\x10\x7C\x25\x00\x41\x0F\x29\x8F\x10\x01\x00\x00"
aob_pattern_replay = b"\x43\x0F\x10\x4C\x25\x00\x4C\x8D\xA0\xB0\x02\x00\x00\x47\x0F\x10\x7C\x25\x00"

# aob_pattern_ticks = b"\x47\x89\x4C\x05\x00\x49\xC7\x47\x48\xEE\x38\x00\x00\x4D\x8D\x5A\x62\x41\xB9\x02\x00\x00\x00"
aob_pattern_ticks = b"\x47\x89\x4C\x05\x00\x49\xC7\x47\x48\xEE\x38"


class mem_hook:
    def __init__(self, js, js_tick, rep_mode, tick_mode, tick_addr=None, tick_instr_addr=None, x_aob_instr=None):
        global aob_pattern_match 
        global aob_pattern_replay
        global aob_pattern_ticks
        
        self.rep_mode = rep_mode
        self.tick_mode = tick_mode
        self.pm = pymem.Pymem("yuzu.exe")
        self.aob = aob_pattern_replay if rep_mode else aob_pattern_match
        if x_aob_instr != None:
            self.aob_instr = x_aob_instr
        else:
            self.aob_instr = aob_scan(self.pm, self.aob)

        self.aob_tick_instr = None
        self.check_cam = True
        self.check_tick = True
        self.frida_lock = threading.Lock()
        if not (self.aob_instr == None):
            print("[mem_hook]: AOB Pattern found at: " + str(self.aob_instr))
            self.js_script = js
            self.js_tick_script = js_tick
            
            
            self.unload_cam_script = False
            self.unload_tick_script = False

            self.frida_session = frida.attach("yuzu.exe")
            self.frida_script = self.frida_session.create_script(self.js_script)

            self.cam_check_thread = threading.Thread(target=self.script_checker_cam)
            self.cam_check_thread.start()

            self.x_addr = 0
            self.y_addr = 0
            self.z_addr = 0
            self.yaw_address = 0 # pos x + 20
            self.pitch_address = 0 # pos x + 24
            self.find_address_x()

            if tick_addr != None:
                self.tick_addr = tick_addr
            else:
                if self.rep_mode:
                    self.aob_tick_instr = aob_scan(self.pm, aob_pattern_ticks)
                    print("Tick AOB pattern found at: " + str(self.aob_tick_instr))
                    self.frida_session_tick = frida.attach("yuzu.exe")
                    self.frida_script_tick = self.frida_session_tick.create_script(self.js_tick_script)
                    self.tick_check_thread = threading.Thread(target=self.script_checker_tick)
                    self.tick_check_thread.start()
                    if not (self.aob_tick_instr == None):
                        print("Tick instruction found at: " + str(self.aob_tick_instr))
                        self.find_address_tick()
                        # exit()
                    else:
                        print("AOB tick scan failed.")
        else:
            print("AOB scan failed.")

    def on_message(self, message, data):
        with self.frida_lock:
            print("Message received: ")
            print(json.dumps(message, indent=2))
            try:
                if (message['type'] == 'send'):
                    if (message['payload'])[0:2] == "M:":
                        print("X Address found, detatching session")
                        self.unload_cam_script = True
                        xAddr = (message['payload'])[2:]
                        print("xAddr:" + str(xAddr))
                        print(str(self.pm.read_float(int(xAddr, 0))))
                        self.set_coords_addr(xAddr)
            except Exception as e:
                print("[on_message] Exception Caught: " + str(e))
    
    def on_message_tick(self, message, data):
        with self.frida_lock:
            print("[on_message_tick]")
            print(json.dumps(message, indent=2))
            try:
                if (message['type'] == 'send'):
                    if (message['payload'])[0:2] == "T:":
                        self.unload_tick_script = True
                        tickAddr = (message['payload'])[2:]
                        print("tickAddr:" + str(tickAddr))
                        print(str(self.pm.read_int(int(tickAddr, 0))))
                        self.set_tick_addr(tickAddr)
            except Exception as e:
                print(e)

    def find_address_x(self):
        self.frida_script.on("message", self.on_message)
        self.frida_script.load()
        time.sleep(0.5)
        self.frida_script.post({"type":"config", "payload": self.aob_instr})


    def set_tick_addr(self, addr):
        print("[set_tick_addr]: ")
        self.tick_addr = int(addr, 0)
    
    def read_tick(self):
        try:
            if self.aob_tick_instr != 0:
                return self.pm.read_int(self.tick_addr)
        except Exception as e:
            pass
            # print(e)

    def find_address_tick(self):
        print("[find_address_tick] :")
        self.frida_script_tick.on("message", self.on_message_tick)
        self.frida_script_tick.load()
        time.sleep(0.5)
        self.frida_script_tick.post({"type":"config", "payload": str(self.aob_tick_instr)})
        print("[find_address_tick] : end")
        
    def set_coords_addr(self, x):
        print("[set_x] :")
        self.x_addr = int(x, 0)
        self.y_addr = self.x_addr + 4
        self.z_addr = self.x_addr + 36
        self.pitch_address = self.x_addr + (20 if not self.rep_mode else 16) 
        self.yaw_address = self.x_addr + (24 if not self.rep_mode else 20)
        self.check_cam = False
        print("X address found at: " + str(self.x_addr))
        print("Camera position: " + str(self.read_xyz()))
    

    def write_xyz(self, x, y, z):
        self.pm.write_float(self.x_addr, x)
        self.pm.write_float(self.y_addr, y)
        self.pm.write_float(self.z_addr, z)
    
    def write_py(self, p, y):
        self.pm.write_float(self.pitch_address, p)
        self.pm.write_float(self.yaw_address, y)

    def read_xyz(self):
        return [
            self.pm.read_float(self.x_addr),
            self.pm.read_float(self.y_addr),
            self.pm.read_float(self.z_addr)
        ]
    
    def read_py(self):
        return [
            self.pm.read_float(self.pitch_address),
            self.pm.read_float(self.yaw_address)
        ]
    
    def input_loop():
        while True:
            inp = input()

    def script_checker_cam(self):
        while self.check_cam:
            # print("Cam checker")
            if self.unload_cam_script:
                with self.frida_lock:
                    print("Detatching Cam Script")
                    try:
                        self.frida_script.unload()
                        self.frida_session.detach()
                        self.frida_session = None
                        self.check_cam = False
                    except Exception as e:
                        print(e)
            time.sleep(0.5)
    
    def script_checker_tick(self):
        while self.check_tick:
            # print("Tick checker")
            if self.unload_tick_script:
                with self.frida_lock:
                    print("Detatching Tick Script")
                    try:
                        self.frida_script_tick.unload()
                        self.frida_session_tick.detach()
                        self.frida_session_tick = None
                        self.check_tick = False
                    except Exception as e:
                        print(e)
            time.sleep(0.5)
    
    def get_tick_instr_and_addr(self):
        try:
            self.frida_script = None
            self.frida_session = None
        except Exception as e:
            print(e)

        self.frida_session = None
        self.frida_session_tick = None
        time.sleep(0.5)
        return self.tick_addr
    
    def detatch_all(self):
        try:
            self.frida_session.detach()
            self.frida_session_tick.detach()
        except Exception as e:
            print(e)
        
    def reload_cam(self):
        try:
            if hasattr(self, 'frida_session'):
                self.frida_script.unload()
                self.frida_session.detach()
                self.frida_script = None 
                self.frida_session = None
        except Exception as e:
            print(e)

        self.unload_cam_script = False
        self.check_cam = True

        self.aob_instr = aob_scan(self.pm, self.aob)
        self.unload_cam_script = False
        self.unload_tick_script = False

        self.frida_session = frida.attach("yuzu.exe")
        self.frida_script = self.frida_session.create_script(self.js_script)
        self.x_addr = 0
        self.y_addr = 0
        self.z_addr = 0
        self.yaw_address = 0 # pos x + 20
        self.pitch_address = 0 # pos x + 24
        self.find_address_x()

    def get_aob_addr(self):
        return self.aob_instr
        




    


        
    