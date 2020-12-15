# ujLaser
This library provides programmatic control of a QuantumComposers MicroJewel laser using the USB serial interface.	
# Requirements
This code has been tested on Python 3.5.
The only other external library required is the `pyserial` library, which can be installed by running:
`pip install -r requirements.txt`

# Installation
To install `ujlaser` onto your system:
- Git clone the repository
- `cd` into the directory
- Run `pip install .`

# Utilities
This repository also has a few useful scripts and programs that may be helpful when developing an application that uses a MicroJewel laser.

Look in the `arduino-spoof` directory and [Arduino_Emulation.md](https://github.com/Student-Space-Programs-Laboratory/py-ujlaser/blob/master/Arduino_Emulation.md) for information about how to setup an Arduino UNO to mimic the behavior of an actual MicroJewel laser.

`tools/laser_terminal.py` is a simple python3 script that provides an interactive shell that pipes the user input and output straight to the selected serial port. See the script for further usage instructions.

# Contributors
- Miles Greene
- Noah Chaffin
- Tyler Sengia

# Disclaimer
The library is not built, endorsed, tested, verified, insured, etc. by Quantum Composers. This library was built by users of the Quantum Composers MicroJewel laser products. We (the authors and contriubutors of this code) are NOT liable for ANY and ALL damages, injuries, costs, etc. created from using this code. Please read the COPYING.txt for the full legal agreement you undertake when using this software.
