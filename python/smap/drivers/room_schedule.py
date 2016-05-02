# -*- coding: utf-8 -*-
"""
Copyright (c) 2011, 2012, Regents of the University of California
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

 - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 - Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.
"""
"""
@author Jonathan Fürst <jonf@itu.dk>
based on Bjørn Friese's work: https://github.com/eitu/eitu
"""
from smap import driver
from smap.util import periodicSequentialCall

import os, re, sys, logging
import pytz, requests
from datetime import datetime, timedelta


URL_STUDY_ACTIVITIES = 'https://dk.timeedit.net/web/itu/db1/public/ri6Q7Z6QQw0Z5gQ9f50on7Xx5YY00ZQ1ZYQycZw.ics'
URL_ACTIVITIES = 'https://dk.timeedit.net/web/itu/db1/public/ri6g7058yYQZXxQ5oQgZZ0vZ56Y1Q0f5c0nZQwYQ.ics'

FAKES = [
    r'ScrollBar', # Locked
    r'Balcony', # Open space
    r'learnIT', # Virtual
    r'DesignLab', # Lab, locked
    r'InterMediaLab', # Lab, locked
    r'5A30',
    r'3A20', # Locked
    r'3A50', # Stuffed with computers
    r'3A52',
    r'^$', # Bug
]


# Fix unicode madness
reload(sys)
sys.setdefaultencoding('utf8')

# Establish timezone and present time
TZ = pytz.timezone('Europe/Copenhagen')
NOW = datetime.now(TZ)

class ROOM_SCHEDULE(driver.SmapDriver):
    def setup(self, opts):
        self.tz = opts.get('Metadata/Timezone', None)
        self.rate = float(opts.get('Rate', 120))

    def start(self):
        # Call read every 2 seconds
        periodicSequentialCall(self.read).start(self.rate)

    def read(self):
        self.rooms = get_room_schedules()
        for r in self.rooms:
            print r
            # normal rooms
            if r['name'][0] in ['0', '1', '2', '3', '4', '5']:
                floor = r['name'][0]
            # auditoriums
            elif r['name']=='AUD1':
                floor = '0'
            elif r['name']=='AUD2':
                floor = '0'
            elif r['name']=='AUD3':
                floor = '2'
            elif r['name']=='AUD4':
                floor = '4'
            else:
                print "ELSE"
            value = long(r['empty'])
            room = r['name']
            path = "/"+floor
            if self.get_collection(path) is None:
                self.add_collection(path)
            path = '/'+floor+'/'+room
            if self.get_collection(path) is None:
                self.add_collection(path)
            if self.get_timeseries(path+"/"+"calendar_booking") is None:
                self.add_timeseries(path+"/"+"calendar_booking",
                    "State", data_type="long", timezone=self.tz)
            self.add(path+"/"+"calendar_booking", value)


def get_room_schedules():

    # Fetch iCalendar sources and parse events
    study_activities = fetch_and_parse(URL_STUDY_ACTIVITIES)
    activities = fetch_and_parse(URL_ACTIVITIES)
    events = study_activities + activities

    # Remove duplicate events
    events = {e['uid']: e for e in events}.values()

    # Establish schedules of events for each room
    logging.info('Establishing schedules')
    schedules = {}
    for event in events:
        for room in event['rooms']:
            if room not in schedules: schedules[room] = []
            schedules[room].append(event)
    schedules = {key: s for key, s in schedules.items() if not is_fake(key)}

    # Merge adjacent and overlapping events in each schedule
    logging.info('Merging events')
    for schedule in schedules.itervalues():
        schedule.sort(key=lambda event: event['start'])
        merged = []
        for event in schedule:
            if merged and merged[-1]['end'] >= event['start']:
                merged[-1]['end'] = event['end']
            else:
                merged.append(event)
        schedule = merged

    # Determine the status of each room and how long it will be empty for
    logging.info('Determining status of rooms')
    rooms = []
    for name, schedule in schedules.iteritems():
        room = {'name': name}
        for event in schedule:
            if NOW <= event['start']:
                room['empty'] = True
                room['until'] = format_date(event['start'])
                room['empty_for'] = event['start'] - NOW
                break
            if event['start'] <= NOW <= event['end']:
                room['empty'] = False
                room['until'] = format_date(event['end'])
                room['empty_for'] = NOW - event['end']
                break
        if 'empty' not in room:
            room['empty'] = True
            room['until'] = 'For the foreseeable future'
            room['empty_for'] = timedelta.max
        rooms.append(room)
    rooms.sort(key=lambda room: room['empty_for'], reverse=True)
    return rooms


def format_date(date): return date.strftime('%a %b %d at %H:%M')

def clean_room(room):
    room = re.sub(r'^Room: ', '', room)
    room = re.sub(r' \(.*\)$', '', room)
    room = room.replace(" ", "")
    room = room.replace("Aud", "AUD")
    room = room.replace("/", "-")
    return room

def is_fake(room):
    return any([re.search(fake, room, re.IGNORECASE) for fake in FAKES])

def fetch_and_parse(url):
    logging.info('Fetching %s' % url)
    ics = requests.get(url).text
    logging.info('Parsing %s' % url)
    calendar = parse(ics)
    events = [{
        'rooms': map(clean_room, event['LOCATION'].split(', ')),
        'start': event['DTSTART'].astimezone(TZ),
        'end': event['DTEND'].astimezone(TZ),
        'uid': event['UID'],
    } for event in calendar]
    return events

def lines_to_event(lines):
    # Unescape double escapes
    lines = [line.replace('\\', '') for line in lines]
    # Transform lines to event
    event = {}
    key = None
    for line in lines:
        if not line.startswith(' '):
            key, value = line.split(':', 1)
            event[key] = value
        elif key is not None:
            event[key] += line[1:]
    # Convert values to datetimes where possible
    # Example datetime: 20160324T164512Z
    for key, value in event.items():
        try:
            event[key] = datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=pytz.UTC)
        except:
            pass
    return event

def parse(ical):
    # Unicode utf-8
    ical = unicode(ical).encode('utf-8')
    # Normalize linebreaks and split ical into list of lines
    ical = ical.replace('\r\n', '\n')
    iterator = iter(ical.split('\n'))
    # Break lines up into a list of events
    events = []
    while True:
        try:
            line = iterator.next()
            if 'BEGIN:VEVENT' == line:
                line = iterator.next()
                lines = []
                while not 'END:VEVENT' == line:
                    lines.append(line)
                    line = iterator.next()
                events.append(lines_to_event(lines))
        except StopIteration:
            return events


if __name__ == "__main__":
    print get_room_schedules()
