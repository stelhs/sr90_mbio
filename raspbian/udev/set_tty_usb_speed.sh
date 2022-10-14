#!/bin/bash

function log() {
    echo $1 | logger -t set_tty_usb_speed
}

DEVNAME=/dev/`basename $DEVPATH`

if [ "$DEVNAME" = "" ]; then
    log "no device name"
    exit 0
fi

log "set speed 115200 for $DEVNAME"
stty 115200 cs8 -F $DEVNAME

