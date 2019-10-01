
# python-cron

A cron implementation in python with extended schedule and command definition.

## Prerequisites

Python with modules ciso8601, cronex, ephem, pytz, requests, tzlocal, unidecode

## Installation

cron.py -> /usr/local/bin
crontab -> /usr/local/etc
cron -> /usr/local/etc/init.d

Adjust the home location in the get_sunrise_and_set() method to get proper sunrise and sunset times.

## Trigger Definition

All notations by [cronex](pypi.org/project/cronex/) are supported. Additionally you can the macros SUNRISE(angle) and SUNSET(angle) instead of the minute and hour definition. These will be replace by the actual sunrise and sunset time of the day. The angle can be used to specify a relative positive or negative horizon offset to the calculation.
