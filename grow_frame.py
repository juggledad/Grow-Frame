"""
Last modified = 18th May 2023 by DjD

This version includes Paul's extended "bebug" code in sub_callback
added code to write "sensors", etc.. to node_details file
added code to handle msg "reset":"yes" in sub_callback

added code to change 'smart' single quotes to just single quotes
also added code in scan to ignore hidden SSIDs

Commented-out all the file.close() statements

Added the shutdown_time non-blocking delay back in - it had gone missing
Introduced default values for...
   deepsleep_dutaion,
   shutdown_time
   cycle_time
   my_mode
at top of the script

Uses new function to check received MQTT topic against user and nodeName
REMOVED the ability to use "all" as a user

Using revised format for mqtt topics

Inserted Paul's mod to read/write SSID with a leading blank-space

Changed pin usage on S2-Mini to match pin-positions on D1-Mini

Checks for 'hostname', 'deepsleep_duration' and 'shutdown_time'
and uses defaults if any of these parameters are missing.

Added "mode":<single> or <repeat>
Added "cycles":3
Added "cycle_time":15
Added "buttons":"yes"

This uses new MQTT topic formats
and "user" in node-Details.tx

Simplified the read/write network_details functions

Added 'top', 'bottom', 'remove' and 'network' commands
Added scan command

Commented-out print() statements and tidy-up code

Added code in sub_callback to handle... changing 'hostname' or 'ref'

Removed node_details from sensors dictionary
Expanded 'pub_sensor_values' to combine node_details

Added code to handle changing 'shutdown_time' and 'deepsleep_duration'

Added i2c.scan() to find BME280 address

This uses the new format for node_details.json

This uses a better pub_callback to check options in sequence

"""
print("\n\nRunning Grow Frame script - v55D_Thur.py")
import sys
sys.path.append("/settings") # Add path to User-defined stuff
print(sys.path)

import math
import network
import time
import ujson

from umqttsimple import MQTTClient

# from small_array  import myNetworks
from v5_mqtt_weatherstation_details import mqtt_server, mqtt_port, mqtt_user, mqtt_passwd, pub_feedback_topic, pub_debug_topic, pub_readings, sub_command

#print(pub_feedback_topic)
#print(pub_readings)

# import machine
from machine import SoftI2C, Pin, deepsleep
from bme280  import BME280

# User specified defaults ##############
default_deepsleep_duration = 30
default_shutdown_time = 4
default_cycle_time = 30
default_mode = "repeat" # "single" or "repeat"
default_report_sensors = "no"
default_report_buttons = "no"
default_report_analog  = "yes"

DEBUG = True
# Do not change anything below this line
########################################

def read_network_details():
    global myNetworks
    myNetworks = []
    with open('/settings/v5_networks.txt', 'r') as file:
        for line in file:
            row = line.split(':')
            row[1] = row[1].strip()
            myNetworks.append(row)
        #file.close()
    print(myNetworks)
        
def write_network_details():
    with open('/settings/v5_networks.txt', 'w') as file:
        for row in myNetworks:
            file.write(':'.join(row) + '\n')
        #file.close()

def read_node_details():
    global node_details
    with open("/settings/v5_node_details.json", "r") as file:
        node_details = dict(ujson.load(file))
        node_details["user"]     = node_details["user"].lower()
        node_details["nodeName"] = node_details["nodeName"].lower()
        node_details["location"] = node_details["location"].lower()
        node_details["type"]     = node_details["type"].lower()
        
        if node_details.get("hostname") is None:
            node_details["hostname"] = "unspecified"
        
        if node_details.get("deepsleep_duration") is None:
            node_details["deepsleep_duration"] = default_deepsleep_duration
            
        if node_details.get("shutdown_time") is None:
            node_details["shutdown_time"] = default_shutdown_time
            
        if node_details.get("sensors") is None:
            node_details["sensors"] = default_report_sensors
        
        if node_details.get("buttons") is None:
            node_details["buttons"] = default_report_buttons
            
        if node_details.get("analog") is None:
            node_details["analog"] = default_report_analog
            
        #file.close()
        print(node_details)
   
