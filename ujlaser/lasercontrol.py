import serial
import serial.tools.list_ports
import time
import threading as thread

from ujlaser.repeatedtimer import RepeatedTimer

class LaserCommandError(Exception):
    pass

class LaserFireError(Exception):
    pass

class KickerError(Exception):
    pass

class LaserStatusResponse():
    """This class is used to manipulate the SS? command and turn it into useful variables"""
    def __init__(self, response):
        """Parses the response string into a new LaserStatusResponseObject"""

        i = int(response) # slice off the \r at the end
        self.laser_enabled = bool(i & 1)
        self.laser_active = bool(i & 2)
        self.diode_external_trigger = bool(i & 8)
        self.external_interlock = bool(i & 64)
        self.resonator_over_temp = bool(i & 128)
        self.electrical_over_temp = bool(i & 256)
        self.power_failure = bool(i & 512)
        self.ready_to_enable = bool(i & 1024)
        self.ready_to_fire = bool(i & 2048)
        self.low_power_mode = bool(i & 4096)
        self.high_power_mode = bool(i & 8192)

    def __int__(self):
        """Returns an integer representation of the laser status. Should be an ASCII number as shown in the user manual."""
        i = 0
        if self.laser_enabled:
            i += 1
        if self.laser_active:
            i += 2
        if self.diode_external_trigger:
            i += 8
        if self.external_interlock:
            i += 64
        if self.resonator_over_temp:
            i += 128
        if self.electrical_over_temp:
            i += 256
        if self.power_failure:
            i += 512
        if self.ready_to_enable:
            i += 1024
        if self.ready_to_fire:
            i += 2048
        if self.low_power_mode:
            i += 4096
        if self.high_power_mode:
            i += 8192

        return i

    def __str__(self):
        """Returns a status print out in human-readable format."""
        s = "Laser is "
        if self.laser_enabled:
            s += "enabled\n"
        else:
            s += "disabled\n"

        s += "External Interlock is: "
        if self.external_interlock:
            s += "DISCONNECTED\n"
        else:
            s += "CONNECTED\n"

        s += "Ready to fire: " + str(self.ready_to_fire) + "\n"
        s += "Ready to enable: " + str(self.ready_to_enable) + "\n"

        if self.low_power_mode:
            s +=  "Laser is in LOW power mode.\n"
        elif self.high_power_mode:
            s += "Laser is in HIGH power mode.\n"
        else:
            s += "Laser is in MANUAL power mode.\n"

        if self.laser_active:
            s += "Laser is ACTIVE.\n"
        else:
            s += "Laser is not active.\n"

        errors = ""
        if self.power_failure:
            errors += "!!!POWER FAILURE              !!!\n"
        if self.resonator_over_temp:
            errors += "!!!RESONATOR OVER TEMPERATURE !!!\n"
        if self.electrical_over_temp:
            errors += "!!!ELECTRICAL OVER TEMPERATURE!!!\n"
        
        if len(errors) > 0:
            s += "!!!---------------------------!!!\n"
            s += "!!!       ERROR REPORT        !!!\n"
            s += errors
            s += "!!!===========================!!!\n"
        return s

