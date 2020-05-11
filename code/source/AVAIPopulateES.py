# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
  
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   A copy of the License is located at
  
#       http://www.apache.org/licenses/LICENSE-2.0
  
#   or in the "license" file accompanying this file. This file is distributed 
#   on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either 
#   express or implied. See the License for the specific language governing 
#   permissions and limitations under the License.

import sys
sys.path.insert(0, '/opt')
import boto3
import requests
from requests_aws4auth import AWS4Auth
from urllib.parse import unquote_plus
import json
import os

my_session = boto3.session.Session()
region = my_session.region_name

# variables that will be used in the code
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
host =  'https://{0}'.format(unquote_plus(os.environ['ES_DOMAIN']))
index = 'avai_index'
type = '_doc'
docurl = host + '/' + index + '/' + type + '/'
indexurl = host+ '/' + index
headers = { "Content-Type": "application/json" }

index_body = {
    "mappings": {
      "properties": {
        "ROWID": {
            "type": "keyword"
        },
        "Location": {
            "type": "keyword"
        },
        "AssetType": {
            "type": "keyword"
        },
        "Operation": {
            "type": "keyword"
        },
        "Tag": {
            "type": "keyword"
        },
        "Confidence": {
            "type": "float"
        },
        "Face_Id": {
            "type": "integer"
        },
        "Value": {
            "type": "keyword"
        },
        "TimeStamp": {
            "type": "date"
        }
      }
    }
  }

def lambda_handler(event, context):
    
    # Check if index exists
    response = requests.get(indexurl, auth=awsauth, headers=headers)
    if not response.ok:
        # create index
        response = requests.put(indexurl, auth=awsauth, json=index_body, headers=headers)
    
    count = 0
    for record in event['Records']:
        # Get the primary key for use as the Elasticsearch ID
        id = record['dynamodb']['Keys']['ROWID']['S'] 
        
        if record['eventName'] == 'REMOVE':
            r = requests.delete(docurl + id, auth=awsauth)
        else:
            document = record['dynamodb']['NewImage']
            # create index document
            item = {}
            item['AssetType'] = document['AssetType']['S']
            item['Confidence'] = float(document['Confidence']['N'])
            item['Operation'] = document['Operation']['S']
            item['Tag'] = document['Tag']['S']
            item['ROWID'] = document['ROWID']['S']
            item['TimeStamp'] = int(document['TimeStamp']['N'])
            if 'Face_Id' in document:
                item['Face_Id'] = int(document['Face_Id']['N'])
            if 'Value' in document:
                item['Value'] = document['Value']['S']
            item['Location'] = document['Location']['S']
            # print(json.dumps(item))
            r = requests.put(docurl + id, auth=awsauth, json=item, headers=headers)
        count += 1
        print(str(count) + ' records processed.')
    return str(count) + ' records processed.'