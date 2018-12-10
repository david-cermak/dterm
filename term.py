import json
import argparse
import curses
import curses.textpad
import serial
import os
import re
from threading import Thread
import time
import paho.mqtt.client as mqtt

connected = 0
mqtt_data = []

def on_connect(client, userdata, flags, rc):
    global connected
    connected = 1

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global mqtt_data
    mqtt_data.append(msg.payload)

class Terminal(object):
    def __init__(self, serial_port, cfg):
        """ Initialize terminal windows
        """
        self.window = curses.initscr()
        self.window.nodelay(True)
        self.window.keypad(True)
        self.log = []
        self.prefix = cfg["prefix"]
        self.sufix = cfg["sufix"]
        self.commands = cfg["commands"]
        self.init_cmd = cfg["init"]
        self.cfg = cfg
        self.search_i = 0
        self.remote = False
        self.port = None
        self.ser = None
        self.client = None
        if "remote" in cfg and serial_port == 'R':
            self.remote = True
            self.client = mqtt.Client()
            self.client.on_connect = on_connect
            self.client.on_message = on_message            
        else:
            self.ser = serial.Serial(
                    port=serial_port,
                    baudrate=115200,
                )

        curses.echo()
        curses.cbreak()

        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        self.height, self.width = self.window.getmaxyx()
        self.search_h = 10
        self.log_height = self.height - self.search_h - 1
        self.log_width = self.width - 1
        self.search_box = self.commands[:self.search_h-1]
        self.selected = 0
        self.refresh()

        self.len = curses.LINES
        self.run_serial = True
        self.start()

    def refresh(self):
        curses.textpad.rectangle(self.window, 0, 0, self.search_h, self.log_width)
        for i in range(self.search_h-1):
            self.window.addstr(i+1, 1, " "*(self.log_width - 2), curses.color_pair(3))
        if len(self.search_box) > 0:
            for idx, item in enumerate(self.search_box[:self.search_h-2]):
                if self.selected != 0 and self.selected == (idx+1):
                    self.window.addstr(idx + 2, 1, item, curses.color_pair(4))
                    self.window.addstr(1, 1, item, curses.color_pair(3))
                else:
                    if self.selected == 0:
                        self.window.addstr(1, 1, "----Enter-to-edit----", curses.color_pair(4))
                    self.window.addstr(idx + 2, 1, item, curses.color_pair(5))
        curses.textpad.rectangle(self.window, self.search_h + 1, 0, self.height - 2, self.log_width)
        log_size = len(self.log)
        top = log_size - (self.log_height - 3)
        if top < 0:
            top = 0
        for idx, item in enumerate(self.log[top:log_size]):
            self.window.addstr(idx+ self.search_h + 2, 1, " "*(self.log_width - 2), curses.color_pair(1))
            self.window.addstr(idx+ self.search_h + 2, 1, item, curses.color_pair(1))

    def send(self, data):
        # TODO: replace with class encapsulation (port.send)
        if self.remote:
            self.client.publish(self.cfg["remote"]["publish"], data, 0)
        else:
            self.ser.write(data)

    def start(self):
        """ Application started """
        thread1 = None
        if self.remote:
            thread1 = Thread(target = self.mqtt_thread )
        else:
            thread1 = Thread(target = self.serial_thread )
        thread1.start()
        self.send((self.prefix + self.init_cmd + self.sufix).encode())
        search_i = 0
        search_f = ''
        try:
            while True:
                ch = self.window.getch()
                self.refresh()
                if ch == curses.KEY_UP:
                    search_i = 0
                    search_f = ''
                    self.selected -= 1
                    if self.selected < 0:
                        self.selected = 0
                elif ch == curses.KEY_DOWN:
                    search_i = 0
                    search_f = ''
                    max_selection = self.search_h-2
                    if self.search_h-2 > len(self.search_box):
                        max_selection = len(self.search_box)
                    self.selected += 1
                    if self.selected > max_selection:
                        self.selected = max_selection
                elif ch == ord('\t') or ch == 9:
                        self.window.addstr(1, 1, " "*(self.log_width - 2), curses.color_pair(3))
                        self.window.addstr(1, 1, self.search_box[self.selected-1], curses.color_pair(3))
                        self.window.move(1, 1 + len(self.search_box[self.selected-1]))
                        self.window.nodelay(False)
                        curses.echo()
                        message = self.window.getstr(1,1 + len(self.search_box[self.selected-1]), 15)
                        self.window.nodelay(True)
                        curses.noecho()
                        self.send(self.prefix.encode() + self.search_box[self.selected-1].encode() +  message + self.sufix.encode() )
                        self.selected = 0
                elif ch == curses.KEY_ENTER or ch == 10 or ch == 13:
                    self.search_i = 0
                    search_f = ''
                    if self.selected == 0:
                        self.window.addstr(1, 1, " "*(self.log_width - 2), curses.color_pair(3))
                        self.window.move(1, 1)
                        self.window.nodelay(False)
                        curses.echo()
                        message = self.window.getstr(1,1, 15)
                        self.window.nodelay(True)
                        curses.noecho()
                        self.send(self.prefix.encode() + message + self.sufix.encode() )
                    else:
                        self.send(self.prefix.encode() + self.search_box[self.selected-1].encode() +self.sufix.encode() )
                    self.search_box = self.commands[:self.search_h-1]
                    self.selected = 0
                elif ch ==  ord('q'):
                    break
                elif ch > 0 and ch < 255 and chr(ch).isalpha(): # >=  ord('a') and ch <= ord('z'):
                    search_i += 1
                    search_f += chr(ch)
                    self.window.addstr(1, 1, "Filter: " + search_f, curses.color_pair(4))
                    self.search_box = []
                    for item in self.commands:
                        if re.match(search_f, item, re.I):
                            self.search_box.append(item)
                    self.refresh()
                elif ch == 27: # ESC
                    search_i = 0
                    search_f = ''
                    self.search_box = self.commands[:self.search_h-1]
                    self.refresh()
        except KeyboardInterrupt:
            pass
        finally:
            curses.endwin()
            self.run_serial = False
            thread1.join()

    def serial_thread(self):
        out = b""
        i = 0
        while self.run_serial:
            while self.ser.inWaiting() > 0:
                char = self.ser.read(1)
                if char == b"\n":
                    break
                out += char
            if out != b"":
                self.log.append(out.strip())
                out = b""
            time.sleep(0.02)

    def mqtt_thread(self):
        global mqtt_data
        global connected
        self.client.connect(self.cfg["remote"]["broker"], 1883, 60)
        self.client.subscribe(self.cfg["remote"]["subscribe"])
        last_len = 0
        while self.run_serial:
            self.client.loop()
            if  connected == 0:
                self.window.addstr(1, 1, "|", curses.color_pair(4))
                time.sleep(0.02)
                self.window.addstr(1, 1, "--", curses.color_pair(4))
                time.sleep(0.02)                
            else:
                if len(mqtt_data) != last_len:
                    self.log = mqtt_data
                    last_len = len(mqtt_data)
            time.sleep(0.02)

def main():
    parser = argparse.ArgumentParser(description='Simple serial terminal')
    parser.add_argument('-p','--port', default='/dev/ttyUSB0', help='Port id', required=False)
    parser.add_argument('-j','--json', default='term.jsom', help='Configuration', required=False)
    args = vars(parser.parse_args())
    with open(args['json']) as f:
        cfg = json.load(f)
    Terminal(args['port'], cfg)


if __name__ == '__main__':
    main()