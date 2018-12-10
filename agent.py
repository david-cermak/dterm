import json
import argparse
import serial
import os
from threading import Thread
import time
import paho.mqtt.client as mqtt

connected = 0
mqtt_data = []
run_mqtt = True
run_serial = True
ser = None
client = None

def on_connect(client, userdata, flags, rc):
    global connected
    connected = 1

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global mqtt_data
    global ser
    print(msg.payload)
    ser.write(msg.payload)

def serial_thread(publish):
    out = b""
    global run_serial
    global ser
    global client
    i = 0
    while run_serial:
        while ser.inWaiting() > 0:
            char = ser.read(1)
            if char == b"\n":
                break
            out += char
        if out != b"":
            client.publish(publish, out.strip(), 0)
            print(out)
            out = b""
        time.sleep(0.02)

def mqtt_thread(broker, subscribe):
    global mqtt_data
    global connected
    global run_mqtt
    global client
    client.connect(broker, 1883, 60)
    client.subscribe(subscribe)
    last_len = 0
    while run_mqtt:
        client.loop()
        if  connected == 0:
            print(".")
        time.sleep(0.02)

def main():
    global ser
    global client
    global run_mqtt
    global run_serial
    parser = argparse.ArgumentParser(description='Simple serial terminal')
    parser.add_argument('-p','--port', default='/dev/ttyUSB0', help='Port id', required=False)
    parser.add_argument('-j','--json', default='term.jsom', help='Configuration', required=False)
    args = vars(parser.parse_args())
    with open(args['json']) as f:
        cfg = json.load(f)
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message            
    ser = serial.Serial(
            port=args['port'],
            baudrate=115200,
            )
    thread1 = Thread(target = mqtt_thread,  args = ( cfg["remote"]["broker"], cfg["remote"]["publish"]) )
    thread2 = Thread(target = serial_thread, args = ( cfg["remote"]["subscribe"], ))
    thread1.start()
    thread2.start()
    try:
        while True:
            print("*")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        run_serial = False
        run_mqtt =False
        thread1.join()
        thread2.join()

if __name__ == '__main__':
    main()