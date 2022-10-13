systemctl restart systemd-udevd
sudo systemctl restart udev.service
sudo service systemd-udevd --full-restart
sudo udevadm control --reload

udevadm info -a -p /block/sdb
sudo udevadm monitor --environment

vim /etc/udev/rules.d/00-usb_storage.rules

/etc/systemd/system/systemd-udevd.service.d/enable_mounting.conf
[Service]
MountFlags=shared
PrivateMounts=no

sudo systemctl daemon-reload

