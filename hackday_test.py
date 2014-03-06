#!/usr/bin/python

# Imports for reading SPI data from MCP3008 ADC converter
import spidev

# Imports for working with LCD
from Adafruit_CharLCD import Adafruit_CharLCD

import json
import os
import RPi.GPIO as GPIO
import random
import requests
import spidev
import string
import sys
import time

ADC_VREF = 3.3
ADC_NUM_LEVELS = 1024
MACHINE_ROLE_CHANNEL = 0
ENVIRONMENT_CHANNEL = 1
button_pin = 18
UNKNOWN_MACHINE_ROLE = 'unknown role'
UNKNOWN_ENVRONMENT = 'unknown env'
FAKE_MODE = os.getenv('FAKE_MODE') == 'true' or False

# Set up GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(button_pin, GPIO.IN)

class FakeLCD:
    def clear(self):
        return None
        
    def message(self, msg):
        print "[LCD] %s" % msg

class FakeSPI:
    def __init__(self):
        self.channels = { '0': open('spi_channel_0', 'w+'),
                          '1': open('spi_channel_1', 'w+') }
        self.channel_values = { '0': 0, '1': 0 }

    def read_adc_level(self, channel):
        val = self.channels[str(channel)].readline().rstrip()
        if not val == '':
            self.channel_values[str(channel)] = int(val)
        return self.channel_values[str(channel)]

    def close(self):
        self.channels['0'].close
        self.channels['1'].close
        
if FAKE_MODE:
  lcd = FakeLCD()
  spi = FakeSPI()
else:  
  # Open SPI bus
  spi = spidev.SpiDev()
  spi.open(0, 0)

  # LCD configuration
  lcd = Adafruit_CharLCD()
  lcd.begin(16,1)

# API machine roles that can be provisioned.
MACHINE_ROLES = list(reversed([ 'infra_bare',
                                'provisioning_api',
                                'puppetmaster',
                                'puppetdb',
                                'logstash_server',
                                'mysql_server' ]))

# API environment names.
ENVIRONMENTS = list(reversed([ 'development',
                               'qa',
                               'uat',
                               'staging',
                               'production',
                               'infra_dev1' ]))

# Spaces out the ADC reading range (10 bit ADC = 1024 levels)
# into upper reading thresholds for the requested number of positions.
def adc_reading_thresholds(num_positions):
    increment =  float(ADC_NUM_LEVELS) / (num_positions - 1)
    thresholds = []
    for level in range(0, num_positions):
        threshold = (level * increment) + (increment / 2.0)
        thresholds.append(threshold)
    return thresholds

# Function to read SPI data from MCP3008 chip.
# Note: Channel must be an integer 0-7
def read_adc_level(channel):
    adc_level = 0
    if FAKE_MODE:
        adc_level = spi.read_adc_level(channel)
    else:
        r = spi.xfer2([1, (8 + channel) << 4, 0])
        adc_level = ((r[1]&3) << 8) + r[2]

    print("ADC Reading (%d) = %d, Volts = %f" % (channel, adc_level, reading_level_to_volts(adc_level)))
    return adc_level
            

# Convert ADC reading level to a voltage (to a specified number of decimal places).
def reading_level_to_volts(reading_level, places=2):
    volts = reading_level * ADC_VREF / ADC_NUM_LEVELS
    volts = round(volts, places)
    return volts

# Determine index in a thresholds array from a specified ADC reading level.
def position_from_reading_level(thresholds, reading_level):
    for i in range(0, len(thresholds)):
        if (reading_level < thresholds[i]):
            return i
    return -1

machine_role_reading_thresholds = adc_reading_thresholds(len(MACHINE_ROLES))
environment_reading_thresholds = adc_reading_thresholds(len(ENVIRONMENTS))

# Get the selected machine role via an ADC reading.
def selected_machine_role():
    reading_level = read_adc_level(MACHINE_ROLE_CHANNEL)
    position = position_from_reading_level(machine_role_reading_thresholds, reading_level)
    if (position >= 0):
        return MACHINE_ROLES[position]
    else:
        return UNKNOWN_MACHINE_ROLE

# Get the selected environment via an ADC reading.
def selected_environment():
    reading_level = read_adc_level(ENVIRONMENT_CHANNEL)
    position = position_from_reading_level(environment_reading_thresholds, reading_level)
    if (position >= 0):
        return ENVIRONMENTS[position]
    else:
        return UNKNOWN_ENVIRONMENT

def WaitForButtonStateChange():
    original_state = GPIO.input(button_pin)
    while True:        
        button_state = GPIO.input(button_pin)
        if (button_state != original_state):
            return button_state
        time.sleep(0.1)

def GetRandomMachineName():
    chars = [random.choice(string.ascii_letters) for n in xrange(6)]
    return "hackday-" + "".join(chars) + ".hq.local"

def DoStuff():
    machine_name = GetRandomMachineName()
    request_body = json.dumps({"machine_role":selected_machine_role(), "environment":selected_environment()})
    definition_url = "http://provisioner-dev.hq.local:8080/v1/node/" + machine_name + "/definition"
    instance_url = "http://provisioner-dev.hq.local:8080/v1/node/" + machine_name + "/instance"

    print("Creating definition: " + definition_url)
    print("Request Body: " + request_body)
    definition_response = requests.put(definition_url, request_body)
    if (definition_response.status_code != 201):
        print("Could not create definition: {}".format(definition_response.text))
        exit
    print("Definition created.")

    print("Provisioning instance: ")
    instance_response = requests.put(instance_url, '')
    if instance_response.status_code != 202:
        print "Could not provision instance."
        exit

    print("Provisioning instance...")
    instance_status = "provision_pending"
    while instance_status in ["provision_pending", "provisioning"]:
        get_response = requests.get(instance_url)
        response_hash = get_response.json()
        instance_status = response_hash['status']
        print("  Status: {}".format(instance_status))
        time.sleep(5)
        
    print("Instance provisioned for {}.".format(machine_name))


try:
    print 'FAKE_MODE = ' + str(FAKE_MODE)
    
    while True:
##        print "-------------------------------------------"
##        machine_role = selected_machine_role()
##        environment = selected_environment()
##        lcd.clear()
##        lcd.message("E: %s\n" % environment)
##        lcd.message("R: %s" % machine_role)
##        print "-------------------------------------------"
##        time.sleep(2)

     button_state = WaitForButtonStateChange()
        if (button_state == 0):
            DoStuff()

        
finally:
    if FAKE_MODE:
        spi.close()

print 'Done.'