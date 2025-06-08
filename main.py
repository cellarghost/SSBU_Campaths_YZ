from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
import glfw
import imgui
import sys
import asyncio
import mem_hook
import time
from datetime import datetime
import json
from tkinter import filedialog

import numpy as np
from scipy.interpolate import UnivariateSpline, interp1d

def interpolate_axis(list_x, list_y=None):
    if list_y == None:
        list_y = []
        i = 0
        for x in list_x:
            list_y.append(i)
            i += 0.1
    
    spline = interp1d(list_y, list_x, kind='quadratic')

    return spline

# def return_increment(splines):


with open("main.js") as f:
    js_code = f.read()

with open("tick.js") as f:
        js_code_tick = f.read()

aob_pattern = b"\x47\x0F\x11\x64\x25\x00\x4C\x8D\xA0\xE0\x03\x00\x00\x47\x0F\x11\x5C\x25\x00"
keyframes=[]
path_speed = 1
ssbu_hook = None
replay_mode = True
tick_mode = False
tick_sync = False
selected_keyframe = None
warnings = []

def generate_splines():
    global keyframes
    global ssbu_hook
    global tick_mode
    global warnings

    try:
        x_points = []
        y_points = []
        z_points = []
        pitch_points = []
        yaw_points = []
        tilt_points = []
        zoom_points = []
        ticks = [] if tick_mode else None
        
        base_tick = keyframes[0]['tick']

        for keyframe in keyframes:
            pos = keyframe["pos"]

            x_points.append(pos[0])
            y_points.append(pos[1])
            z_points.append(pos[2])

            rot = keyframe["rot"]

            pitch_points.append(rot[0])
            yaw_points.append(rot[1])
            tilt_points.append(rot[2])

            zoom = keyframe["fov"]

            zoom_points.append(zoom)

            ticks.append(keyframe["tick"] - base_tick)
        
        print(x_points)

        path_end = (0.25 * len(x_points)) if not tick_mode else (keyframes[-1]['tick'] - base_tick)
        
        return [ # returns smoothed splines and path end
            interpolate_axis(x_points, ticks),
            interpolate_axis(y_points, ticks),
            interpolate_axis(z_points, ticks),
            interpolate_axis(pitch_points, ticks),
            interpolate_axis(yaw_points, ticks),
            interpolate_axis(tilt_points, ticks),
            interpolate_axis(zoom_points, ticks),
            path_end
        ]


    except Exception as e:
        print('[generate splines] : ' + str(e))


async def play_campath():
    try:
        x_spline, y_spline, z_spline, pitch_spline, yaw_spline, tilt_spline, zoom_spline, path_end = generate_splines()

        progress = 0
        print(path_end)
        while progress < (path_end):
            # print("writing cam coordinates")
            ssbu_hook.write_xyz(float(x_spline(progress)), float(y_spline(progress)), float(z_spline(progress)))
            ssbu_hook.write_pyt(float(pitch_spline(progress)), float(yaw_spline(progress)), float(tilt_spline(progress)))
            ssbu_hook.write_zoom(float(zoom_spline(progress)))
            progress += 0.001 if not tick_mode else 1
            time.sleep(0.008 if not tick_mode else 0.016)
            print(str(progress) + "-->" + str(path_end))
            # print(progress)
        ssbu_hook.write_xyz(0, 0, -100)
        ssbu_hook.write_pyt(0, 0, 0)
        ssbu_hook.write_zoom(70)
    
    except Exception as e:
        print('[play_campath] : ' + str(e))
    
async def play_campath_sync():
    global tick_sync
    tick_sync = True
    try: 
        x_spline, y_spline, z_spline, pitch_spline, yaw_spline, tilt_spline, zoom_spline, path_end = generate_splines()
        global keyframes 
        global ssbu_hook
        base_tick = keyframes[0]['tick']
        previous_tick = 0
        while tick_sync:
            current_tick = ssbu_hook.read_tick()
            if current_tick != previous_tick:
                print(current_tick)
            if current_tick >= base_tick:
                if current_tick > (path_end + base_tick):
                    tick_sync = False 
                else:
                    progress = current_tick - base_tick
                    ssbu_hook.write_xyz(float(x_spline(progress)), float(y_spline(progress)), float(z_spline(progress)))
                    ssbu_hook.write_pyt(float(pitch_spline(progress)), float(yaw_spline(progress)), float(tilt_spline(progress)))
                    ssbu_hook.write_zoom(float(zoom_spline(progress)))
            time.sleep(0.01666)
            previous_tick = current_tick
    except Exception as e:
        print(e)

