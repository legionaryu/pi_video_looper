# encoding: utf-8

import logging
import serial
import serial.threaded
import threading


class ArduinoProtocol(serial.threaded.LineReader):

    TERMINATOR = b'\r\n'
    ENCODING = 'ascii'

    def __init__(self):
        super(ArduinoProtocol, self).__init__()
        self.selector_position = -1
        self.charger_state = -1

    def handle_line(self, line):
        """
        Handle input from serial port, check for events.
        """
        if line[0] == 'S':
            try:
                self.selector_position = min(max(int(line[1]), 1), 4)
            except Exception as e:
                print('ArduinoProtocol error reading selector_position:\n %s'.format(e))
            if line[2] == 'C':
                try:
                    self.charger_state = 0 if int(line[3]) == 0 else 1
                except Exception as e:
                    print('ArduinoProtocol error reading charger_state:\n %s'.format(e))