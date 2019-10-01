
# python-cron

A cron implementation in python with extended schedule and command definition.

## Prerequisites

Python with modules ciso8601, cronex, ephem, pytz, requests, tzlocal, unidecode

## Installation

- install -c -m 755 cron.py /usr/local/bin
- install -c -m 755 crontab /usr/local/etc
- install -c -m 755 cron /usr/local/etc/init.d

Adjust the home location in the get_sunrise_and_set() method in cron.py to get proper sunrise and sunset times.

## Trigger Definition

All notations by [cronex](pypi.org/project/cronex/) are supported. Additionally you can the macros SUNRISE(angle) and SUNSET(angle) instead of the minute and hour definition. These will be replace by the actual sunrise and sunset time of the day. The angle can be used to specify a relative positive or negative horizon offset to the calculation.

## Command Definition

The commands to executed when a trigger hits are specified in a

>prefix:command

The following prefixes can be used:

- iobroker    an iobroker value setting via the corresponding HTTP REST setBulk request
- python      a python method executed via the python eval funtion
- system      a system command executed via the python os.system function

For iobroker and system multiple commands can be specified separated by a ','.

