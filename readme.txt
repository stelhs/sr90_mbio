Configuring Raspberry Pi:
1) Install minimal image 2021-10-30-raspios-bullseye-armhf-lite.zip
    cat 2021-10-30-raspios-bullseye-armhf-lite.zip | funzip | sudo dd of=/dev/mmcblk0 bs=4M conv=fsync status=progress

2) run raspi-config and enable: sshd, w1-bus. set locale and timezone
3) install:
    vim
    lnav
    git
    screen

4) Set root password:
    sudo passwd

5) /etc/ssh/sshd_config: add
    PermitRootLogin yes

6) setup /etc/hostname

7) tear off two resistors on I2C bus

8) /boot/config.txt add:
    dtoverlay=w1-gpio,gpiopin=4

9) setup ip address:
    /etc/dhcpcd.conf add:

    interface enxb827ebb4ab83
    static ip_address=192.168.10.4
    static routers=192.168.10.1
    static domain_name_servers=8.8.8.8
    static domain_search=8.8.8.8

10) clone sources https://github.com/stelhs/sr90_mbio.git into /root/sr90_mbio
11) setup .gpios.json, .mbio_name, .server.json
    cp /root/sr90_mbio/defaults/.* /root/sr90_mbio

12) /etc/rc.local add:
        sleep 10
        cd /root/sr90_mbio
        screen -dmS mbio
        screen -S mbio -X screen python3 -i mbio.py
