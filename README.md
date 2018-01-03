# Windcentrale
**Beta!!!**
## Why?
The standard 'Winddelen' device only displays the current power of the windmill. This device gives you more detailed information about the production off the windmill, like current power, energy produced this year, windspeed, rotation speed, etc. 
## Parameters
Parameters are the same as for the Winddelen device:

| Parameter | Description |
| :--- | :--- |
| **Select a mill** | eg. De Grote Geert, etc |
| **Number of winddelen** | The number of wind shares ("Winddelen") you own |
## Devices
The following 9 units are created:

| Name | Description |
| :--- | :--- |
| **Power (you)** | The current power provided for your wind shares |
| **Power (total)** | The power the windmill currently producing in total |
| **Relative** | The relative power of the windmill against the maximum power |
| **Energy (you)** | The total energy this windmill has produced this year for your wind shares |
| **Energy (total)** | The total energy the windmill has produced this year |
| **Windspeed** | Measured current windspeed on the location of the windmill |
| ~~**Winddirection**~~ | ~~Current wind direction~~ |
| **RPM** | Rotation speed of the windmill |
| **Operational time** | The percentage of up-time of the windmill, since the beginning |
| **Hours** | Hours up-time this year |
## To do
- [ ] Add polling time (now every minute)
- [ ] Add 'Wind direction'. Didn't found a way to display this. The standard 'Wind' device, also display the wind speed in m/s. But we get only the wind speed in bft from windcentrale :(
- [ ] Add possibility to see the results from multiple windmills?
