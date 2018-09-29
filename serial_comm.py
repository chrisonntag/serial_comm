import serial
import re
import random
from datetime import datetime
import logging
import threading
from queue import Queue


logging.basicConfig(filename='serial_comm.log',
                    level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Session:
    """
    Represents a charging session from START to END, instantiated
    by the charging station.
    """

    def __init__(self, header):
        self.id = None
        self.charging_station = header['Id']
        self.key = header['Key']
        self.start_time = None
        self.end_time = None

    def open(self):
        self.set_session_id(random.randint(0, 1000))
        self.start_time = datetime.timestamp()

    def close(self):
        self.end_time = datetime.timestamp()

    def get_charging_station(self):
        return self.charging_station

    def get_rfid_key(self):
        return self.key

    def get_session_id(self):
        return self.id

    def set_session_id(self, session_id):
        self.id = session_id


class SessionHandler:
    """
    Handles communication according to the MMETERING/1.0 protocol.
    """

    def __init__(self):
        self.sessions = dict()

    def is_empty(self):
        return self.sessions == {}

    def get(self, key):
        return self.sessions[key]

    def end(self, key):
        logger.debug("Session %d will be closed." % key)

        session = self.sessions[key]
        del self.sessions[key]
        session.close()

        return 'OK', session.get_session_id()

    def start(self, session):
        session.open()
        self.sessions[session.get_session_id()] = session

        logger.debug("New session with id %d on charger %d has been "
                     "started." % (session.get_session_id, session.get_charging_station()))
        return 'OK_Lader%d' % session.get_charging_station()


class SerialListener(threading.Thread):
    def __init__(self, port, serial_in: Queue, serial_out: Queue,
                 baud=19200,
                 bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE):
        threading.Thread.__init__(self)
        self.ser = serial.Serial(port, baud, bytesize, parity, stopbits)
        self.serial_in = serial_in
        self.serial_out = serial_out

    def run(self):
        while True:
            # read data from the bus
            line = str(self.ser.readline(), 'ascii')
            logger.debug('INCOMING>' + line.replace('\n', ''))
            self.serial_in.put(line)

            # write data to the bus
            if not self.serial_out.empty():
                data = self.serial_out.get()
                logger.debug('OUTGOING>' + data)
                self.ser.write(data + '\r\n'.encode())


class SerialHandler(threading.Thread):
    def __init__(self, serial_in: Queue, serial_out: Queue):
        threading.Thread.__init__(self)
        self.serial_in = serial_in
        self.serial_out = serial_out
        self.regexp = {
            'alive': 'LADER ([0-9]+) lebt',
            'start': '(Abrechnung auf)',
            'rfid': 'Tag ID = (([0-9A-F\s|A-F0-9\s]{3})+)',
            'check': '(Verstanden)',
            'end': '(total FERTIG)',
        }

    def run(self):
        while True:
            if not self.serial_in.empty():
                data = self.serial_in.get()
                alive_match = re.match(self.regexp['alive'], data)
                start_match = re.match(self.regexp['start'], data)
                if alive_match:
                    logger.debug('Charger %s is alive' % alive_match.group(1))
                elif start_match and not self.serial_in.empty():
                    rfid_line = self.serial_in.get()
                    rfid_match = re.match(self.regexp['rfid'], rfid_line)
                    if rfid_match:
                        tag_id = rfid_match.group(1)
                        logger.debug("Ready for charging on station with tag %s" % tag_id)
                        self.serial_out.put('OK_Lader1!')

    def process(self, header):
        if header['Action'] == 'START':
            # new session will be started
            status, session_id = self.handler.start(Session(header))
        else:
            # closes a session
            try:
                status, session_id = self.handler.end(header['Session-Id'])
            except KeyError:
                # couldn't find the session_id, maybe transmission error
                status = 'ERROR'

        if status is not 'ERROR':
            self.ser.write('MMETERING/1.0 OK\n'.encode())
            self.ser.write(('Session-Id: %d\n' % session_id).encode())
        else:
            self.ser.write('MMETERING/1.0 ERROR\n'.encode())


if __name__ == '__main__':
    in_queue = Queue()
    out_queue = Queue()

    listener = SerialListener('/dev/ttyUSB1', in_queue, out_queue)
    handler = SerialHandler(in_queue, out_queue)

    listener.start()
    handler.start()
    listener.join()
    handler.join()