def write_node_details():
    global node_details
    with open("/settings/v5_node_details.json", "w") as file:
        ujson.dump(node_details, file)
        #file.close()

def row_ssid_is_in_myNetworks(ssid):
    for row in range (len(myNetworks)):
        if myNetworks[row][0] == ssid:
            print("Found target value in column 0!")
            return row
            break
    else:
        print("Target value not found in column 0.")
        return -1
   
def force_deepsleep(): # There was a problem, so go to sleep and try again
    print("Going into forced Deepsleep")
    time.sleep(2)
    deepsleep(10000) #Go to sleep for 10 secs
    
def find_a_network():
    global ssid
    network_found = False
    for row in range(len(myNetworks)):
        ssid = myNetworks[row][0]
        passwd = myNetworks[row][1]
        print("Trying connection to... ", ssid)
        wlan.connect(ssid, passwd)

        # Wait for connect or fail
        max_wait = 10
        print("Waiting for connection.", end="")
        while max_wait > 0:
            if wlan.isconnected():
                network_found = True
                break
            max_wait -= 1
            print(".", end="")           
            time.sleep(1)
            
        if network_found == True:
            break
        
    return network_found

def read_sensor_values():
    global sensors
    temp = float(bme.values[0][:-1])
    temp = temp * 10
    temp = math.floor(temp)
    temp = temp /10
    sensors["temp"] = temp
    
    humidity = float(bme.values[2][:-1])
    humidity = math.floor(humidity)
    sensors["humidity"] = humidity
    
    pressure = float(bme.values[1][:-3])
    pressure = math.floor(pressure)
    sensors["pressure"] = pressure

def read_button_values():
    pass

def read_analog_values():
    pass

def pub_network_details():
    json_data = ujson.dumps(myNetworks)
    mqtt_client.publish(publish_to_reading, json_data)

def pub_scan_results():
    json_data = ujson.dumps(network_data)
    json_data = json_data.replace("’", "'")  #change smart quotes to dumb ones
    mqtt_client.publish(publish_to_reading, json_data) #reading

def pub_sensor_values():
    # combine 'sensors' with 'node_details'
    combined = dict(sensors)
    combined["type"]     = node_details["type"]
    combined["nodeName"] = node_details["nodeName"]
    combined["location"] = node_details["location"]
    json_data = ujson.dumps(combined)
    mqtt_client.publish(publish_to_reading, json_data)

def pub_button_values():
    # combine 'buttons' with 'node_details'
    combined = dict(buttons)
    combined["type"]     = node_details["type"]
    combined["nodeName"]      = node_details["nodeName"]
    combined["location"] = node_details["location"]
    json_data = ujson.dumps(combined)
    mqtt_client.publish(publish_to_reading, json_data)

def pub_analog_values():
    # combine 'analog' with 'node_details'
    combined = dict(analog)
    combined["type"]     = node_details["type"]
    combined["nodeName"] = node_details["nodeName"]
    combined["location"] = node_details["location"]
    json_data = ujson.dumps(combined)
    mqtt_client.publish(publish_to_reading, json_data)
    
def pub_node_settings():
    # Convert the dictionary to a JSON-formatted string
    json_data = ujson.dumps(node_details)
    mqtt_client.publish(publish_to_reading, json_data)
    #print("Pub node settings")
    
def pub_feedback(message):
    json_data = ujson.dumps({"nodeRef": node_details["nodeName"],"message": message})
    mqtt_client.publish(publish_to_feedback, json_data)  # <<<<< Note for Paul
    
def pub_debug(message):
    json_data = ujson.dumps({"message": message})
    mqtt_client.publish(publish_to_debug, json_data)  
    