def main():

    global keyframes
    global ssbu_hook
    global tick_mode
    global tick_sync

    imgui.create_context()
    window = impl_glfw_init()
    impl = GlfwRenderer(window)

    show_custom_window = True

    while not glfw.window_should_close(window):
        glfw.poll_events()
        impl.process_inputs()

        imgui.new_frame()

        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(360, 720)

        if show_custom_window:
            is_expand, show_custom_window = imgui.begin("SSBU Campaths", True,
            flags=imgui.WINDOW_NO_MOVE |
                imgui.WINDOW_NO_TITLE_BAR |
                imgui.WINDOW_NO_RESIZE
            )

            if is_expand:
                imgui.text("SSBU Campath Creator")

        if ssbu_hook == None:
            imgui.text("Select mode:")

            if imgui.button("Replay Mode"):
                print("Entering replay mode:")
                ssbu_hook = mem_hook.mem_hook(js_code, js_code_tick, True, tick_mode)

            changed, tick_mode = imgui.checkbox("Enable Tick Mode", tick_mode)
                # tick_mode = not tick_mode

            if imgui.button("Match mode"):
                ssbu_hook = mem_hook.mem_hook(js_code, False, False)

            imgui.end()
            
            gl.glClearColor(0.0, 0.0, 0.0, 1)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

            imgui.render()
            impl.render(imgui.get_draw_data())
            glfw.swap_buffers(window)
            continue
        
        # Runs after AOB Injection:
        
        def mode_repl_tick():

            global keyframes
            global selected_keyframe
            global ssbu_hook
            global tick_mode
            global tick_sync
            global warnings

            if imgui.button("Add Keyframe"):
                if replay_mode:
                    current_tick = ssbu_hook.read_tick()
                    if current_tick == None:
                        warnings.append(datetime.now().strftime("%H:%M:%S") + ":: Keyframe not added: Tick value is None. Try unpausing/moving forward in the replay.")
                    elif len(keyframes) > 0:
                        if keyframes[-1]['tick'] == current_tick:
                            warnings.append(datetime.now().strftime("%H:%M:%S") + ":: Keyframe not added: Cannot add two keyframes at the same tick.")
                keyframe = {"pos": ssbu_hook.read_xyz(),
                        "rot": ssbu_hook.read_pyt(),
                        "tick": ssbu_hook.read_tick(),
                        "fov": ssbu_hook.read_zoom(),
                        "name": "Keyframe " + str(len(keyframes))
                        }
                print("Keyframe Added :: " + str(keyframe))
                keyframes.append(keyframe)

            imgui.same_line()
            try:
                if imgui.button("Remove Keyframe"):
                    if not (selected_keyframe == None):
                        print(selected_keyframe)
                        print(keyframes)
                        keyframes.pop(selected_keyframe)
            except:
                pass
            
            imgui.begin_child("Keyframes", height=200, border=True)
            i = 0
            for keyframe in keyframes:
                row_clicked, _ = imgui.selectable(str(keyframe["name"]), False if (i != selected_keyframe) else True)
                if row_clicked:
                    selected_keyframe = i
                i += 1
            
            imgui.end_child()

            imgui.begin_child("SaveBox", height=50, border=True)

            if imgui.button("Export Keyframes"):
                JSONfile = json.dumps(keyframes, indent=4)
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".JSON",  
                    filetypes=[("JSON (JavaScript Object Notation)", "*.json"), ("All files", "*.*")],
                    title="Save As"
                )
                if file_path: 
                    with open(file_path, 'w') as file:
                        file.write(str(JSONfile))
            
            imgui.same_line()

            if imgui.button("Import Keyframes"):
                file_path = filedialog.askopenfilename(
                    defaultextension=".JSON", 
                    filetypes=[("JSON (JavaScript Object Notation)", "*.json"), ("All files", "*.*")],
                    title="Open"
                )
                if file_path:  
                    with open(file_path, 'r') as file:
                        keyframes = json.load(file)
                        print(keyframes)

            imgui.end_child()

            imgui.begin_child("WarningBox", height=100, border=True)

            imgui.text("Warnings")
            for warning in warnings:
                imgui.text_wrapped(warning)

            imgui.end_child()

            if imgui.button("Preview Campath"):
                asyncio.run(play_campath())
            
            if imgui.button("Clear Keyframes"):
                keyframes = []
            
            imgui.text("Current tick: " + str(ssbu_hook.read_tick()))
            
            if imgui.button("Play in sync"):
                asyncio.run(play_campath_sync())
            if imgui.button("Stop syncing"):
                tick_sync = False
            if imgui.button("Relocate Camera"):
                x_aob = ssbu_hook.get_aob_addr()
                tick_addr = ssbu_hook.get_tick_instr_and_addr()

                print(tick_addr)
                ssbu_hook = None
                time.sleep(1)
                ssbu_hook = mem_hook.mem_hook(js_code, js_code_tick, True, tick_mode, tick_addr=tick_addr, x_aob_instr=x_aob)
                # ssbu_hook = mem_hook.mem_hook(js_code, js_code_tick, True, tick_mode)

        mode_repl_tick()

        imgui.end()
        
        gl.glClearColor(0.0, 0.0, 0.0, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        imgui.render()
        impl.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.terminate()


def impl_glfw_init():
    width, height = 360, 720
    window_name = "SSBU Campaths"

    if not glfw.init():
        print("Could not initialize OpenGL context")
        sys.exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)

    window = glfw.create_window(int(width), int(height), window_name, None, None)
    glfw.make_context_current(window)

    if not window:
        glfw.terminate()
        print("Could not initialize Window")
        sys.exit(1)

    return window


if __name__ == "__main__":
    main()