class Laser:
    """This class is where all of our functions that interact with the laser reside."""
    # Constants for Energy Mode
    MANUAL_ENERGY = 0
    LOW_ENERGY = 1
    HIGH_ENERGY = 2

    # Constants for shot mode
    CONTINUOUS = 0
    SINGLE_SHOT = 1
    BURST = 2

    def __init__(self, pulseMode = 0, pulsePeriod = 0, repRate = 1, burstCount = 10, pulseWidth = 10, diodeTrigger = 0):
        self._ser = None
        self.pulseMode = pulseMode # NOTE: Pulse mode 0 = continuous is actually implemented as 2 = burst mode in this code.
        self.pulsePeriod = pulsePeriod
        self.repRate = repRate          # NOTE: The default repitition rate for the laser is 1 Hz not 10 Hz (10 is out of bounds aswell)
        self.burstCount = burstCount    # NOTE: The default burst count for the laser is 10 not 10000
        self.pulseWidth = pulseWidth
        self.diodeTrigger = diodeTrigger

        self.emergencyStopActive = False
        self._lock = thread.Lock() # this lock will be acquired every time the serial port is accessed.
        self._device_address = "LA"
        self.connected = False
        self._fire_timer = 0
        self._kicker_interval = 1 # Run the kicker every second
        self._kicker = RepeatedTimer(self._kicker_interval, self._kicker_callback, False, self)

    def connect(self, port_number, baud_rate=115200, timeout=1, parity=None, refresh=False):
        """
        Sets up connection between flight computer and laser

        Parameters
        ----------
        port_number : int
            This is the port number for the laser

        baud_rate : int
            Bits per second on serial connection

        timeout : int
            Number of seconds until a read operation fails.

        refresh : bool
            Default set to False. This resets all class variables if set to true

        """
        with self._lock:
            #if port_number not in serial.tools.list_ports.comports():
            #    raise ValueError(f"Error: port {port_number} is not available")
            
            if isinstance(port_number,serial.Serial):
                self._ser = port_number
            else:
                self._ser = serial.Serial(port=port_number)
            
            if baud_rate and isinstance(baud_rate, int):
                self._ser.baudrate = baud_rate
            else:
                raise ValueError('Error: baud_rate parameter must be an integer')
            if timeout and isinstance(timeout, int):
                self._ser.timeout = timeout
            else:
                raise ValueError('Error: timeout parameter must be an integer')
            if not parity or parity == 'none':
                self._ser.parity = serial.PARITY_NONE
            elif parity == 'even':
                self._ser.parity = serial.PARITY_EVEN
            elif parity == 'odd':
                self._ser.parity = serial.PARITY_ODD
            elif parity == 'mark':
                self._ser.parity = serial.PARITY_MARK
            elif parity == 'space':
                self._ser.parity = serial.PARITY_SPACE
            else:
                raise ValueError("Error: parity must be None, \'none\', \'even\', \'odd\', \'mark\', \'space\'")
            
            self.connected = True            
            
        if refresh:
            self.refresh_parameters()

    def disconnect(self):
        if not self.connected:
            return
        self._ser.close()
        self.connected = False
        self._ser = None
        
    def refresh_parameters(self):
        """
        Query the laser about it's current settings.
        """
        self.pulseMode = self.get_pulse_mode()
        self.pulsePeriod = self.get_pulse_period()
        self.repRate = self.get_repetition_rate()
        self.burstCount = self.get_burst_count()
        self.pulseWidth = self.get_pulse_width()
        self.diodeTrigger = self.get_diode_trigger()

    def _send_command(self, cmd):
        """
        Sends command to laser

        Parameters
        ----------
        cmd : string
            This contains the ASCII of the command to be sent. Should not include the prefix, address, delimiter, or terminator

        Returns
        ----------
        response : bytes
            The binary response received by the laser. Includes the '\r' terminator. May be None is the read timedout.
        """
        if len(cmd) == 0:
            return

        if not self.connected:
            raise ConnectionError("Not connected to a serial port. Please call connect() before issuing any commands!")

        # Form the complete command string, in order this is: prefix, address, delimiter, command, and terminator
        cmd_complete = ";" + self._device_address + ":" + cmd + "\r"

        with self._lock: # make sure we're the only ones on the serial line
            self._ser.write(cmd_complete.encode("ascii")) # write the complete command to the serial device
            time.sleep(0.01)
            response = self._ser.read_until("\r") # laser returns with <CR> = \r Note that this may timeout and return None

        return response

    def get_status(self):
        """
        Obtains the status of the laser

        Returns
        -------
        status : LaserStatusResponse object
                Returns a LaserStatusResponse object created from the SS? command's response that is received.
        """
        response = self._send_command('SS?')
        if not response or response[0] == b"?": # Check to see if we got an error instead. NOTE: This originally had len(response) < 5, but I don't see the purpose of this and it causes errors.
            raise LaserCommandError(Laser.get_error_code_description(response))
        else:
            response = str(response[:-1].decode('ascii'))
            return LaserStatusResponse(response)

    def fire(self):
        """
            Sends commands to laser to have it fire
        """
        status = self.get_status()
        
        if self.pulseMode == 0: # continuous
            fire_duration = 1 / self.repRate
        elif self.pulseMode == 1:
            fire_duration = 1 / self.repRate
        elif self.pulseMode == 2:
            fire_duration = self.burstCount / self.repRate
        else:
            raise LaserCommandError("Invalid pulse mode set for laser!")

        self.fire_duration = fire_duration

        if not status.laser_enabled:
            raise LaserCommandError("Laser not armed!") 
        if not status.ready_to_fire:
            raise LaserCommandError("Laser not ready to fire!")
        
        if fire_duration >= 3: # Start the kicker thread
            print("Starting kicker...")
            self._kicker.start()

        print("Laser firing...") 
        fire_response = self._send_command('FL 1')
        if fire_response != b"ok\r\n":
            self._send_command('FL 0') # aborts if laser fails to fire
            raise LaserCommandError(Laser.get_error_code_description(fire_response))
 
    def _kicker_callback(self, laser):
        try:
            status = laser.get_status()
        except LaserCommandError as e:
            laser._send_command("FL 0")
            laser._kicker.stop()

        if not status:
            laser._send_command("FL 0") # We got an error while asking for the status, best idea to stop firing
            laser._kicker.stop()
 
        if not status.laser_active and laser._fire_timer > laser.fire_duration:
            laser._kicker.stop()
            laser._fire_timer = 0
        else:
            laser._fire_timer += laser._kicker_interval

    def emergency_stop(self):
        """Immediately sends command to laser to stop firing
        
        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        self.emergencyStopActive = True
        if self.fireThread not in self._threads:    # Checking if fireThread is an active thread
            response = self._send_command('FL 0')
            if response == b"ok\r\n":
                return True
            else:
                raise LaserCommandError(Laser.get_error_code_description(response))
            
    def arm(self):
        """Sends command to laser to arm. Returns True on nominal response.
        
        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        if self.is_armed():
            raise LaserCommandError("Laser already armed")
        response = self._send_command('EN 1')
        if response == b"ok\r\n":
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def disarm(self):
        """Sends command to laser to disarm. Returns True on nominal response.
        
        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        response = self._send_command('EN 0')

        if response == b"ok\r\n":
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def is_armed(self):
        """
        Checks if the laser is armed
        Returns
        -------
        armed : boolean
            True if the laser is armed. False if the laser is not armed.
        """
        response = self._send_command('EN?')
        if not response or response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))

        return response[0] == b'1' # This has been tested on the driver box

    def get_resonator_temp(self):
        """
        Checks the resonator temperature the laser

        Returns
        -------
        resonator_temp : float
            Returns the float value of the resonator temperature in Celsius.
        """
        response = self._send_command('TR?')
        if not response or response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return float(response.decode('ascii'))

    def get_fet_temp(self):
        """
        Checks the FET temperature the laser

        Returns
        -------
        fet : float
            Returns the float value of the FET temperature in Celsius.
        """
        response = self._send_command('FT?')
        if response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return float(response[:-1].decode('ascii'))

    def get_fet_voltage(self):
        """
        Checks the FET voltage of the laser

        Returns
        -------
        fet_voltage : float
            Returns the float value of the FET voltage
        """
        response = self._send_command('FV?')
        if response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return float(response.decode('ascii'))    #TODO: All responce[:-4] does is returns b'', what is the purpose of this... It should be returning the actual data, something like responce [:-1] would remove the \r and leave just data

    def get_diode_current(self):
        """
        Checks current to diode of the laser

        Returns
        -------
        diode_current : float
            Returns the float value of the diode current
        """
        response = self._send_command('IM?')
        if response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return float(response.decode('ascii'))

    def get_bank_voltage(self):
        """
        This command requests to see what value the laser's bank voltage is at.
        
        Returns
        -------
        bank_voltage : float
            Returns the float value of the laser's bank voltage.
        """
        response = self._send_command('BV?')
        if response[0] == b'?':
            raise LaserCommandError(Laser.get_error_code_description(response))
        response_str = response.decode('ascii')
        return float(response_str)

    def get_laser_ID(self):
        """
        This command requests to see what the laser's ID value is.

        Returns
        -------
        ID : str
            Returns a string containing the laser's ID information
        """
        response = self._send_command('ID?')
        if response[0] == b'?':
            raise LaserCommandError(Laser.get_error_code_description(response))
        response_str = str(response[:-1].decode('ascii'))
        return response_str

    def get_latched_status(self):
        """
        This command requests to see what the laser's latched status is.

        Returns
        -------
        latched_status : str
            Returns a string containing the laser's latched status
        """
        #Returns b'0\r' when the remote interlock is in, and returns b'64\r' when the remote interlock is out.
        response = self._send_command('LS?')
        if response[0] == b'?':
            raise LaserCommandError(Laser.get_error_code_description(response))
        response_str = str(response[:-1].decode('ascii'))
        return response_str

    def get_system_shot_count(self):
        """
        This command requests to see what the laser's system shot count is.

        Returns
        -------
        system_SC : int
            Returns the system shot count since factory build.
        """
        response = self._send_command('SC?')
        if response[0] == b'?':
            raise LaserCommandError(Laser.get_error_code_description(response))
        response_str = str(response.decode('ascii'))
        return int(response_str)

    def get_pulse_mode(self):
        response = self._send_command("PM?")
        if not response or response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return int(response)

    def set_pulse_mode(self, mode):
        """Sets the laser pulse mode. 0 = continuous, 1 = single shot, 2 = burst. Returns True on nominal response.
        
        Parameters
        ----------
        mode : int
            Sets the laser pulse mode to either continuous, single shot, or burst.
        
        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        if not mode in (0,1,2) or not type(mode) == int:
            raise ValueError("Invalid value for pulse mode! 0, 1, or 2 are accepted values.")

        response = self._send_command("PM " + str(mode))
        if response == b"ok\r\n":
            self.pulseMode = mode
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def set_pulse_period(self, period):
        """Sets the pulse period for firing.
        
        Parameters
        ----------
        period : float
            The period set for continuous pulsing

        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        #TODO: We must find the pulse period MIN and MAX restrictions when we get the laser control box.
        #TODO: Once found, add these restrictions into the function so we don't send over invalid commands.
        #TODO: Also, we need to see what the laser's default pulse period is set to.
        response = self._send_command("PE " + str(period))
        if response == b"ok\r\n":
            self.pulsePeriod = float(period)
            self.repRate = 1/period
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def get_pulse_period(self):
        response = self._send_command("PE?")
        if not response or response[0] == b'?':
            raise LaserCommandError(Laser.get_error_code_description(response))
        return float(response)
        
    def get_pulse_period_range(self):
        """Returns the min and max periods for firing.
        
        Returns
        -------
        range : tuple
            Item at index 0 is the minimum period, and item at index 1 is the maximum period.
        """
        min_response = self._send_command("PE:MIN?")
        if min_response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(min_response))
        minimum = float(min_response)

        max_response = self._send_command("PE:MAX?")
        if max_response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(max_response))
        maximum = float(max_response)
            
        return (minimum, maximum)

    def get_diode_trigger(self):
        response = self._send_command("DT?")
        if not response or response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return int(response)

    def set_diode_trigger(self, trigger):
        """Sets the diode trigger mode. 0 = Software/internal. 1 = Hardware/external trigger. Returns True on nominal response.
        
        Parameters
        ----------
        trigger : int
            Sets the laser's current diode trigger between internal and external triggers

        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        if trigger != 0 and trigger != 1 or not type(trigger) == int:
            raise ValueError("Invalid value for trigger mode! 0 or 1 are accepted values.")

        response = self._send_command("DT " + str(trigger))
        if response == b"ok\r\n":
            self.diodeTrigger = trigger
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def set_pulse_width(self, width):
        """Sets the diode pulse width. Width is in seconds, may be a float. Returns True on nominal response, False otherwise.
        
        Parameters
        ----------
        width : float
            Sets the laser's pulse width

        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """

        if type(width) != int and type(width) != float or width <= 0:
            raise ValueError("Pulse width must be a positive, non-zero number value (no strings)!")

        width = float(width)

        response = self._send_command("DW " + str(width))
        if response == b"ok\r\n":
            self.pulseWidth = width
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))
        
    def get_pulse_width(self):
        response = self._send_command("DW?")
        if not response or response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return float(response)

    def set_burst_count(self, count):
        """Sets the burst count of the laser. Must be a positive non-zero integer. Returns True on nominal response, False otherwise.
        
        Parameters
        ----------
        count : int
            Sets the burst count for the laser

        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        if count <= 0 or not type(count) == int:
            raise ValueError("Burst count must be a positive, non-zero integer!")

        response = self._send_command("BC " + str(count))
        if response == b"ok\r\n":
            self.burstCount = count
            self.burstDuration = self.burstCount / self.repRate
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def get_burst_count(self):
        """Retreives the burst count of the laser."""
        response = self._send_command("BC?")
        if response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        return int(response)

    def set_repetition_rate(self, rate):
        """Sets the repetition rate of the laser. Rate must be a positive integer from 1 to 5 (# of Hz allowed). Returns True on nominal response, False otherwise.
        
        Parameters
        ----------
        rate : int
            Sets the repition rate (in Hz) for the laser.

        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        if not (type(rate) == int or type(rate) == float) or rate < 1 or rate > 5:
            raise ValueError("Laser repetition rate must be a positive number from 1 to 5!")

        response = self._send_command("RR " + str(rate))
        if response == b"ok\r\n":
            self.repRate = rate
            self.burstDuration = self.burstCount / self.repRate
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def get_repetition_rate(self):
        response = self._send_command("RR?")
        if not response:
            return
        if response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(response))
        
        return float(response)

    def get_repetition_rate_range(self):
        """Gets the minimum and maximum repitition rate for firing.
        
        Returns
        -------
        range : tuple
            Item at index 0 is the minimum repitition rate, and item at index 1 is the maximum repitition rate.
        """
        min_response = self._send_command("RR:MIN?")
        if not min_response or min_response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(min_response))
        minimum = float(min_response)

        max_response = self._send_command("RR:MAX?")
        if not max_response or max_response[0] == b"?":
            raise LaserCommandError(Laser.get_error_code_description(max_response))
        maximum = float(max_response)
            
        return (minimum, maximum)

    def set_diode_current(self, current):
        """Sets the diode current of the laser. Must be a positive non-zero integer (maybe even a float?). Returns True on nominal response, False otherwise.
        
        Parameters
        ----------
        current : float
            Sets the diode current for the laser. (can be an int or float)

        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        if (type(current) != int and type(current) != float) or current <= 0:
            raise ValueError("Diode current must be a positive, non-zero number!")

        response = self._send_command("DC " + str(current))
        if response == b"ok\r\n":
            self.diodeCurrent = current
            self.energyMode = 0 # Whenever diode current is adjusted manually, the energy mode is set to manual.
            return True
        raise LaserCommandError(Laser.get_error_code_description(response))

    def laser_reset(self):
        """This command resets all laser variables to default.
        
        Returns
        -------
        valid : bool
            If the command sent to the laser was processed properly, this should show as True. Otherwise an error will be raised.
        """
        responce = self._send_command('RS')
        if responce == b'ok\r\n':
            self.editConstants()    # Refreshing all constants back to their default states if response is valid
            return True
        raise LaserCommandError(Laser.get_error_code_description(responce))

    def update_settings(self):
        """Updates laser settings"""
        cmd_strings = list()
        cmd_strings.append('RR ' + str(self.repRate))
        cmd_strings.append('BC ' + str(self.burstCount))
        cmd_strings.append('DC ' + str(self.diodeCurrent))
        cmd_strings.append('EM ' + str(self.energyMode))
        cmd_strings.append('PM ' + str(self.pulseMode))
        cmd_strings.append('DW ' + str(self.pulseWidth))
        cmd_strings.append('DT ' + str(self.pulseMode))

        for i in cmd_strings:
            self._send_command(i)

    @staticmethod
    def get_error_code_description(code):
        """
        A function used to understand what the incoming error from our laser represents
        """
        if not code:
            return "No response received from laser in time."
        
        if code == b'?1\r\n':
            return "Command not recognized."
        elif code == b'?2\r\n':
            return "Missing command keyword."
        elif code == b'?3\r\n':
            return "Invalid command keyword."
        elif code == b'?4\r\n':
            return "Missing Parameter"
        elif code == b'?5\r\n':
            return "Invalid Parameter"
        elif code == b'?6\r\n':
            return "Query only. Command needs a question mark."
        elif code == b'?7\r\n':
            return "Invalid query. Command does not have a query function."
        elif code == b'?8\r\n':
            return "Command unavailable in current system state."
        else:
            return "Error description not found, response code given: " + str(code)

def list_available_ports():
    return serial.tools.list_ports.comports()
