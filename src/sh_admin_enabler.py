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

def enable_admin(sh_admin_session, sh_admin_account, region, security_standards):
    try:
        sh_admin_client = sh_admin_session.client('securityhub', 
        endpoint_url=f"https://securityhub.{region}.amazonaws.com", 
        region_name=region)
        # make inexpensive call as much possible
        paginator = sh_admin_client.get_paginator('get_findings')
        filters = {
            'AwsAccountId': [
                {
                    'Value': sh_admin_account,
                    'Comparison': 'EQUALS'
                }
            ],
            'Region': [
                {
                    'Value': region,
                    'Comparison': 'EQUALS'
                }
            ]
        }
        iterator = paginator.paginate(Filters=filters)
        findings = []
        for page in iterator:
            for finding in page['Findings']:
                findings.append(finding)
            # break on 1st page
            break
        if len(findings) > 0:
            print("Findings: {} found Region: {}".format(len(findings), region))
        else:
            # no findings is assumed SecurityHub is not enabled
            print("No findings. Enable SecurityHub Admin ..")
            try:
                sh_admin_client.enable_security_hub(EnableDefaultStandards=False)
                print("Enabled SecurityHub on Account: {} in Region: {}".format(sh_admin_account, region))
                # enable standards
                standards = process_security_standards(sh_admin_session, sh_admin_account, region, security_standards)
            except Exception as ex:
                print("Failed to enable SecurityHub on Account: {} in Region: {}".format(sh_admin_account, region))
                print(str(e))
    except Exception as e:
        print("Failed to enable SecurityHub Admin for Account: {} in Region: {}".format(sh_admin_account, region))
        print(str(e))

def process_security_standards(sh_session, sh_account, region, security_standards):
    try:
        sh_client = sh_session.client('securityhub', 
            endpoint_url=f"https://securityhub.{region}.amazonaws.com", 
            region_name=region)
        # AWS standard ARNs
        aws_standard_arn = 'arn:aws:securityhub:{}::standards/aws-foundational-security-best-practices/v/1.0.0'.format(region)
        aws_subscription_arn = 'arn:aws:securityhub:{}:{}:subscription/aws-foundational-security-best-practices/v/1.0.0'.format(region, sh_account)
        # CIS standard ARNs
        cis_standard_arn = 'arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.2.0'
        cis_subscription_arn = 'arn:aws:securityhub:{}:{}:subscription/cis-aws-foundations-benchmark/v/1.2.0'.format(region, sh_account)
        aws_standard_enabled = False
        cis_standard_enabled = False
        enabled_standards = sh_client.get_enabled_standards()
        for enabled_standard in enabled_standards['StandardsSubscriptions']:
            if aws_standard_arn in enabled_standard['StandardsArn']:
                aws_standard_enabled = True
            if cis_standard_arn in enabled_standard['StandardsArn']:
                cis_standard_enabled = True
        for standard in security_standards:
            if standard['aws'] == 'yes':
                if aws_standard_enabled:
                    print('Standard: {} is already enabled in Account: {} in Region: {}'.format(aws_standard_arn, sh_account, region))
                else:
                    try:
                        sh_client.batch_enable_standards(
                            StandardsSubscriptionRequests=[
                                {
                                    'StandardsArn': aws_standard_arn
                                }
                            ]
                        )
                        print('Standard: {} is enabled in Account: {} in Region: {}'.format(aws_standard_arn, sh_account, region))
                    except Exception as ex:
                        print('Failed to enable Standard: {} in Account: {} in Region: {}'.format(aws_standard_arn, sh_account, region))
                        print(str(ex))
                        raise ex
            elif standard['aws'] == 'no':
                try:
                    sh_client.batch_disable_standards(StandardsSubscriptionArns=[aws_subscription_arn])
                    print('Standard: {} is disabled in Account: {} in Region: {}'.format(aws_standard_arn, sh_account, region))
                except Exception as ex:
                    print('Failed to disable Standard: {} in Account: {} in Region: {}'.format(aws_standard_arn, sh_account, region))
                    print(str(ex))
                    raise ex
            if standard['cis'] == 'yes':
                if cis_standard_enabled:
                    print('Standard: {} is already enabled in Account: {} in Region: {}'.format(cis_standard_arn, sh_account, region))
                else:
                    try:
                        sh_client.batch_enable_standards(
                            StandardsSubscriptionRequests=[
                                {
                                    'StandardsArn': cis_standard_arn
                                }
                            ]
                        )
                        print('Standard: {} is enabled in Account: {} in Region: {}'.format(cis_standard_arn, sh_account, region))
                    except Exception as ex:
                        print('Failed to enable Standard: {} in Account: {} in Region: {}'.format(cis_standard_arn, sh_account, region))
                        print(str(ex))
                        raise ex
            elif standard['cis'] == 'no':
                try:
                    sh_client.batch_disable_standards(StandardsSubscriptionArns=[cis_subscription_arn])
                    print('Standard: {} is disabled in Account: {} in Region: {}'.format(cis_standard_arn, sh_account, region))
                except Exception as ex:
                    print('Failed to disable Standard: {} in Account: {} in Region: {}'.format(cis_standard_arn, sh_account, region))
                    print(str(ex))
                    raise ex
    except Exception as e:
        print(f"Failed to enable security standards: {e}")
        print(str(e))
    return security_standards

def add_member(sh_admin_session, sh_admin_account, sh_region, member_account, member_email):
    unprocessed_accounts = []
    try:
        sh_admin_client = sh_admin_session.client('securityhub',
        endpoint_url=f"https://securityhub.{sh_region}.amazonaws.com",
        region_name=sh_region)
        response = sh_admin_client.create_members(
            AccountDetails=[
                {
                    'AccountId': member_account,
                    'Email': member_email
                }
            ]
        )
        if len(response['UnprocessedAccounts']) > 0:
            unprocessed_accounts = response['UnprocessedAccounts']
            for unprocessed_account in unprocessed_accounts:
                print('Account: {} could not be processed by Admin: {} in Region: {}'.format(
                    unprocessed_account, sh_admin_account, sh_region
                ))
        else:
            print('API call create_members(..) successful')
            unprocessed_accounts = create_invite(sh_admin_client, sh_admin_account, member_account, sh_region)
    except Exception as e:
        print('Failed to add Member: {} to Admin: {} in Region: {}'.format(member_account, sh_admin_account, sh_region))
        print(str(e))
    return unprocessed_accounts

def create_invite(sh_admin_client, sh_admin_account, member_account, sh_region):
    try:
        response = sh_admin_client.invite_members(AccountIds=[member_account])
        unprocessed_accounts = response['UnprocessedAccounts']
        if len(response['UnprocessedAccounts']) > 0:
            unprocessed_accounts = response['UnprocessedAccounts']
            for unprocessed_account in unprocessed_accounts:
                print('Account: {} could not be processed by Admin: {} in Region: {}'.format(
                    unprocessed_account, sh_admin_account, sh_region
                ))
        else:
            print('API call invite_members(..) successful')
        return unprocessed_accounts
    except Exception as e:
        print('Failed to Create Invitation for Member: {} to Admin: {} in Region: {}'.format(member_account, sh_admin_account, sh_region))
        print(str(e))
        raise e

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
    sh_admin_session = assume_role(org_id, sh_admin_account, assume_role_name)
    enabled_regions_standards = enable_admin(sh_admin_session, sh_admin_account, member_region, security_standards)
    unprocessed_accounts = add_member(sh_admin_session, sh_admin_account, member_region, member_account, member_email)
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
        'member_region': member_region,
        'unprocessed_accounts': unprocessed_accounts
    }