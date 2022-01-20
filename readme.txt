Configuring Raspberry Pi:
1) install:
    aptitude
    lnav
    screen

2) setup /etc/hostname

3) /etc/ssh/sshd_config: add
    PermitRootLogin yes

2) tear off two resistors on I2C bus

3) /boot/config.txt add:
        dtoverlay=w1-gpio
        dtparam=gpiopin=4

4) setup ip address:
    /etc/dhcpcd.conf add:

    interface enxb827ebb4ab83
    static ip_address=192.168.10.84
    static routers=192.168.10.1
    static domain_name_servers=8.8.8.8
    static domain_search=8.8.8.8

5) clone sources into /root/sr90_mbio
6) setup .gpios.json, .mbio_name, .server.json
7) /etc/rc.local add:
        cd /root/sr90_mbio
        screen -dmS mbio
        screen -S mbio -X screen python3 -i mbio.py
