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

def assume_role(org_id, aws_account_number, role_name):
    sts_client = boto3.client('sts')
    partition = sts_client.get_caller_identity()['Arn'].split(":")[1]
    response = sts_client.assume_role(
        RoleArn='arn:%s:iam::%s:role/%s' % (
            partition, aws_account_number, role_name
        ),
        RoleSessionName=str(aws_account_number+'-'+role_name),
        ExternalId=org_id
    )
    sts_session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken']
    )
    print(f"Assumed region_session for Account {aws_account_number}")
    return sts_session

def accept_invitation(member_session, member_account, sh_admin_account, region):
    try:
        sh_client = member_session.client('securityhub', 
            endpoint_url=f"https://securityhub.{region}.amazonaws.com", 
            region_name=region)
        response = sh_client.list_invitations()
        for invite in response['Invitations']:
            if invite['AccountId'] == sh_admin_account:
                invitationId = invite['InvitationId']
                try:
                    sh_client.accept_administrator_invitation(
                        AdministratorId=sh_admin_account,
                        InvitationId=invitationId
                    )
                    print('Member: {} accepted Invite from Admin: {} in Region: {}'.format(
                        member_account, sh_admin_account, region
                    ))
                except Exception as ex:
                    print('Member: {} could not accept Invite from Admin: {} in Region: {}'.format(
                        member_account, sh_admin_account, region
                    ))
                    print(str(ex))
            else:
                print('Invitation from Admin: {} for Member: {} NOT FOUND in Region: {} !'.format(
                    sh_admin_account, member_account, region
                ))
    except Exception as e:
        print('Member: {} failed to Accept Invitation from Admin: {} in Region: {}'.format(
            member_account, sh_admin_account, region
        ))
        print(str(e))

def lambda_handler(event, context):
    print(f"REQUEST RECEIVED: {json.dumps(event, default=str)}")
    org_id = event['org_id']
    ou_id = event['org_unit_id']
    ct_home_region = event['ct_home_region']
    sh_admin_account = event['sh_admin_account']
    assume_role_name = event['assume_role']
    compliance_frequency = event['compliance_frequency']
    enable_aws_standard = event['enable_aws_standard']
    enable_cis_standard = event['enable_cis_standard']
    member_account = event['member_account']
    member_email = event['member_email']
    member_region = event['member_region']
    security_standards = [ { 'aws': enable_aws_standard, 'cis': enable_cis_standard } ]
    member_session = assume_role(org_id, member_account, assume_role_name)
    accept_invitation(member_session, member_account, sh_admin_account, member_region)
    return {
        'statusCode': 200,
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
        'member_region': member_region
    }