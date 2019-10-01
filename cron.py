#!/usr/bin/python
# -*- coding: utf-8 -*-

# standard python modules
import argparse
import datetime
import logging
import logging.config
import math
from operator import itemgetter
import time
import os
import re
import sys

# additional python modules
import ciso8601
import cronex
import ephem
import pytz
import requests
import tzlocal
import unidecode

# === PLACE YOUR CUSTOM METHODS TO BE CALLED FROM THE CRONTAB ENTRIES HERE ===
# === THE CRONTAB ENTRY MUST INCLUDE ANY ARGUMENTS                         ===
# === CURRENTLY ONLY THE TRIGGER TIME IS PROVIDED                          ===

def my_crontab_method(t):
    now = datetime.datetime(*t)
    log.info('my_crontab_method {0}'.format(now))
    # ...
    
def family_presence():
    checkList = {}
    checkList['alexander'] = [ 'javascript.0.host.alex.state', 'javascript.0.host.handyalex.state', 'javascript.0.host.depacnglw1nb0mx.state', 'javascript.0.host.depacnglw1nb0mx-wlan.state' ]
    checkList['helga'] = [' javascript.0.host.helga.state', 'javascript.0.host.handyhelga.state' ]
    checkList['martin'] = [ 'javascript.0.host.martin2.state', 'javascript.0.host.martin2-wlan.state', 'javascript.0.host.handymartin.state' ]
    checkList['daniel'] = [ 'javascript.0.host.surface.state', 'javascript.0.host.surface-wlan.state', 'javascript.0.host.handydaniel.state' ]
    values = []
    for name in checkList.keys():
        objs = get_iobroker_values(args.iobroker, checkList[name])
        presence = False
        for val in objs.keys():
            if not 'val' in objs[val].keys() or not objs[val]['val']:
                continue
            presence = True
        now = datetime.datetime.now()
        duration = 0.0
        if presence:
            state = 'home'
            values.append('javascript.0.family.{0}.lastseen={1}'.format(name, now.strftime('%Y-%m-%d %H:%M:%S')))
        else:
            lastseen = get_iobroker_value(args.iobroker, 'javascript.0.family.{0}.lastseen'.format(name))
            duration = 1.0
            if lastseen:
                duration = (now - ciso8601.parse_datetime(lastseen)).total_seconds() / 3600.0
            if duration >= 24.0:
                state = 'gone'
            elif duration >= 1.0:
                state = 'away'
            else:
                state = 'inactive'
        log.info('PRESENCE {0} = {1} {2:.1f}h'.format(name, state, duration))
        values.append('javascript.0.family.{0}.presence={1}'.format(name, state))
    if len(values) > 0:
        set_iobroker_values(args.iobroker, values)

def update_calendars():
    """
    Update calendar entries.
    """
    values = []
    for name in [ 'Alexander', 'Helga', 'Martin', 'Daniel', 'Familie' ]:
        lastEvent = get_iobroker_value(args.iobroker, 'javascript.0.family.{0}.nextevent'.format(name))
        cal = get_calendar(name)
        nextEvent = ""
        if len(cal) > 0:
            dt = sorted(cal.keys())[0]
            nextEvent = dt.strftime('%m-%d %H:%M') + ' ' + cal[dt]
        if nextEvent != lastEvent:
            cmd = u'javascript.0.family.{0}.nextevent={1}'.format(name.lower(), nextEvent)
            log.debug(cmd)
            values.append(cmd)
    if len(values) > 0:
        set_iobroker_values(args.iobroker, values)

def update_hosts():
    """
    Dedicated rules/logic for specific hosts.
    """
    switches = { 'raspi4' : 'node-red.0.Haus.Dachgeschoss.Arbeitszimmer.Sonoff-R04.Command' }
    calEvents = [ "ical.0.events.Brückentag", "ical.0.events.Feiertag", "ical.0.events.Gleittag", "ical.0.events.Urlaub" ]
    dayAtHome = False
    for item in get_iobroker_values(args.iobroker, calEvents).values():
        if not item['val']:
            continue
        dayAtHome = True
        break
    cronLines = []
    for host in switches.keys():
        line = ''
        if not dayAtHome:
            line = '0 7 * * 1-5     iobroker:{0}=false'.format(switches[host])
        if line:
            cronLines.append(line)
    return cronLines

def host_shutdown(host, switch_command):
    """
    Shutdown and power off a host.
    """
    cmd = 'ssh pi@{0} {1}'.format(host, 'sudo /usr/local/sbin/auto_shutdown')
    os.system(cmd)
    time.sleep(10)
    set_iobroker_values(args.iobroker, [ switch_command ])

def vdr_timer():
    """
    Update switches with regard to VDR timers.
    """
    switches = { 'raspi7' : 'pilight.0.brennenstuhl2a.state' }
    cronLines = []
    for host in switches.keys():
        nextTimer = get_iobroker_value(args.iobroker, 'javascript.0.host.{0}.vdr.next'.format(host))
        if not nextTimer or nextTimer == '-':
            continue
        dt = datetime.datetime.strptime(nextTimer, '%Y-%m-%d %H:%M:%S') - datetime.timedelta(minutes=10)
        line = '{0} {1} {2} {3} *     '.format(dt.minute, dt.hour, dt.day, dt.month)
        #if 'rcs2044' in switches[host]:
        #    line += 'system:/usr/local/bin/switch.py -H raspi4 1 on'
        #else:
        line += 'iobroker:{0}=true'.format(switches[host])
        cronLines.append(line)
    return cronLines
    
