import gpio
import pubsub

//Topics
INCOMING_TOPIC ::= "cloud:door/in"
OUTGOING_TOPIC ::= "cloud:door/out"

//Logic variables 
alarm_activated := true
alarm_flag := false

//Pin definitions
pin := gpio.Pin 26 --input
led := gpio.Pin 33 --output 

main:
  task:: subscriber_publisher
  task:: door_check

//Three states can be triggered via pubsub. Use the python program to fire the triggers.
subscriber_publisher: 
  pubsub.subscribe INCOMING_TOPIC --auto_acknowledge: | msg/pubsub.Message |
    if msg.payload.to_string == "on":
      pubsub.publish OUTGOING_TOPIC "Alarm activated"
      alarm_activated = true
    if msg.payload.to_string == "off":
      pubsub.publish OUTGOING_TOPIC "Alarm deactivated"
      alarm_activated = false
    if msg.payload.to_string == "status":
      pubsub.publish OUTGOING_TOPIC "alarm activated: $alarm_activated"
      alarm_activated = false

//Basic logic for the door checker
door_check: 
  while true:
    if alarm_activated == false:
      led.set 0
      sleep --ms=500
    else:
      if pin.get==0:
        if alarm_flag==false:
          print "Door open"
          pubsub.publish OUTGOING_TOPIC "Door open"
          alarm_flag = true
      if pin.get==1:
        if alarm_flag==true:
          print "Door closed"
          pubsub.publish OUTGOING_TOPIC "Door closed"
          alarm_flag = false
      if alarm_flag==true:
        led.set 1
        sleep --ms=500
      if alarm_flag==false: 
        led.set 0
        sleep --ms=500


        