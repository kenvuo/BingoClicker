import pyaudio
from math import pow
import struct
import time
import threading
import multiprocessing


import pyHook
import pythoncom
import pyautogui

Threshold = 0.001
SHORT_NORMALIZE = (1.0/32768.0)
chunk = 1024
swidth = 2
TIMEOUT_LENGTH = 0.2


class Recorder:

    process = None
    clickerStatus = False
    clickerRestart = False

    @staticmethod
    def rms(frame):
        count = len(frame) / swidth
        format = "%dh" % count
        shorts = struct.unpack(format, frame)

        sum_squares = 0.0
        for sample in shorts:
            n = sample * SHORT_NORMALIZE
            sum_squares += n * n
            rms = pow(sum_squares / count, 0.5)

            return rms * 1000

    def __init__(self):

        # create a hook manager
        hm = pyHook.HookManager()
        # watch for all mouse events
        hm.KeyDown = self.OnKeyboardEvent
        # set the hook
        hm.HookKeyboard()

    def setup(self):
        self.process = multiprocessing.Process(target=self.run)
        # self.process.start()
        self.process.daemon = True
        # Read commands 4ever
        print("Handler ready. Press Shift+P to start")
        self.handler()
    
    def restart(self):
        self.process = multiprocessing.Process(target=self.run)
        self.process.daemon = True

    def run(self):
        self.p = pyaudio.PyAudio()
        device_info = self.setDevice()
        CHANNELS = device_info["maxOutputChannels"]
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=CHANNELS,
                                  rate=int(device_info["defaultSampleRate"]),
                                  input=True,
                                  frames_per_buffer=chunk,
                                  input_device_index = device_info["index"],
                                  as_loopback=True)
        self.listen()

    def setDevice(self):
        # Loop device. Check for speaker and WASAPI
        for i in range(0, self.p.get_device_count()):
            device_info = self.p.get_device_info_by_index(i)
            is_input = device_info["maxInputChannels"] > 0
            is_wasapi = (self.p.get_host_api_info_by_index(device_info["hostApi"])["name"]).find("WASAPI") != -1
            if is_wasapi and not is_input:
                # print('Device found. Qutting loop')
                # print(": \t %s \n \t %s \n" % (device_info["name"], self.p.get_host_api_info_by_index(device_info["hostApi"])["name"]))
                # print(device_info["defaultSampleRate"])
                # print(device_info["maxOutputChannels"])
                return device_info
        print('No device found. Exiting')
        exit(0)

    def record(self):
        print('Noise detected')
        current = time.time()
        end = time.time() + TIMEOUT_LENGTH

        while current <= end:
            data = self.stream.read(chunk)
            # print(data)
            if self.rms(data) >= Threshold:
                end = time.time() + TIMEOUT_LENGTH
            current = time.time()
        print('Noise stopped')

    def listen(self):
        print('Listening')
        clicker = Clicker()
        clicker.daemon = True
        clicker.start()
        while True:
            input = self.stream.read(chunk)
            rms_val = self.rms(input)
            if rms_val > Threshold:
                clicker.pause()
                self.record()
                clicker.resume()
            # print('End of Loop')

    def handler(self):
        # wait forever
        pythoncom.PumpMessages()

    def OnKeyboardEvent(self, event):
        #print("test")
        ctrl_pressed = pyHook.GetKeyState(pyHook.HookConstants.VKeyToID('VK_SHIFT'))
        if ctrl_pressed and pyHook.HookConstants.IDToName(event.KeyID) == 'P':
            # Try start clicker
            if self.clickerRestart:
                print("Shift+P pressed. Resuming")
                self.restart()
                self.process.start()
                self.clickerRestart = False
                self.clickerStatus = True
            elif not self.clickerStatus:
                print("Shift+P pressed. Resuming")
                self.process.start()
                self.clickerStatus = True

        if pyHook.HookConstants.IDToName(event.KeyID) == 'Return':
            if self.clickerStatus:
                print('Return pressed. Pausing')
                self.process.terminate()
                self.clickerStatus = False
                self.clickerRestart = True

        # return True to pass the event to other handlers
        return True


class Clicker(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        #flag to pause thread
        self.paused = False
        self.pause_cond = threading.Condition(threading.Lock())

    def run(self):
        while True:
            with self.pause_cond:
                while self.paused:
                    self.pause_cond.wait()

                #thread should do the thing if
                #not paused
                print('left-click')
                # self.left_click()
            time.sleep(2)

    def left_click(self):
        pyautogui.click()

    def pause(self):
        self.paused = True
        # If in sleep, we acquire immediately, otherwise we wait for thread
        # to release condition. In race, worker will still see self.paused
        # and begin waiting until it's set back to False
        self.pause_cond.acquire()

    #should just resume the thread
    def resume(self):
        self.paused = False
        # Notify so thread will wake after lock released
        self.pause_cond.notify()
        # Now release the lock
        self.pause_cond.release()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    b = Recorder()
    b.setup()
