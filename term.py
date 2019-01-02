import json
import argparse
import curses
import curses.textpad
import serial
import os
import sys
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
        self.macro = []
        if "macro" in cfg and cfg["macro"] != None:
            for i in cfg["macro"].keys():
                self.macro.append(i)
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
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(9, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(10, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(11, curses.COLOR_BLACK, curses.COLOR_RED)

        self.height, self.width = self.window.getmaxyx()
        self.search_h = 10
        self.log_height = self.height - self.search_h - 1
        self.log_width = self.width - 1
        self.selected = 0
        self.history = [ self.init_cmd ]
        self.populate_search_box()
        self.refresh()

        self.len = curses.LINES
        self.run_serial = True
        self.start()

    def populate_search_box(self):
        self.search_box = self.history[:5] +  self.macro +  self.commands

    def refresh(self):
        curses.textpad.rectangle(self.window, 0, 0, self.search_h, self.log_width)
        for i in range(self.search_h-1):
            self.window.addstr(i+1, 1, " "*(self.log_width - 2), curses.color_pair(3))
        if len(self.search_box) > 0:
            for idx, item in enumerate(self.search_box[:self.search_h-2]):
                if self.selected != 0 and self.selected == (idx+1):
                    self.window.addstr(idx + 2, 1, item, curses.color_pair(9))
                    self.window.addstr(1, 1, item, curses.color_pair(4))
                else:
                    if self.selected == 0:
                        self.window.addstr(1, 1, "----Enter-to-edit----", curses.color_pair(9))
                    self.window.addstr(idx + 2, 1, item, curses.color_pair(10))
        curses.textpad.rectangle(self.window, self.search_h + 1, 0, self.height - 2, self.log_width)
        # Ansi characters
        ansi_escape = re.compile(r'\x1B\[[0-9]*[\;]*[0-9]*m')
        for idx, item in enumerate(self.log[-(self.height - 4  - self.search_h):]):
            item = item.replace(b'\0', b'0').decode() 
            self.window.addstr(idx+ self.search_h + 2, 1, " "*(self.log_width - 2), curses.color_pair(1))
            m = ansi_escape.search(item)
            pos = 0
            last_color = curses.color_pair(1)
            while m:
                if m.span()[0] > 0:
                    self.window.addstr(idx+ self.search_h + 2, 1 + pos, item[0:m.span()[0]], last_color)
                    pos = m.span()[0]
                if m.group() == '\x1B[0;31m':
                    last_color = curses.color_pair(3)
                elif m.group() == '\x1B[0;32m':
                    last_color = curses.color_pair(4)
                elif m.group() == '\x1B[0;33m':
                    last_color = curses.color_pair(5)
                elif m.group() == '\x1B[0;34m':
                    last_color = curses.color_pair(6)
                elif m.group() == '\x1B[0;35m':
                    last_color = curses.color_pair(7)
                elif m.group() == '\x1B[0;36m':
                    last_color = curses.color_pair(8)
                elif m.group() == '\x1B[0;41m':
                    last_color = curses.color_pair(11)
                elif m.group() == '\x1B[0m':
                    last_color = curses.color_pair(1)
                item = item[m.span()[1]:]
                m = ansi_escape.search(item)
            if item:
                self.window.addstr(idx+ self.search_h + 2, 1 + pos, item, last_color)

    def macro_code(self, code):
        last_len = len(self.log)
        # by default set timeout to 2 seconds
        start = time.time()
        while (time.time() - start) <= 2:
            if last_len != len(self.log):
                sys.argv = [code , self.log[last_len]]
                execfile(code)
                last_len = len(self.log)

    def send(self, data):
        # TODO: replace with class encapsulation (port.send)
        if self.history[0] != data:
            self.history.insert(0,data)
        if data in self.macro:
            if "code" in self.cfg["macro"][data]:
                t = Thread(target = self.macro_code, args=(self.cfg["macro"][data]["code"], ) )
                t.start()
            for i in self.cfg["macro"][data]["commands"]:
                self.send(i)
            return
        data = (self.prefix + data + self.sufix).encode()
        # echo commands to window -> TODO make it configurable
        self.log.append(b'\x1B[0;41m'+ data + b'\x1B[0m')
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
        self.send(self.init_cmd)
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
                        self.window.addstr(1, 1, " "*(self.log_width - 2), curses.color_pair(4))
                        self.window.addstr(1, 1, self.search_box[self.selected-1], curses.color_pair(1))
                        self.window.nodelay(False)
                        curses.echo()
                        ch = 0
                        self.window.move(1, 1 + len(self.search_box[self.selected-1]))
                        while ch != curses.KEY_ENTER and ch != 10 and ch != 13 and ch != 27:
                            ch = self.window.getch()
                        message = self.window.instr(1, 1, 50).strip()
                        self.window.nodelay(True)
                        curses.noecho()
                        if ch != 27: # ESC
                            self.send(message.decode())
                        self.selected = 0
                elif ch == curses.KEY_ENTER or ch == 10 or ch == 13:
                    self.search_i = 0
                    search_f = ''
                    if self.selected == 0:
                        self.window.addstr(1, 1, " "*(self.log_width - 2), curses.color_pair(1))
                        self.window.move(1, 1)
                        self.window.nodelay(False)
                        curses.echo()
                        message = self.window.getstr(1,1, 35)
                        self.window.nodelay(True)
                        curses.noecho()
                        self.send(message.decode())
                    else:
                        self.send(self.search_box[self.selected-1])
                    self.populate_search_box()
                    self.selected = 0
                elif ch == ord('+') and self.search_h < self.height-5:
                    self.search_h += 1
                elif ch == ord('-') and self.search_h > 5:
                    self.search_h -= 1
                elif ch ==  ord('q'):
                    break
                elif ch > 0 and ch < 255 and chr(ch).isalpha():
                    search_i += 1
                    search_f += chr(ch)
                    self.window.addstr(1, 1, "Filter: " + search_f, curses.color_pair(4))
                    full_search_box = self.search_box
                    self.search_box = []
                    for item in full_search_box:
                        if re.match(search_f, item, re.I):
                            self.search_box.append(item)
                    self.search_box = list(set(self.search_box))
                    self.refresh()
                elif ch == 27: # ESC
                    search_i = 0
                    search_f = ''
                    self.populate_search_box()
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