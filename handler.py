# -*- coding: utf-8 -*-

import boto3
import os
import json
from base64 import b64decode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

kms = boto3.client('kms')
s3 = boto3.client('s3')

region = os.environ['AWS_REGION']
encrypted_slack_endpoint = os.environ['SLACK_ENDPOINT']
slack_endpoint = 'https://' + \
    kms.decrypt(CiphertextBlob=b64decode(encrypted_slack_endpoint))['Plaintext'].decode('utf-8')
slack_channel = os.environ['SLACK_CHANNEL']
slack_username = os.environ['SLACK_USERNAME']
slack_icon_emoji = os.environ['SLACK_ICON_EMOJI']
artifacts_bucket = os.environ['ARTIFACTS_BUCKET']
result_url_expire = os.environ['RESULT_URL_EXPIRE']


def select_slack_status_color(status):
    """
    """
    if status == 'IN_PROGRESS':
        color = '#00D6F2'
    elif status == 'SUCCEEDED':
        color = '#00E03B'
    elif status == 'FAILED' or status == 'STOPPED':
        color = '#F35A00'
    else:
        color = '#F2E200'

    return color


def generate_slack_filelds(name, buildid, status, url):
    """
    """
    fields = [
        {
            'title': 'Build Name',
            'value': name,
        },
        {
            'title': 'Build ID',
            'value': buildid,
        },
        {
            'title': 'Status',
            'value': status,
        },
     ]

    if status == 'SUCCEEDED' or status == 'FAILED':
        if not url == 'NoURL':
            url_field = {
                'title': 'Result URL',
                'value': url,
            }
            fields.append(url_field)

    return fields


def post_to_slack(result_parm, message):
    """
      Description: Slack への通知
    """
    print(message)

    buildid = result_parm['id']
    name = result_parm['name']
    status = result_parm['status']
    url = result_parm['url']

    color = select_slack_status_color(status)
    fields = generate_slack_filelds(name, buildid, status, url)

    attachement = {
        'fallback': message,
        'text': message,
        'fields': fields,
        'color': color
    }

    slack_message = {
        'channel': slack_channel,
        'username': slack_username,
        'icon_emoji': slack_icon_emoji,
        'attachments': [attachement]
    }

    payload = json.dumps(slack_message)
    req = Request(slack_endpoint, payload.encode('UTF-8'))
    try:
        response = urlopen(req)
        response.read()
    except HTTPError as e:
        print("Request failed: %d %s" % e.code, e.reason)
    except URLError as e:
        print("Server connection failed: %s" % e.reason)


def generate_result_url(build_id, build_name):
    _id = build_id.split(":")[6]
    key = 'html/%s/%s/result.html' % (build_name, _id)
    params = {'Bucket': artifacts_bucket, 'Key': key}
    try:
        result_url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params=params,
            ExpiresIn=int(result_url_expire),
            HttpMethod='GET')
        return result_url
    except:
        print('Get Object failed: %s' % key)
        return 'NoURL'


def notify(event, context):
    build_detail = event['detail']
    build_name = build_detail['project-name']
    build_id = build_detail['build-id']

    build_status = build_detail['build-status']

    result_parm = {}
    result_parm['id'] = build_id
    result_parm['name'] = build_name
    result_parm['status'] = build_status

    if build_status == "IN_PROGRESS":
        message = build_name + " のテストが開始しました. :dash:"
        result_parm['url'] = "NoURL"
    elif build_status == "STOPPED":
        message = build_name + " のテストを強制終了しました. :dash:"
        result_parm['url'] = "NoURL"
    else:
        message = build_name + " のテストが " + build_status + " しました. :bow:"
        result_parm['url'] = generate_result_url(build_id, build_name)

    post_to_slack(result_parm, message)
