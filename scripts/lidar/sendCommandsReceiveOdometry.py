#!/usr/bin/python
import random
import sys
import serial
import time

import numpy as np

from CmdMessenger import CmdMessenger
from serial.tools import list_ports

from rawStringsLoggingServer import PyTableSavingHandler


class GunnarCommunicator(object):

    def __init__(self, fname="data/gunnarCommunicator.h5", logLength=28):
        self.statusHistory = [''] * logLength
        self.constructionTime = time.time()
        
        # Create a handler object for saving data.
        nfields = (
              1  # time (milliseconds)
            + 1  # sonar
            + 4  # heading and euler angles (redundant)
            + 3  # orientation x,y,z
            + 3  # velocity vx,vy,vz
            + 3  # motor 1 ticks, speed, and status
            + 3  # motor 2 ticks, speed, and status
            + 1  # whether motor PID controller is in turning mode (obsolete)
            )
        self.nfields = nfields
        self.handler = PyTableSavingHandler(fname, dataShape=(nfields,))
        
        # Make sure this matches the baudrate on the Arduino.
        self.baud = 19200
        
        self.commands = [
                         'acknowledge',    # outgoing
                         'error',          
                         'speedSet',       # outgoing
                         'sensorsRequest', # outgoing
                         'sensorsResponse',
                         'acknowledgeResponse',
                         ]

        try:
            # Try to open a USB port.
            self.port_name = self.list_usb_ports()[1][0]
            self.serial_port = serial.Serial(self.port_name, self.baud, timeout=0)
        except (serial.SerialException, IndexError) as e:
            raise SystemExit('Could not open serial port: %s' % e)
        else:
            self.statusMessage =  'Serial port %s sucessfully opened.' % self.port_name
            self.messenger = CmdMessenger(self.serial_port, cmdNames = self.commands)
            # attach callbacks
            self.messenger.attach(func=self.onError, msgid=self.commands.index('error'))
            self.messenger.attach(func=self.onSensorsResponse,
                                  msgid=self.commands.index('sensorsResponse'))
            self.messenger.attach(func=self.onError, msgid=None)

            # send a command that the arduino will acknowledge
            self.acknowledge()
            self.statusMessage =  'Arduino ready.'
        
    @property
    def statusMessage(self):
        return self._statusMessage
    
    @statusMessage.setter
    def statusMessage(self, args):
        if isinstance(args, tuple):
            self._statusMessage = ' '.join(['%s' % (s,) for s in args])
            for i in range(1, len(self.statusHistory)):  # Keep a scrolling history of status messages.
                self.statusHistory[i-1] = self.statusHistory[i]
            self.statusHistory[i] = self._statusMessage
        else:
            self.statusMessage = (args,)

    def list_usb_ports(self):
        """ Use the grep generator to get a list of all USB ports.
        """
        ports =  [port for port in list_ports.grep('usb')]
        return ports

    def loopOnce(self):
        # Request sensor data.
        self.sensorsRequest()

        # Check to see if any data has been received
        self.messenger.feed_in_data()

    ############################### C O M M A N D S ###########################
    def acknowledge(self, wait=True):
        self.messenger.send_cmd(self.commands.index('acknowledge'))
        if wait:
            # Wait until the arduino sends an acknowledgement back
            self.messenger.wait_for_ack(ackid=self.commands.index('acknowledgeResponse'))

    def sensorsRequest(self):
        self.messenger.send_cmd(self.commands.index('sensorsRequest'))
        ## This doesn't work:
        #self.messenger.wait_for_ack(ackid=self.commands.index('acknowledgeResponse'),
                                    #msgid=self.commands.index('sensorsResponse')
            #)
        
    def speedSet(self, left, right):
        self.statusMessage = 'Setting motor speeds to left=%f, right=%f.' % (left, right)
        self.messenger.send_cmd(self.commands.index('speedSet'), left, right)

    ####################### R E S P O N S E   C A L L B A C K S ###############
    def onError(self, received_command, *args, **kwargs):
        """Callback function to handle errors
        """
        self.statusMessage =  'Error:', args

    nresp = 0.
    def onSensorsResponse(self, received_command, *args, **kwargs):
        """Callback to handle the float addition response
        """
        try:
            from struct import unpack#, calcsize
            types = 'LffffffLLlHH?'
            #s = calcsize(types)
            s = 45
            byteString = args[0][-1]
            if len(byteString) >= s:
                arr = unpack(types, byteString[:s])
                elapsed = time.time() - self.constructionTime
                self.statusMessage =  'Got response data: %s.' % (arr,)
                self.nresp += 1
                #self.statusMessage =  "Response data:", arr
        except Exception as e:
            self.statusMessage =  "Failed with %s: %s" % (type(e), e)
        
        ## Save the data in our HDF5 file.
        #data = np.empty((self.nfields,))
        #assert len(args[0]) == self.nfields
        #data[:] = args[0]
        #self.handler.enquque(data)


if __name__ == '__main__':
    from time import sleep
    
    gunnarCommunicator = GunnarCommunicator()
    gunnarCommunicator.loopOnce()
