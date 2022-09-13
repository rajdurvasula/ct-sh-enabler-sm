#!/bin/bash
if [ $# -ne 1 ]; then
	echo "Expected argument: bucket_name"
	exit 0
fi
for i in src/*.zip
do
	filename=$(basename $i)
	aws s3 cp src/$filename s3://$1/
done
aws s3 cp securityhub-enabler.yaml s3://$1/
aws s3 cp sh_enabler_sm_event-3.json s3://$1/
