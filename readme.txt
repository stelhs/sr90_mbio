Configuring Raspberry Pi:
1) Install minimal image 2021-10-30-raspios-bullseye-armhf-lite.zip
    cat 2021-10-30-raspios-bullseye-armhf-lite.zip | funzip | sudo dd of=/dev/mmcblk0 bs=4M conv=fsync status=progress

2) install:
    aptitude
    vim
    lnav
    git
    screen

3) setup /etc/hostname

4) /etc/ssh/sshd_config: add
    PermitRootLogin yes

5) tear off two resistors on I2C bus

6) /boot/config.txt add:
    dtoverlay=w1-gpio,gpiopin=4

7) setup ip address:
    /etc/dhcpcd.conf add:

    interface enxb827ebb4ab83
    static ip_address=192.168.10.4
    static routers=192.168.10.1
    static domain_name_servers=8.8.8.8
    static domain_search=8.8.8.8

8) clone sources https://github.com/stelhs/sr90_mbio.git into /root/sr90_mbio
9) setup .gpios.json, .mbio_name, .server.json
    cp /root/sr90_mbio/defaults/.* /root/sr90_mbio

10) /etc/rc.local add:
        cd /root/sr90_mbio
        screen -dmS mbio
        screen -S mbio -X screen python3 -i mbio.py
