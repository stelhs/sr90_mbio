Configuring Raspberry Pi:
1) Install minimal image 2021-10-30-raspios-bullseye-armhf-lite.zip
    cat 2021-10-30-raspios-bullseye-armhf-lite.zip | funzip | sudo dd of=/dev/mmcblk0 bs=4M conv=fsync status=progress

2) run raspi-config and enable: sshd, w1-bus. set locale and timezone

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

10) /boot/config.txt and add:
    run: mount -o remount,rw /boot

    add to files: dtoverlay=w1-gpio,gpiopin=4

    run: mount -o remount,ro /boot


11) automount USB storage
    mkdir /storage
    scp raspbian/udev/80-usb_storage.rules root@192.168.10.103:/etc/udev/rules.d/
    scp raspbian/udev/mount_storage.sh root@192.168.10.103:/root/
    scp raspbian/udev/umount_storage.sh root@192.168.10.103:/root/

    mkdir /etc/systemd/system/systemd-udevd.service.d
    scp raspbian/udev/enable_mounting.conf root@192.168.10.103:/etc/systemd/system/systemd-udevd.service.d/

    sudo systemctl daemon-reload
    sudo udevadm control --reload


12) vim ~/.bashrc
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

13) vim ~/.vimrc
        vim ~/.vimrc


14) Задать статический IP адрес
    setup ip address:
    /etc/dhcpcd.conf add:

    interface enxb827ebb4ab83
    static ip_address=192.168.10.4
    static routers=192.168.10.1
    static domain_name_servers=8.8.8.8
    static domain_search=8.8.8.8

15) clone sources
    cd /root
    git clone https://github.com/stelhs/sr90_mbio.git
    cd sr90_mbio
    git checkout redesign_for_new_skynet
    git clone https://github.com/stelhs/sr90lib.git
    git clone https://github.com/stelhs/mbio_config.git configs
    cd configs
    git checkout mbio4

16) setup .gpios.json, .mbio_name, .server.json
    cp /root/sr90_mbio/defaults/.* /root/sr90_mbio

17) /etc/rc.local add:
        sleep 10
        screen -dmS mbio bash -c "cd /root/sr90_mbio; python3 -i mbio.py; exec bash"


