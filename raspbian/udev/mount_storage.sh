#!/bin/bash
# DEVNAME - aka /dev/sdb
# $1 - mount point name
MPOINT=$1

function log() {
    echo $1 | logger -t mount_storage
}

function mk_fs() {
	dev=$1
	log "cleaning $dev"
	dd if=/dev/zero of=$dev bs=1024 count=100
	log "make fs $dev"
	mkfs.ext4 $dev
	return $?
}


if [ "$DEVNAME" = "" ]; then
    log "no device name"
    exit 0
fi

if [ "$MPOINT" = "" ]; then
    log "no mount point name"
    exit 0
fi


log "run USB storage mounting $DEVNAME $MPOINT"

log "run fsck $DEVNAME"
fsck -y $DEVNAME
if [ "$?" != "0" ]; then
	log "fsck error"
	mk_fs $DEVNAME
	if test "$?" != "0"; then
		log "can't mkfs"
		exit 0
	fi
fi

log "mount $DEVNAME $MPOINT"
mount $DEVNAME $MPOINT
if [ "$?" == "0" ]; then
    log "success"
    /home/stelhs/temp/remount_overlay.sh
    exit 0
fi

log "can't mount $DEVNAME"

