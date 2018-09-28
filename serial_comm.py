import serial
import re
import random
from datetime import datetime
import logging


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


class SerialListener:
    def __init__(self, port,
                 baud=19200,
                 bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE):
        self.ser = serial.Serial(port, baud, bytesize, parity, stopbits)
        self.handler = SessionHandler()
        self.regexp = {
            'alive': 'LADER ([0-9]+) lebt',
            'start': '(Abrechnung auf)',
            'rfid': 'Tag ID = (([0-9A-F\s|A-F0-9\s]{3})+)',
            'check': '(Verstanden)',
            'end': '(total FERTIG)',
        }

    def listen(self):
        while True:
            # TODO: Separate bus reading and processing
            line = str(self.ser.readline(), 'ascii')
            logger.debug(line)
            line_params = line.split(' ')

            alive_match = re.match(self.regexp['alive'], line)
            start_match = re.match(self.regexp['start'], line)
            if alive_match:
                logger.debug('Charger %s is alive' % alive_match.group(1))
            elif start_match:
                rfid_line = str(self.ser.readline(), 'ascii')
                rfid_match = re.match(self.regexp['rfid'], rfid_line)
                if rfid_match:
                    tag_id = rfid_match.group(1)
                    logger.debug("Ready for charging on station"
                                 " %s with tag %s" % (alive_match.group(1), tag_id))
                    self.ser.write('OK_Lader1')

            """
            if line_params[0].split('/')[0] == 'MMETERING':
                content_length = str(self.ser.readline(), 'ascii').split(": ")

                chunk = {
                    'Version': line_params[0].split("/")[1],
                    'Action': line_params[1].rstrip(),
                    'Content-Length': int(content_length[1].rstrip())
                }

                for i in range(0, chunk['Content-Length']):
                    header = str(self.ser.readline(), 'ascii')

                    kv = header.split(': ')
                    chunk[kv[0]] = kv[1].rstrip()

                print(chunk)
                self.handle(chunk)
            """
    def handle(self, header):
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


listener = SerialListener('/dev/ttyUSB1')
listener.listen()
