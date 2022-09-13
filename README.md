# Setup Security Hub in Control Tower Landing Zone
- This automation code enables SecurityHub Master/Admin on Audit/Security Account and SecurityHub Member/Child on Member accounts

## Instructions

1. Upload files to **org-sh-ops**:
  - src/sh_admin_enabler.zip to S3 Bucket. Note down the S3 Key
  - src/sh_member_enabler.zip to S3 Bucket. Note down the S3 Key
  - src/sh_member_invite.zip to S3 Bucket. Note down the S3 Key
  - src/sh_sm_launcher.zip to S3 Bucket. Note down the S3 Key
  - sh_enabler_sm.json to S3 Bucket. Note down the S3 Key
    - *This is referred as* **SecurityHubEnablerSM** *statemachine*
  - securityhub-enabler1.yaml to S3 Bucket

## Control Tower
- This automation is part of Control Tower Customizations Pipeline.
  - Manual launch of CF Template is not required
  - Files mentioned MUST be uploaded to **org-sh-ops** S3 Bucket on Master Account

## Launch sequence
1. Enrol Account to CT (either: Re-register OU where new Account exists, or use Account Factory)
  - On successful enrolment of Account, **SecurityHubEnablerSM** *statemachine* is launched

## State Machine
- State Machine attempts to enable SecurityHub on member account that belong to provided Organizational Unit
- State Machine attempts to enable SecurityHub Organizational Admin on Audit/Security account in all CT-governed regions
  - State Machine attempts to add Member to Admin Account
- State Machine attempts to Accept Admin Invite on member account
- Last Task in State Machine sends a custom event `SecurityHubEnabled` targeted to **SHRemediatorSMLauncher** Lambda
  - **SHRemediatorSMLauncher** launches `cis-benchmark-remediation` on Member Account in all CT-governed regions

*NOTE*
- In case the resources are pre-configured / pre-existed, then execution is idempotent.

![sh_enabler_sm.png](./sh_enabler_sm.png?raw=true)

## Considerations
- This automation is aimed to enable SecurityHub on a freshly encolled Account
- This automation is triggered on successful enrolment of Account
- Prior to enrolment of Account, ensure the `AWS Config service` is enabled on the Account (being enrolled)
