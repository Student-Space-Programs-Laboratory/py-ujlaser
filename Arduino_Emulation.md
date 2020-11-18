# Arduino Emulation
Within this repository is also a Arduino .ino code file that provides a near approximation of the behaviour of a MicroJewel laser.

This is by no means a perfect emulation, and certainly has flaws, but this is still a useful tool to have when waiting to test software. Live firing a laser can be a difficult and rare opportunity, so any chance to further test code without the restrictions of physical access to the laser is a help.

The code was written for an Arduino UNO, using the below schematic. A toggle switch is used to represent the external interlock connection, and the red LED indicates when the laser is "active"/firing.

The serial commands and responses to the Arduino UNO are almost identical to that of an actual MicroJewel laser. Including the error codes and number of digits after the decimal point for query commands.
