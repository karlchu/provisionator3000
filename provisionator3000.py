#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import os
import RPi.GPIO as GPIO
import random
import requests
import spidev
import string
import sys
import time


# Define sensor channels
machine_role_channel = 0
environment_channel = 1
button_pin = 18

# Set up GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(button_pin, GPIO.IN)

# Open SPI bus
spi = spidev.SpiDev()
spi.open(0,0)

def GetPositionThresholdArray(position_count):
    incr = 1023.0 / (position_count - 1)
    thresholds = []
    for pos in range(0, position_count):
        threshold = (pos * incr) + (incr / 2)
        thresholds.append(threshold)
    return thresholds

machine_roles = ['infra_bare',
                 'provisioning_api',
                 'puppetdb',
                 'puppetmaster',
                 'logstash_server',
                 'mysql_server',
                 'yum_server'
                 ]
environments = ['infra_dev1',
                'infra_dev2',
                'development',
                'qa',
                'uat',
                'staging',
                'production'
                ]

machine_role_threshold_array = GetPositionThresholdArray(len(machine_roles))
environment_threshold_array = GetPositionThresholdArray(len(environments))

# Function to read SPI data from MCP3008 chip
# Channel must be an integer 0-7
def ReadChannel(channel):
    adc = spi.xfer2([1,(8+channel)<<4,0])
    data = ((adc[1]&3) << 8) + adc[2]
    return data

# Function to convert data to voltage level,
# rounded to specified number of decimal places.
def ConvertVolts(data,places):
    volts = (data * vref) / 1023
    volts = round(volts,places)
    return volts

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

def GetPositionByLevel(threshold_array, level):
    for i in range(0, len(threshold_array)):
        if (level < threshold_array[i]):
            return i

def GetMachineRole():
    level = ReadChannel(machine_role_channel)
    return machine_roles[GetPositionByLevel(machine_role_threshold_array, level)]

def GetEnvironment():
    level = ReadChannel(environment_channel)
    return environments[GetPositionByLevel(environment_threshold_array, level)]

def DoStuff():
    machine_name = GetRandomMachineName()
    request_body = json.dumps({"machine_role":GetMachineRole(), "environment":GetEnvironment()})
    definition_url = "http://provisioner-dev.hq.local:8080/v1/node/" + machine_name + "/definition"
    instance_url = "http://provisioner-dev.hq.local:8080/v1/node/" + machine_name + "/instance"

    print("Creating definition: " + definition_url)
    print("Request Body: " + request_body)
##    definition_response = requests.put(definition_url, request_body)
##    if (definition_response.status_code != 201):
##        print("Could not create definition: {}".format(definition_response.text))
##        exit
##    print("Definition created.")
##
##    print("Provisioning instance: ")
##    instance_response = requests.put(instance_url, '')
##    if instance_response.status_code != 202:
##        print "Could not provision instance."
##        exit
##
##    print("Provisioning instance...")
##    instance_status = "provision_pending"
##    while instance_status in ["provision_pending", "provisioning"]:
##        get_response = requests.get(instance_url)
##        response_hash = get_response.json()
##        instance_status = response_hash['status']
##        print("  Status: {}".format(instance_status))
##        time.sleep(5)
##        
##    print("Instance provisioned for {}.".format(machine_name))

while True:
    button_state = WaitForButtonStateChange()
    if (button_state == 0):
        DoStuff()