def get_energy_offset():
    """
    Store current energy reading in a dedicated ioBroker variable.
    """
    energy = get_iobroker_value(args.iobroker, 'fhem.1.HM_4D12B7_IEC_01.energy')
    log.debug('energy={0}'.format(energy))
    if energy != None:
        set_iobroker_values(args.iobroker, [ 'javascript.0.rooms.wk.energy={0}'.format(energy) ])

def update_daily():
    """
    Daily update method
    """
    (sr, ss) = get_sunrise_and_set()
    values = []
    values.append('javascript.0.sunrise=' + sr.strftime('%H:%M'))
    values.append('javascript.0.sunset=' + ss.strftime('%H:%M'))
    set_iobroker_values(args.iobroker, values)

def update():
    """
    General update method.
    Do whatever is necessary and meaningful here collecting additional crontab entries.
    At the end call update_crontab() with the collected entries.
    """
    log.debug('update() start')
    additionalEntries = []
    additionalEntries += vdr_timer()
    additionalEntries += update_hosts()
    update_crontab(additionalLines=additionalEntries)
    log.debug('update() finish')

# === HERE STARTS THE BASIC CRON.PY INFRASTRUCTURE ===
# ===  ONLY MODIFY, IF YOU KNOW WHAT YOU'RE DOING  ===

crontabFile = '/usr/local/etc/crontab'
crontabTmpFile = '/var/tmp/crontab.txt'

def get_sunrise_and_set(horizon=0):
    """
    Get today's sunrise and sunset time for a given angle relative to the horizon.
    """

    aachen = ephem.Observer()
    aachen.lat = '50.7499'
    aachen.lon = '6.1775'
    aachen.elevation = 250
    aachen.horizon = horizon * math.pi / 180
    aachen.date = datetime.date.today()
    sun = ephem.Sun()
    sr = ephem.localtime(aachen.next_rising(sun))
    sr = datetime.datetime(sr.year, sr.month, sr.day, sr.hour, sr.minute)
    ss = ephem.localtime(aachen.next_setting(sun))
    ss = datetime.datetime(ss.year, ss.month, ss.day, ss.hour, ss.minute)
    return (sr, ss)

def get_calendar(cal_name, cal_class=None):
    """
    Get calendar entries for given calendar name from ioBroker
    Returns dictionary of datetime and event name.
    """
    result = {}
    cal = get_iobroker_values(args.iobroker, [ 'ical.0.data.table' ])
    if not 'ical.0.data.table' in cal.keys():
        log.warning('no ical data table from ioBroker on {0}'.format(args.iobroker))
        return result
    local_tz = tzlocal.get_localzone()
    today = datetime.date.today()
    for ical in cal['ical.0.data.table']['val']:
        if not ical['_calName'] == cal_name:
            continue
        log.debug('{0} {1} {2}'.format(ical['date'], ical['_date'], unidecode.unidecode(ical['event'])))
        if cal_class != None and not ical['_class'].endswith(cal_class):
            continue
        # convert UTC time to local time
        start = ciso8601.parse_datetime(ical['_date']).replace(tzinfo=pytz.utc).astimezone(local_tz)
        end = ciso8601.parse_datetime(ical['_end']).replace(tzinfo=pytz.utc).astimezone(local_tz)
        dt = start
        if start.date() <= today and end.date() >= today:
            dt = ciso8601.parse_datetime(today.isoformat()).replace(tzinfo=local_tz)
        result[dt] = unidecode.unidecode(ical['event'])
    return result

def get_iobroker_value(host, object_id):
    """
    Get a single ioBroker object value.
    """
    result = None
    log.debug('get_iobroker_value() start')
    try:
        response = requests.get('http://' + host + ':8082/getPlainValue/' + object_id)
        if response.status_code == 200:
            result = response.json()
    except:
        log.critical('ioBroker connection to {0} failed'.format(host))
        pass
    log.debug('get_iobroker_value() finish')
    return result
    
def get_iobroker_values(host, object_ids):
    """
    Get ioBroker object values.
    """
    result = {}
    log.debug('get_iobroker_values() start')
    for id in object_ids:
        try:
            response = requests.get('http://' + host + ':8082/get/' + id)
            if response.status_code == 200:
                result[id] = response.json()
        except:
            log.critical('ioBroker connection to {0} failed'.format(host))
            pass
    log.debug('get_iobroker_values() finish')
    return result
    
def set_iobroker_values(host, values):
    """
    Set ioBroker object values.
    """
    log.debug('set_iobroker_values() start')
    result = False
    if len(values) > 0:
        try:
            response = requests.post('http://' + host + ':8082/setBulk/?' + '&'.join(values))
            result = response.status_code == 200
            log.info('{0} values sent to ioBroker on {1}'.format(len(values), host))
        except:
            log.critical('ioBroker connection to {0} failed'.format(host))
            pass
    log.debug('set_iobroker_values() finish')
    return result

