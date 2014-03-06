#!/bin/sh

CHANNEL=$1
VAL=$2

echo "Sending ADC level $VAL to channel SPI $CHANNEL"
echo $VAL >> "spi_channel_$CHANNEL" 
