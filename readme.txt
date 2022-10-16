Configuring Raspberry Pi:
1) Install minimal image 2021-10-30-raspios-bullseye-armhf-lite.zip
    cat 2021-10-30-raspios-bullseye-armhf-lite.zip | funzip | sudo dd of=/dev/mmcblk0 bs=4M conv=fsync status=progress

2) run raspi-config and enable: sshd, w1-bus. set locale, timezone and overlay-fs

3) Configure overctl utility
    3.1) cp raspbian/overctl /usr/local/sbin
         chmod +x /usr/local/sbin/overctl
         cp /boot/cmdline.txt /boot/cmdline.txt.orig
         cp /boot/cmdline.txt /boot/cmdline.txt.overlay

    3.2) Add option boot=overlay itno file cmdline.txt.overlay

4) enable overlay-fs with RO rootfs + RW tmpfs and reboot
    after booting switch to RW:
        overctl -w
    and reboot

5) install:
    aptitude
    telnet
    vim
    lnav
    git
    screen

6) Set root password:
    sudo passwd

7) /etc/ssh/sshd_config: add
    PermitRootLogin yes

8) setup /etc/hostname

9) tear off two resistors on I2C bus

10) Turn off the RPi and remove the DS card. Insert the SD card into another PC and
    create a new partiton with at least 2048Mb of tail space.

    Turn on the RPi and configure /etc/fstab for mounting a
    new partition to the /root folder with RW access.


11) /boot/config.txt and add:
    run: mount -o remount,rw /boot

    add to files: dtoverlay=w1-gpio,gpiopin=4

    run: mount -o remount,ro /boot


12) automount USB storage and ttyUSB
    mkdir /storage
    scp raspbian/udev/80-usb_storage.rules root@192.168.10.103:/etc/udev/rules.d/
    scp raspbian/udev/mount_storage.sh root@192.168.10.103:/etc/udev/rules.d/
    scp raspbian/udev/umount_storage.sh root@192.168.10.103:/etc/udev/rules.d/
    scp raspbian/udev/set_tty_usb_speed.sh root@192.168.10.103:/etc/udev/rules.d/

    mkdir /etc/systemd/system/systemd-udevd.service.d
    scp raspbian/udev/enable_mounting.conf root@192.168.10.103:/etc/systemd/system/systemd-udevd.service.d/

    rename /etc/udev/rules.d/99-com.rules to /etc/udev/rules.d/90-com.rules
    scp raspbian/udev/91-tty_usb_speed.rules root@192.168.10.103:/etc/udev/rules.d/

    sudo systemctl daemon-reload
    sudo udevadm control --reload


13) vim ~/.bashrc
        alias gst='git status'
        alias gl='git log'
        alias ga='git add'
        alias gc='git commit -m'
        alias gp='git pull --rebase && git push'
        alias gull='git pull --rebase'
        alias gush='git push'
        alias gb='git branch'
        alias gco='git checkout'
        alias gd='git diff'


14) vim ~/.vimrc
        set mouse-=a
        syntax on


15) vim ~/.screenrc
        vbell off


16) Set static IP /etc/dhcpcd.conf
        interface eth0
        static ip_address=192.168.10.200/24
        static routers=192.168.10.1
        static domain_name_servers=192.168.10.1 8.8.8.8


17) clone sources
    cd /root
    git clone https://github.com/stelhs/sr90_mbio.git
    cd sr90_mbio
    git checkout redesign_for_new_skynet
    git clone https://github.com/stelhs/sr90lib.git
    git clone https://github.com/stelhs/mbio_config.git configs
    cd configs
    git checkout mbio4


18) /etc/rc.local add:
        sleep 4
        screen -dmS mbio bash -c "cd /root/sr90_mbio; python3 -i mbio.py; exec bash"
        echo heartbeat >  /sys/class/leds/led0/trigger

19) vim /etc/ssh/sshd_config and add:
        GSSAPIAuthentication no
        UseDNS no

20) vim /etc/default/keyboard
        XKBLAYOUT=”us”
