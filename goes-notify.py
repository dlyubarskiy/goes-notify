#!/usr/bin/env python

import logging
import sys
import os
import glob
import requests
import hashlib
import telegram
import asyncio
import json

from datetime import datetime, timedelta
from os import path
from subprocess import check_output
from distutils.spawn import find_executable

GOES_URL_FORMAT = 'https://ttp.cbp.dhs.gov/schedulerapi/slots?orderBy=soonest&limit=3&locationId={0}&minimum=1'

def main(current_apt, enrollment_location_id_list, telegram_api_token, telegram_channel_id):
    
    for enrollment_location_id in enrollment_location_id_list:
        try:
            logging.info('Checking appointment availability in location: %s' % enrollment_location_id)
            # obtain the json from the web url
            data = requests.get(GOES_URL_FORMAT.format(enrollment_location_id)).json()

            # parse the json
            if not data:
                logging.info('No appointments available.')
                continue

            dates = []
            for o in data:
                if o['active']:
                    dt = o['startTimestamp'] #2017-12-22T15:15
                    dtp = datetime.strptime(dt, '%Y-%m-%dT%H:%M')
                    if current_apt > dtp:
                        dates.append(dtp.strftime('%A, %B %d @ %I:%M%p'))

            if not dates:
                continue

            hash = hashlib.md5(''.join(dates) + current_apt.strftime('%B %d, %Y @ %I:%M%p')).hexdigest()
            fn = "goes-notify_{0}_{1}.txt".format(enrollment_location_id,hash)
            if os.path.exists(fn):
                continue
            else:
                for f in glob.glob("goes-notify_{0}_*.txt".format(enrollment_location_id)):
                    os.remove(f)
                f = open(fn,"w")
                f.close()

        except OSError:
            logging.critical("Something went wrong when trying to obtain the appointment data.")
            continue

        msg = 'Found new appointment(s) at %s (location ID: %s) on %s (current is on %s)!' % (get_enrollment_center_name(enrollment_location_id), enrollment_location_id, dates[0], current_apt.strftime('%B %d, %Y @ %I:%M%p'))
        send_telegram_notification(telegram_api_token, telegram_channel_id, msg)
    
def send_telegram_notification(telegram_api_token, telegram_channel_id, msg):
    bot = telegram.Bot(token=telegram_api_token)

    # need to pre-pend '-100' before the Telegram channel ID for the messages to go through
    updated_telegram_channel_id = '-100' + telegram_channel_id
    try:
        asyncio.run(bot.send_message(chat_id=updated_telegram_channel_id, text=msg))

    except Exception as e:
        logging.error("Something went wrong when trying to send the message to Telegram channel, the error is: ",e)
        sys.exit()

def get_enrollment_center_name(enrollment_location_id):

    enrollment_center_name = ''
    pwd = path.dirname(sys.argv[0])
    enrollment_centers_json = os.path.join(pwd, 'enrollment_centers.json')    

    try:
        with open(enrollment_centers_json) as f:
            enrollment_centers = json.load(f)
            for enrollment_center in enrollment_centers:
                if enrollment_center['ID'] == enrollment_location_id:
                    enrollment_center_name = enrollment_center['Name']
                    break
    
    except Exception as e:
        logging.error("Something went wrong when trying to find enrollment center name, the error is: ",e)
    
    return enrollment_center_name


if __name__ == '__main__':

    # Configure Basic Logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(asctime)s %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        stream=sys.stdout,
    )

    pwd = path.dirname(sys.argv[0])

    # Read in environment variables
    CURR_IVIEW_DATE = os.environ.get("CURR_IVIEW_DATE")
    LOCATION_IDS    = os.environ.get("LOCATION_IDS")
    TG_API_TOKEN    = os.environ.get("TG_API_TOKEN")
    TG_CHANNEL_ID   = os.environ.get("TG_CHANNEL_ID")
    LOG_FILE        = os.environ.get("LOG_FILE")

    if CURR_IVIEW_DATE is None or CURR_IVIEW_DATE == "":
        current_apt = datetime.now() + timedelta(days=6*30)
        logging.info('Current appointment not set, assuming time window is six months from today.')
    else:
        current_apt = datetime.strptime(CURR_IVIEW_DATE, '%B %d, %Y')

    if LOCATION_IDS is None or LOCATION_IDS == "":
        logging.error('Location IDs are required to search for available appointments. Please set LOCATION_IDS environment variable')
        sys.exit()
    else:
        enrollment_location_id_list = LOCATION_IDS.split(",")

    if TG_API_TOKEN is None or TG_API_TOKEN == "":
        logging.error('Telegram API token is required to send notifications. Please set TG_API_TOKEN environment variable')
        sys.exit()
    else:
        telegram_api_token = TG_API_TOKEN

    if TG_CHANNEL_ID is None or TG_CHANNEL_ID == "":
        logging.error('Telegram channel ID is required to send notifications. Please set TG_CHANNEL_ID environment variable')
        sys.exit()
    else:
        telegram_channel_id = TG_CHANNEL_ID

    if LOG_FILE is None or LOG_FILE == "":
        logfile = ""
    else:
        logfile = LOG_FILE

    # Configure File Logging
    if logfile:
        handler = logging.FileHandler('%s/%s' % (pwd, logfile))
        handler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s %(message)s'))
        handler.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(handler)

    main(current_apt, enrollment_location_id_list, telegram_api_token, telegram_channel_id)
