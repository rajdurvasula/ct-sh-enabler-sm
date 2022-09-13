#!/bin/bash
if [ $# -ne 1 ]; then
	echo "Expected Argument: bucket_name"
	exit 0
fi
for i in src/*.zip
do
	filename=$(basename $i)
	aws s3 rm s3://$1/$filename
done
aws s3 rm s3://$1/securityhub-enabler.yaml
aws s3 rm s3://$1/sh_enabler_sm_event.json
