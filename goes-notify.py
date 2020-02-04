#!/usr/bin/env python

# Note: for setting up email with sendmail, see: http://linuxconfig.org/configuring-gmail-as-sendmail-email-relay

import argparse
import commands
import json
import logging
import smtplib
import sys
import os
import glob
import requests
import hashlib

from datetime import datetime
from os import path
from subprocess import check_output
from distutils.spawn import find_executable
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

EMAIL_TEMPLATE = """
<p>Good news! New Global Entry appointment(s) available on the following dates:</p>
%s
<p>Your current appointment is on %s</p>
<p>If this sounds good, please sign in to https://ttp.cbp.dhs.gov/ to reschedule.</p>
"""
GOES_URL_FORMAT = 'https://ttp.cbp.dhs.gov/schedulerapi/slots?orderBy=soonest&limit=3&locationId={0}&minimum=1'

def main(settings):

    if not settings['enrollment_location_id_list']:
        logging.info('Location ID list is empty.')
        return
    
    for enrollment_location_id in settings['enrollment_location_id_list']:
        try:
            logging.info('Checking appointment availability in location: %s' % enrollment_location_id)
            # obtain the json from the web url
            data = requests.get(GOES_URL_FORMAT.format(enrollment_location_id)).json()

            # parse the json
            if not data:
                logging.info('No appointments available.')
                continue

            current_apt = datetime.strptime(settings['current_interview_date_str'], '%B %d, %Y')
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
            if settings.get('no_spamming') and os.path.exists(fn):
                continue
            else:
                for f in glob.glob("goes-notify_{0}_*.txt".format(enrollment_location_id)):
                    os.remove(f)
                f = open(fn,"w")
                f.close()

        except OSError:
            logging.critical("Something went wrong when trying to obtain the appointment data.")
            continue

        msg = 'Found new appointment(s) in location %s on %s (current is on %s)!' % (enrollment_location_id, dates[0], current_apt.strftime('%B %d, %Y @ %I:%M%p'))
        notify_via_gmail(dates, current_apt, settings, enrollment_location_id)

def notify_via_gmail(dates, current_apt, settings, enrollment_location_id):
    sender = settings.get('gmail_account')
    recipient = settings.get('email_to', sender)  # If recipient isn't provided, send to self.

    try:
        password = settings.get('gmail_password')
        if not password:
            logging.warning('Trying to send from gmail, but password was not provided.')
            return
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)

        subject = 'Alert: Global Entry interview openings are available at location {}.'.format(enrollment_location_id)

        dateshtml = '<ul>'
        for d in dates:
            dateshtml += "<li>" + d + "</li>"

        dateshtml += "</ul>"

        message = EMAIL_TEMPLATE % (dateshtml, current_apt.strftime('%B %d, %Y'))

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = ','.join(recipient)
        msg['mime-version'] = "1.0"
        msg['content-type'] = "text/html"
        msg.attach(MIMEText(message, 'html'))

        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
    except Exception:
        logging.exception('Failed to send succcess e-mail.')
        log(e)

def _check_settings(config):
    required_settings = (
        'current_interview_date_str',
        'enrollment_location_id_list',
        'gmail_account',
        'gmail_password',
        'email_to'
    )

    for setting in required_settings:
        if not config.get(setting):
            raise ValueError('Missing setting %s in config.json file.' % setting)
    
    if not isinstance(config.get('enrollment_location_id_list'), list):
        raise ValueError('enrollment_location_id_list has to be a list')

    if not isinstance(config.get('email_to'), list):
        raise ValueError('email_to has to be a list')

if __name__ == '__main__':

    # Configure Basic Logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(asctime)s %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        stream=sys.stdout,
    )

    pwd = path.dirname(sys.argv[0])

    # Parse Arguments
    parser = argparse.ArgumentParser(description="Command line script to check for goes openings.")
    parser.add_argument('--config', dest='configfile', default='%s/config.json' % pwd, help='Config file to use (default is config.json)')
    arguments = vars(parser.parse_args())
    logging.info("config file is:" + arguments['configfile'])
    # Load Settings
    try:
        with open(arguments['configfile']) as json_file:
            settings = json.load(json_file)

            # merge args into settings IF they're True
            for key, val in arguments.iteritems():
                if not arguments.get(key): continue
                settings[key] = val

            settings['configfile'] = arguments['configfile']
            _check_settings(settings)
    except Exception as e:
        logging.error('Error loading settings from config.json file: %s' % e)
        sys.exit()

    # Configure File Logging
    if settings.get('logfile'):
        handler = logging.FileHandler('%s/%s' % (pwd, settings.get('logfile')))
        handler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s %(message)s'))
        handler.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(handler)

    logging.debug('Running script with arguments: %s' % arguments)

    main(settings)
