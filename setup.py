from setuptools import setup

setup(
    name='ujlaser',
    version='1.0',
    description='Library to control a Quantum Composers MicroJewel Laser.',
    url='https://github.com/Student-Space-Programs-Laboratory/py-ujlaser',
    author='Miles Green, Noah Chaffin, Tyler Sengia',
    author_email='tylersengia@gmail.com',
    license='CC0',
    packages=['ujlaser'],
    install_requires=['pyserial>=3.0'],
    classifiers=['Programming Language :: Python :: 3',
                 'Programming Language :: Python :: 3.5'],
)