def update_crontab(add_debug_entry=False, additionalLines=[]):
    """
    Update the execution crontab from the global one.
    Replace SUNRISE(hor), SUNSET(hor) macros by actual values for today.
    """
    log.debug('update_crontab() start')
    cronLines = []
    with open(crontabFile) as f:
        for line in f.readlines():
            if line.startswith('#'):
                continue
            m = re.match('SUNRISE\(([^\)]+)\)', line)
            if m:
                angle = float(m.group(1))
                (sr, ss) = get_sunrise_and_set(angle)
                log.info('  sunrise({0}) {1}'.format(angle, sr))
                line = sr.strftime('%M %H ') + ' '.join(line.split()[1:])
            m = re.match('SUNSET\(([^\)]+)\)', line)
            if m:
                angle = float(m.group(1))
                (sr, ss) = get_sunrise_and_set(angle)
                log.info('  sunset({0}) {1}'.format(angle, ss))
                line = ss.strftime('%M %H ') + ' '.join(line.split()[1:])
            cronLines.append(line)
    if add_debug_entry:
        cronLines.append('* * * * *   python:cron_debug(t)')
    with open(crontabTmpFile, 'w') as f:
        for line in cronLines + additionalLines:
            f.write(line.strip() + '\n')
    log.debug('update_crontab() finish')

def cron_debug(t):
    """
    Debug entry for python methods in the crontab.
    """
    now = datetime.datetime(*t)
    log.info('cron_debug {0}'.format(now))

def cron_check(cron_line, t, execute=True):
    """
    Check the given crontab line for execution at the given time.
    If triggered, execute the specified command.
    """
    job = cronex.CronExpression(cron_line)
    # time up to minute precision
    t = t[:5]
    #log.debug('check t={0} {1}'.format(t, job))
    if not job.check_trigger(t):
        return False
    if job.comment.startswith('system:'):
        if execute:
            cmd = job.comment[7:]
            log.info('executing system job {0}'.format(cmd))
            for subcmd in cmd.split(','):
                os.system(subcmd)
        return True
    elif job.comment.startswith('iobroker:'):
        if execute:
            cmd = job.comment[9:]
            log.info('executing iobroker job {0}'.format(cmd))
            set_iobroker_values(args.iobroker, cmd.split(','))
        return True
    elif job.comment.startswith('python:'):
        if execute:
            cmd = job.comment[7:]
            log.info('executing python job {0}'.format(cmd))
            eval(cmd)
        return True
    else:
        log.error('unknown job {0}'.format(job.comment))
    return False

def cron_loop(fileName, sleep_interval=10):
    """
    """
    log.debug('cron_loop() start')
    while True:
        log.debug('  sleep {0}s'.format(sleep_interval))
        time.sleep(sleep_interval)
        t = time.localtime(time.time())
        # only trigger, if the seconds are within the sleep interval
        if t[5] >= sleep_interval:
            continue
        for line in open(fileName):
            if line.startswith('#'):
                continue
            cron_check(line.strip(), t)
    log.debug('cron_loop() finish')

def cron_test(fileName, t=None):
    log.debug('cron_test() start')
    if t == None:
        t = datetime.datetime.now().timetuple()
    for line in open(fileName):
        if line.startswith('#'):
            continue
        trigger = cron_check(line.strip(), t, execute=False)
        print('{0}:{1} {2} -> {3}'.format(t[3], t[4], line.strip(), trigger))
    #update_calendars()
    #family_presence()
    #print(vdr_timer())
    #update_hosts()
    #update_daily()
    #get_energy_offset()
    #print get_calendar('Alexander', 'today')
    #print get_calendar('Helga')
    #print get_calendar('Familie')
    log.debug('cron_test() finish')

parser = argparse.ArgumentParser(description='')
parser.add_argument('-d', '--debug', action='store_true', help='debug execution')
parser.add_argument('-i', '--iobroker', default='localhost', help='ioBroker hostname/IP (localhost)')
parser.add_argument('-s', '--sleep', type=int, default=10, help='sleep interval in seconds (10)')
parser.add_argument('-t', '--test', default='', help='test at given time HH:MM')
args = parser.parse_args(sys.argv[1:])

self = os.path.basename(sys.argv[0])
myName = os.path.splitext(self)[0]
log = logging.getLogger(myName)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
if args.debug:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)

if not os.path.exists(crontabFile):
    log.critical(crontabFile + 'not found')
    quit()
if not os.path.exists(crontabTmpFile) or args.debug:
    update_crontab(args.debug)
if args.test:
    log.info('TEST mode')
    today = datetime.date.today()
    h = int(args.test.split(':')[0])
    m = int(args.test.split(':')[1])
    cron_test(crontabTmpFile, (today.year, today.month, today.day, h, m))
    #host_shutdown('raspi6', 'pilight.0.brennenstuhl2d.state=false')
else:
    log.info('REGULAR mode')
    cron_loop(crontabTmpFile, args.sleep)
