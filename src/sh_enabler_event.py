#
# Environemt Variables
# event_bus
#

import sys
import boto3
import json
import urllib3
import os
import logging
from datetime import date, datetime
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
if 'log_level' in os.environ:
    LOGGER.setLevel(os.environ['log_level'])
    print('Log level set to %s' % LOGGER.getEffectiveLevel())
else:
    LOGGER.setLevel(logging.ERROR)

session = boto3.Session()

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError('Type %s not serializable' % type(obj))

def push_sh_enabled_event(event_source, resource_arn, member_account, member_email):
    try:
        ev_client = session.client('events')
        event_payload = {
            'EventName': 'SecurityHubEnabled',
            'Message': 'SecurityHub enabled on Account',
            'serviceEventDetails': {
                'securityHubEnabledAccount': {
                    'member_account': member_account,
                    'member_email': member_email
                }
            }
        }
        event = {
            'Time': datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%SZ'),
            'Source': event_source,
            'Resources': [ resource_arn ],
            'DetailType': 'SHEnablerSM Event',
            'Detail': json.dumps(event_payload),
            'EventBusName': os.environ['event_bus']
        }
        print('Event:')
        print(json.dumps(event, indent=2))
        response = ev_client.put_events(Entries=[ event ])
        print(json.dumps(response, indent=2))
        return response['Entries'][0]
    except Exception as e:
        print(f'failed in put_events(..): {e}')
        print(str(e))

def lambda_handler(event, context):
    print(f"REQUEST RECEIVED: {json.dumps(event, default=str)}")
    member_account = event['member_account']
    member_email = event['member_email']
    event_source = 'org.{}'.format(context.function_name)
    resource_arn = context.invoked_function_arn
    response_data = push_sh_enabled_event(event_source, resource_arn, member_account, member_email)
    return {
        'statusCode': 200,
        'member_account': member_account,
        'member_email': member_email,
        'event_data': response_data
    }    
    