def check_received_topic(topic):
    match_found = False
    print("topic:", topic)
    
    topic_parts = topic.split('/')
    num_parts = len(topic_parts)
    if num_parts == 4:
        user_part = topic_parts[2].lower()
        node_part = topic_parts[3].lower().rstrip("'")
        
        print("user_part: ", user_part)
        print("node_part: ", node_part)
        
        if user_part == node_details["user"]:
            print("User details match")
            print("node_part : ", node_part)
            
            if (node_part == "all") or (str(node_part) == node_details["nodeName"]):
                print("Node details match")
                match_found = True    

            clear_command_topic = "weatherStation/command"+"/"+user_part+"/"+node_part
            print("clear_command_topic:",clear_command_topic)
            mqtt_client.publish(clear_command_topic, '') #clear out command

    else:
        pub_feedback("Command has incorrect number of parameters")

    return match_found

def sub_callback(topic, msg):
    global node_details
    global shutdown_sequence
    global network_data
    global DEBUG

#    DEBUG = False
    
    print("DEBUG IS:", DEBUG)
    if DEBUG: print("Topic is: ", topic)
    if DEBUG: print("Msg is: ", msg)
    
    #exit if payload is empty
    if msg == b'': return #exit if payload is empty

    if check_received_topic(str(topic)) == True:
        if DEBUG: print("Got the command")
        if DEBUG: print("msg: ", msg)
        message = dict(ujson.loads(msg.decode("utf-8")))  
        write_to_flash = False

        if message.get("debug") is not None:
            node_details["debug"] = message["debug"]
            DEBUG = message["debug"]
            if DEBUG: print("in DEBUG")
            shutdown_sequence = "disabled"
            if DEBUG: print("Shutdown sequence - stopped")
            pub_feedback(str("DEBUG is "+DEBUG))
            write_to_flash = True

        if message.get("stop") is not None:
            if DEBUG: print("in STOP")
            shutdown_sequence = "disabled"
            if DEBUG: print("Shutdown sequence - stopped")
            pub_feedback("Shutdown sequence stopped")
            
        if message.get("scan") is not None:
            if DEBUG: print("in SCAN")
            networks = wlan.scan()
            num_rows = len(networks)
            network_data = {}

            for row in range(num_rows):
                if networks[row][0] != b'': #ignore hidden SSID's
                    network_data[networks[row][0]] = networks[row][3]

            pub_scan_results()
            print(network_data)
                
        if message.get("remove") is not None:
            if DEBUG: print("in REMOVE")
            if DEBUG: print("Remove detected")
            if message.get("ssid") is not None:
                if DEBUG: print("SSID detected",message["ssid"])
                target_value = message["ssid"]
                for row in range (len(myNetworks)):
                    if DEBUG: print(myNetworks[row][0])
                    if myNetworks[row][0] == target_value:
                        if DEBUG: print("Found SSID value in column 0!")
                        del myNetworks[row]
                        write_network_details() #Update the file in flash memory
                        break
                else:
                    if DEBUG: print("SSID value not found in column 0.")
            else:
                if DEBUG: print("SSID is missing - so nothing doing")
            
        if message.get("top") is not None:
            if DEBUG: print("in TOP")
            if (message.get("ssid") is not None) and (message.get("passwd") is not None):
                row = row_ssid_is_in_myNetworks(message["ssid"])
                if row == -1:
                    new_row = [message["ssid"],message["passwd"]]
                    myNetworks.insert(0, new_row)
                    write_network_details()
                    if DEBUG: print("New network added to TOP of flash file")
                else:
                    if DEBUG: print("SSID needs to be deleted before using TOP")
            else:
                if DEBUG: print("SSID or PASSWD - missing in command string")
                
        if message.get("bottom") is not None:
            if DEBUG: print("in BOTTOM")
            if (message.get("ssid") is not None) and (message.get("passwd") is not None):
                row = row_ssid_is_in_myNetworks(message["ssid"])
                if row == -1:
                    new_row = [message["ssid"],message["passwd"]]
                    myNetworks.append(new_row)
                    write_network_details()
                    if DEBUG: print("New network added to BOTTOM of flash file")
                else:
                    if DEBUG: print("SSID needs to be deleted before using TOP")
            else:
                if DEBUG: print("SSID or PASSWD - missing in command string")
                    
        if message.get("network") is not None:
            if DEBUG: print("in NETWORK")
            pub_network_details()
            
        if message.get("reset") is not None:
            if DEBUG: print("in RESET")
            if DEBUG: print(message["reset"])
            
            node_details["deepsleep_duration"] = default_deepsleep_duration
            node_details["shutdown_time"]      = default_shutdown_time
            node_details["cycle_time"]         = default_cycle_time
            node_details["sensors"]            = default_report_sensors
            node_details["buttons"]            = default_report_buttons
            node_details["analog"]             = default_report_analog
            node_details["mode"]               = default_mode
            
            write_to_flash = True
            pub_feedback("Node settings reset to default values")
        
        if message.get("location") is not None:
            if DEBUG: print("in LOCATION")
            if DEBUG: print(message["location"])
            node_details["location"] = message["location"]
            write_to_flash = True
            pub_feedback("Location has been updated")
            
        if message.get("hostname") is not None:
            if DEBUG: print("in HOSTNAME")
            if DEBUG: print(message["hostname"])
            node_details["hostname"] = message["hostname"]
            write_to_flash = True
            pub_feedback("Hostname has been updated")
                
        if message.get("ref") is not None:
            if DEBUG: print("in REF")
            if DEBUG: print(message["ref"])
            node_details["ref"] = message["ref"]
            write_to_flash = True
            pub_feedback("REF has been updated")
            
        if message.get("deepsleep_duration") is not None:
            if DEBUG: print("in DEEPSLEEP")
            if DEBUG: print("deepsleep duration is: ",message["deepsleep_duration"])
            node_details["deepsleep_duration"] = message["deepsleep_duration"]
            write_to_flash = True
            pub_feedback("Deepsleep Duration has been updated")
        
        if message.get("shutdown_time") is not None:
            if DEBUG: print("in SHUTDOWN TIME")
            if DEBUG: print("Shutdown time is: ",message["shutdown_time"])
            node_details["shutdown_time"] = message["shutdown_time"]
            write_to_flash = True
            pub_feedback("Shutdown Time has been updated")

        if message.get("settings") is not None:
            if DEBUG: print("in SETTINGS")
            if DEBUG: print("Publish node settings")
            pub_node_settings()
            pub_feedback("Settings published")
            
        if message.get("sensors") is not None:
            if DEBUG: print("in SENSORS")
            if DEBUG: print("Publish sensor values")
            node_details["sensors"] = message["sensors"]
            write_to_flash = True
            read_sensor_values()
            pub_sensor_values()
            pub_feedback("Sensors values published")
            
        if message.get("buttons") is not None:
            if DEBUG: print("in BUTTONS")
            if DEBUG: print("Publish button values")
            node_details["buttons"] = message["buttons"]
            write_to_flash = True
            read_button_values()
            pub_button_values()
            pub_feedback("Buttons published")
            
        if message.get("analog") is not None:
            if DEBUG: print("in ANALOG")
            if DEBUG: print("Publish analog values")
            node_details["analog"] = message["analog"]
            write_to_flash = True
            read_analog_values()
            pub_analog_values()
            pub_feedback("Analog values published")
            
        if message.get("resume") is not None:
            if DEBUG: print("Shutdown sequence - resumed")
            shutdown_sequence = "enabled"
            pub_feedback("Shutdown sequence resumed")
                    
        if write_to_flash == True:
            write_node_details()
            pub_feedback("node_details have been written to flash")

        pub_feedback("command(s) have been processed")

