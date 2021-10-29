# Color Settings

Starting with version 0.45, we added new global configuration parameters that allows users to customize the client's background colors.

![New Hummingbot UI](/assets/img/new-ui-1.png)

1. `top-pane` 
2. `output-pane` 
3. `input-pane` 
4. `bottom-pane`  
5. `log-pane`
6. `terminal-primary`


## Changing the panel colors

To make changes to the panel colors, run `config [parameter_name]` inside the Hummingbot client. For example, the command for changing the log pane color is `config log-pane` and enter the hex code of the desired color.

!!! tip 
    You can use a hexadecimal color picker like the one here to choose colors: https://www.w3schools.com/colors/colors_picker.asp

Alternatively, you can edit these values in the `conf_global.yml` file using a text editor.


## Reset colors to default

Press `CTRL + R` while inside Hummingbot to reset the style to use its default colors.

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
