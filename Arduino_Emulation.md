# Arduino Emulation
Within this repository is also a [Arduino .ino code](https://github.com/Student-Space-Programs-Laboratory/py-ujlaser/blob/master/arduino-spoof/ujlaser_emulator/ujlaser_emulator.ino) file that provides a near approximation of the behaviour of a MicroJewel laser.

This is by no means a perfect emulation, and certainly has flaws, but this is still a useful tool to have when waiting to test software. Live firing a laser can be a difficult and rare opportunity, so any chance to further test code without the restrictions of physical access to the laser is a help. 

`ujlaser_emulator.ino` was created without ANY knowledge of the source code/firmware of MicroJewel laser and was created using trial-and-error through the python test benches. The process we used to create the `ujlaser_emulator.ino` file was:
1. Create new test case on test bench
2. Adjust test bench until the MicroJewel laser passes the test bench
3. Adjust the `.ino` file until the Arduino UNO also passes the test bench
4. Repeat steps 1-3 until all desired commands and error cases have been implemented.

Not all commands are implemented in the emulation file. Saving and loading user settings and user shot counts is not implemented.

The code was written for an Arduino UNO, using the below schematic. A toggle switch is used to represent the external interlock connection, and the red LED indicates when the laser is "active"/firing.

The serial commands and responses to the Arduino UNO are almost identical to that of an actual MicroJewel laser. Including the error codes and number of digits after the decimal point for query commands.