read_node_details()
if DEBUG: print("debug1:",node_details)

# Create shortcuts for pub & sub topics
publish_to_reading   = pub_readings+"/"+node_details["user"]+"/"+node_details["nodeName"]
publish_to_feedback  = pub_feedback_topic+"/"+node_details["user"]+"/"+node_details["nodeName"]
publish_to_debug     = pub_debug_topic+"/"+node_details["user"]+"/"+node_details["nodeName"]
subscribe_to_command = sub_command

# if node_details.get("mode") is not None:
#     my_mode = node_details["mode"]
# else:
#     my_mode = default_mode

if node_details["type"] == "s2-mini":
    #These pins on a ESP32-S2 Mini are specifically for I2C0
    i2c = SoftI2C(scl=Pin(35), sda=Pin(33))

elif node_details["type"] =="wemos-d1":
    #These pins on a Wemos D1 Mini are specifically for I2C0
    i2c = SoftI2C(scl=Pin(5), sda=Pin(4))

elif node_details["type"] == "pico-w":
    #These pins on a Pico-W are specifically for I2C0
    i2c = SoftI2C(scl=Pin(1), sda=Pin(0))

else:
    raise RuntimeError("Device not recognised")

shutdown_sequence = "enabled"

read_network_details()

sensors = {
    "ssid":"unknown",
    "temp":0.0,
    "humidity":0,
    "pressure": 0,
    "voltage": 3.2
}

