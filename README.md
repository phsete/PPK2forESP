# PPK2 for ESP
Toolkit to measure power consumption of ESP devices with Nordic Semiconductors PPK2

## Known Bugs
* PPK2 device does not reset the serial interface after a flash resulting in the next reading being doubled
* NTP request fails sometimes with:
```ntplib.NTPException: No response received from europe.pool.ntp.org```