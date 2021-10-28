### **Client UI Improvements**
 Updated on version [0.45](/release-notes/0.45.0)**

Starting with version 0.45 we've made some exciting changes to the client user interface to allow users to be able to further customize Hummingbot to their liking. 

- Adjusted default panel colors to create a division between the input pane and log pane
- Changed top panel text colors including paper trade mode indicator
- Added global configuration parameters allowing users to specify and customize colors inside the client terminal (`top-pane`, `bottom-pane`, `output-pane`, `input-pane`, `logs-pane`, `terminal-primary`)

![New Hummingbot UI](/assets/img/new-ui-1.png)

1. Top pane 
2. Output pane 
3. Input pane 
4. Bottom pane  
5. Logs pane 
6. Toggle for opening / closing the log pane or press `CTRL + T`  


### Changing the panel colors
To make changes to the panel colors, edit the `config_global.yml` file to specify the colors for each of the panes.

!!! note
    A hex color code is a 6-symbol code made of up to three 2-symbol elements. Each of the 2-symbol elements expresses a color value from 0 to 255. The code is written using a formula that turns each value into a unique 2-digit alphanumeric code. For example, the RGB code (224, 105, 16) is E06910 in hexadecimal code

!!! tip 
    You can use a hexadecimal color picker like the one here to choose colors - https://www.w3schools.com/colors/colors_picker.asp   

```
# Background color of the top pane
top-pane: '#000000'

# Background color of the bottom pane
bottom-pane: '#000000'

# Background color of the output pane
output-pane: '#282C2F'

# Background color of the input pane
input-pane: '#151819'

# Background color of the logs pane
logs-pane: '#151819'

# Terminal primary color (text)
terminal-primary: '#00FFE5'

```

!!! tip
     Press `CTRL + R` to reset the style to use default colors