buttons = {
    "btn1":"on",
    "btn2":"off",
    "btn3":"off",
    "btn4":"on"
}

analog = {
    "an1":1023,
    "an2":213,
    "an3":0,
    "an4":567
}

# Main program sort of starts here 
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.disconnect()

if node_details.get("hostname") is not None:
    wlan.config(dhcp_hostname=node_details["hostname"])
else:
    wlan.config(dhcp_hostname="unspecified")

# Try joining a WiFi network
# Try this sequence 3 times
wifi_cycle = 3
while wifi_cycle > 0:
    wifi_cycle -= 1
    wifi_status = find_a_network()
    if wifi_status == True:
        sensors["ssid"] = ssid
        break

if wifi_status == False:
    if DEBUG: print("\n\nNo networks available")
    # Call the DeepSleep function as there is no point in carrying on
    force_deepsleep()
    
else:
    if DEBUG: print("\n\nFound and joined a network")

if DEBUG: print("\nConnected to: ",ssid)
status = wlan.ifconfig()
if DEBUG: print("IP = " + status[0] )

# Now try to make a MQTT connection
mqtt_client = MQTTClient("joe", mqtt_server, mqtt_port, mqtt_user, mqtt_passwd)
mqtt_client.set_callback(sub_callback)

mqtt_cycle = 3
while mqtt_cycle > 0:
    mqtt_cycle -= 1
    try:
        mqtt_client.connect()
        mqtt_status = True
    
    except Exception as e:
        if DEBUG: print("Failed to connect to MQTT broker: {}".format(e))
        mqtt_status = False
    if mqtt_status == True:
        break

if mqtt_status == False:
    if DEBUG: print("\n\nMQTT connection not available")
    # Call the DeepSleep function as there is no point in carrying on
    force_deepsleep()
else:
    if DEBUG: print("\nFound and joined a MQTT broker")
    if DEBUG: print(subscribe_to_command)
    mqtt_client.subscribe(subscribe_to_command)
    if DEBUG: print("Connected to %s MQTT broker, subscribed to %s" % (mqtt_server, subscribe_to_command))

# pub_feedback("Node is active")
if DEBUG: print("\nArray after writing and reading to/from flash memory")
if DEBUG: pub_debug("Array after writing and reading to/from flash memory")
if DEBUG: print(myNetworks)
if DEBUG: pub_debug(myNetworks)

