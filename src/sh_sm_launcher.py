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

# globals

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError('Type %s not serializable' % type(obj))

def get_account_from_ct_event(event):
    if 'detail' in event:
        if 'eventName' in event['detail']:
            if event['detail']['eventName'] == 'CreateManagedAccount':
                service_detail = event['detail']['serviceEventDetails']
                status = service_detail['createManagedAccountStatus']
                state = status['state']
                print("Received Control Tower Event: CreateManagedAccount State: {}".format(state))
                account_id = status['account']['accountId']
                org_unit_id = status['organizationalUnit']['organizationalUnitId']
                if state != 'SUCCEEDED':
                    return {
                        'account_id': account_id,
                        'org_unit_id': org_unit_id,
                        'state': state
                    }
                org_client = session.client('organizations')
                account_data = org_client.describe_account(AccountId=account_id)
                email = account_data['Account']['Email']
                return {
                    'account_id': account_id,
                    'email': email,
                    'org_unit_id': org_unit_id,
                    'state': state
                }

def get_ct_regions(account_id):
    # use CT session
    cf_client = session.client('cloudformation')
    region_set = set()
    try:
        # stack instances are outdated
        paginator = cf_client.get_paginator('list_stack_instances')
        iterator = paginator.paginate(StackSetName='AWSControlTowerBP-BASELINE-CONFIG',
            StackInstanceAccount=account_id)
        for page in iterator:
            for summary in page['Summaries']:
                region_set.add(summary['Region'])
    except Exception as ex:
        print("Control Tower StackSet not found in this Region")
        print(str(ex))
    print(f"Control Tower Regions: {list(region_set)}")
    return list(region_set)

def start_workflow(input):
    sm_name = os.environ['sm_name']
    print('Search for StateMachine Name: {} ..'.format(sm_name))
    try:
        sfn_client = session.client('stepfunctions')
        sm_arn = ''
        exec_id = date.strftime(datetime.now(), '%Y%m%d%I%M%S')
        response = sfn_client.list_state_machines()
        for sm in response['stateMachines']:
            if sm['name'] == sm_name:
                sm_arn = sm['stateMachineArn']
                break
        print("Invoking StateMachine Arn: {} ..".format(sm_arn))
        response = sfn_client.start_execution(
            stateMachineArn=sm_arn,
            name=exec_id,
            input=json.dumps(input)
        )
        execArn = response['executionArn']
        print('StateMachine: {} started with Execution ARN: {}'.format(sm_name, execArn))
    except Exception as e:
        print('Failed to execute StateMachine: {}'.format(sm_name))
        print(str(e))

def prepare_input(event, member):
    org_id = os.environ['org_id']
    ct_home_region = os.environ['ct_home_region']
    sh_admin_account = os.environ['sh_admin_account']
    assume_role_name = os.environ['assume_role']
    compliance_frequency = os.environ['compliance_frequency']
    enable_aws_standard = os.environ['enable_aws_standard']
    enable_cis_standard = os.environ['enable_cis_standard']
    member_account = member['account_id']
    member_email = member['email']
    ou_id = member['org_unit_id']
    sh_regions = get_ct_regions(sh_admin_account)
    sh_member_regions = []
    for region in sh_regions:
        sh_member_regions.append({
            'org_id': org_id,
            'org_unit_id': ou_id,
            'ct_home_region': ct_home_region,
            'sh_admin_account': sh_admin_account,
            'assume_role': assume_role_name,
            'compliance_frequency': compliance_frequency,
            'enable_aws_standard': enable_aws_standard,
            'enable_cis_standard': enable_cis_standard,
            'member_account': member_account,
            'member_email': member_email,
            'member_region': region
        })
    return sh_member_regions

def lambda_handler(event, context):
    print(f"REQUEST RECEIVED: {json.dumps(event, default=str)}")
    member = get_account_from_ct_event(event)
    print(json.dumps(member, indent=2))
    if member['state'] != 'SUCCEEDED':
        print('Account Enrolment for Account: %s is not in SUCCEEDED State. SecurityHub will not be enabled.' % member['account_id'])
    else:
        input = prepare_input(event, member)
        start_workflow(input)


