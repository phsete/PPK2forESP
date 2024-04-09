# PPK2 for ESP
Toolkit to measure power consumption and log events of ESP32 devices with Nordic Semiconductors PPK2.

## Usage
### Integrate a new Device that should be measured
1. Connect a Power Profiler Kit II and a ESP32-Dev-Board to any computing device able to execute Python scripts.
2. Conenct the Power Profiler Kit II to the power measurement pins of the Dev-Board.
3. Execute the node.py script on the computing device.

### Configuration
1. Make sure a valid GitHub Repository and Personal Access Token is entered in the config.toml file. This Token must allow access to the releases of the ESP-Firmware.
> An example Repository with a valid GitHub Action for creating the needed releases can be found under [https://github.com/phsete/ESPNOWLogger](https://github.com/phsete/ESPNOWLogger).
2. Configure the nodes.save file for every node that should be measured.
    * Every line represents a single node.
    * Syntax per line: `(UUID_OF_NODE[string],NODE_NAME[string],NODE_IP[string],CONNECTED_TO_PI[boolean],RELEASE_VERSION[string],TYPE[sender|receiver],PROTOCOL[string],SLEEP_MODE[string],POWER_SAVE_MODE[string])`
    * Example: `(d46c204b-b90a-4ef8-9b28-5a8f67021fef,Sensor,127.0.0.1,True,v0.2.8-f7c4323,sender,ESP_NOW,NO_SLEEP,EXAMPLE_POWER_SAVE_NONE)`
    > A example of this configuration is given with the `nodes_example.save` file.

### Start Test
1. Execute the `cli.py` script on any available device. If you need help with the syntax, simply call `cli.py --help` or `cli.py run --help`.

### View Results
1. Configure the options on the top of the viewer script.
2. Execute the `viewer.py` script and make sure that the result files are in the same folder.
3. Select a result group by entering the number stated in the output.
4. The detailled power consumption of each cycle is printed in the log.
5. A browser should open with an interactive graph of the results.
> Hint: You can save a picture of the currently shown graph by clicking on the camera at the top right of the browser view.

## Known Bugs
* _(currently not used)_ NTP request fails sometimes with:
```ntplib.NTPException: No response received from europe.pool.ntp.org```
* sometimes not every event of the ESP32 is logged
* longer runs lead to a crash of the script running out of memory

# Context
The contents of this repository where created mainly during the creation of a master thesis at Technische Universität Dortmund - Fakultät für Informatik - Lehrstuhl für eingebettete Systeme, AG Systemsoftware (LS-12).

More details in german can be found under the title of the thesis: "Evaluation drahtloser Kommunikationsverfahren von eingebetteten Sensorknoten am Beispiel eines Bodenfeuchtesensors" (not yet available).

If you want to use the presented code in your own thesis or want to expand it and have any questions about it, feel free to [contact me on 	
&#120143; (formerly Twitter) @philteb](https://twitter.com/philteb) or any other way you can find my contact information.

&copy; 2024 Philipp Sebastian Tebbe