# Now see if BME280 sensor is working
bme_address = i2c.scan()[0] # Scan the I2C bus to find the address of the sensor
if DEBUG: print("I2C address for the sensor is ", hex(bme_address))

try:
    bme = BME280(i2c=i2c, address=bme_address)
    status = True

except Exception as e:
    if DEBUG: print("Failed to connect to BME280: {}".format(e))
    status = False

if (status == False):
    if DEBUG: print("Problem")
    # Call Deepsleep
    force_deepsleep()
    

# Node is connected to WiFi and MQTT broker
# BME280 is active
pub_feedback("Node is active")
time.sleep(2)

# This WHILE loop will be performed ONCE if "mode"=="single"
# It will be repeated forever if "mode"=="repeat"
# If "cycles" is present and has a positive value, it will be repeated that number of times
# If "cycle_time" is present, then the loop will be repeated with that delay
# If "cycle_time" is missing, a default value of 15 secs will be used
number_of_cycles = 0
while True:
    mqtt_client.check_msg() # Check for MQTT messages
    
    if node_details["sensors"] == "yes":
        read_sensor_values()
        pub_sensor_values()
        pub_feedback("Sensor readings published")
        
    if node_details["buttons"] == "yes":
        read_button_values()
        pub_button_values()
        pub_feedback("Button values published")
        
    if node_details["analog"] == "yes":
        read_analog_values()
        pub_analog_values()
        pub_feedback("Analog values published")
    
    if node_details.get("mode") is not None:
        my_mode = node_details["mode"]
        if DEBUG: print("my_mode is ",my_mode)
        time.sleep(5)
    else:
        my_mode = default_mode
        
    if my_mode == "single":
        break # Because my_mode = "single" or is missing
    
    if node_details.get("cycles") is not None:
        cycles = node_details["cycles"]
        if cycles < 0: #If the user has enetered a negative value, set cycles to -1
            cycles = -1
    else:
        cycles = -1
    if cycles != -1:
        number_of_cycles += 1
        if number_of_cycles >= cycles:
            break # Because we have repeated the correct number of cycles
    
    if node_details.get("cycle_time") is not None:
        cycle_time = node_details["cycle_time"]
    else:
        cycle_time = default_cycle_time
    
    #Now do a non-blocking delay for 'cycle_time' secs
    start_time = time.time()
    while time.time() - start_time < cycle_time:
        mqtt_client.check_msg() # Check for MQTT messages
    if DEBUG: print("Cycle_Time delay completed")

#Shutdown sequence    
shutdown_time = node_details["shutdown_time"]
start_of_shutdown_time = time.time()

if DEBUG: print("\nJust waste time here\n")
deepsleep_duration = (node_details["deepsleep_duration"]) * 1024 #Deepsleep time in mS

if DEBUG: print("\nDeepsleep duration is:",node_details["deepsleep_duration"],"secs")
if DEBUG: print("Shutdown time is:",node_details["shutdown_time"],"secs")
if DEBUG: print("")

shutdown_time = node_details["shutdown_time"]
start_of_shutdown_time = time.time()
mqtt_client.check_msg()

while (True):
    mqtt_client.check_msg() # Check for MQTT messages
    time_now = time.time()
    if (time_now - start_of_shutdown_time >= shutdown_time) and (shutdown_sequence == "enabled"):
        # deepsleep_duration = (node_details["deepsleep_duration"]) * 1024 #Deepsleep time in mS
        if DEBUG: print("\nDisconnected MQTT & Wifi and turned-off WiFi")
        pub_feedback("Going into deepsleep")
        time.sleep(1)
        mqtt_client.disconnect() # Disconnect from MQTT broker
        wlan.disconnect() # Disconnect from current network
        wlan.active(False)
        deepsleep(deepsleep_duration)
        time.sleep(5)
        if DEBUG: print("Shouldnt get here")
        
    if DEBUG: print("Kicking my heels at end of program")
    time.sleep(1)

#### End of program
