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
import json
import uuid
import decimal
import time
import os
from urllib.parse import unquote_plus

dynamoDBResource = boto3.resource('dynamodb', region_name = 'us-east-1')

sqs = boto3.client('sqs')
rekognition = boto3.client('rekognition')
hera  = boto3.client(service_name='comprehendmedical', use_ssl=True, region_name = 'us-east-1')
textract = boto3.client('textract',region_name='us-east-1')
transcribe = boto3.client('transcribe',region_name='us-east-1')
s3 = boto3.resource('s3')

# queueName = 'VSS_Incoming_Queue.fifo'
queueName = unquote_plus(os.environ['QUEUE_NAME'])
    
# ddb_table = 'mayank-sandstone-demo'
ddb_table = unquote_plus(os.environ['DDB_TABLE'])

table = dynamoDBResource.Table(ddb_table)


def lambda_handler(event, context):

    
    queue_url = sqs.get_queue_url(
                            QueueName=queueName
                        )['QueueUrl']
    
    # Receive message from SQS queue
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        MessageAttributeNames=[
            'All'
        ],
        VisibilityTimeout=90,
        WaitTimeSeconds=3
    )
    
    if 'Messages' in response:
        print (('Found {0} messages, processing').format(str(len(response['Messages']))))
        for message in response['Messages']:
            receipt_handle = message['ReceiptHandle']
            
            messageBody = json.loads(message['Body'])
            
            try:

                if (messageBody['keyName'].lower().endswith('.jpg') 
                        or messageBody['keyName'].lower().endswith('.jpeg') 
                        or messageBody['keyName'].lower().endswith('.png')):
                    # Process the image.
                    process_image(messageBody)
                    
                if (messageBody['keyName'].lower().endswith('.txt')):
                    print("Processing Document: {0}/{1}".format(messageBody['bucketName'], messageBody['keyName']))
                    #get the S3 object
                    bucket = s3.Bucket(messageBody['bucketName'])
                    fileText = bucket.Object(messageBody['keyName']).get()['Body'].read().decode("utf-8", 'ignore')
                    # Process the document.
                    process_document(messageBody['bucketName'], messageBody['keyName'], fileText, 'Text-file')

                if (messageBody['keyName'].lower().endswith('.pdf')):
                    process_pdf(messageBody)

                if (messageBody['keyName'].lower().endswith('.mp3') 
                    or messageBody['keyName'].lower().endswith('.mp4') 
                    or messageBody['keyName'].lower().endswith('.flac') 
                    or messageBody['keyName'].lower().endswith('.wav')):
                    process_audio(messageBody)
            except:
                print("Something went wrong processing " + str(messageBody['keyName']))

            # Delete received message from queue
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            # print('Received and deleted message: %s' % message)
    else:
        print ('No messages found in queue.')

def process_audio(messageBody):
    if messageBody is not None:
        
        bucketName = messageBody['bucketName']
        keyName = unquote_plus(messageBody['keyName'])
        
        print("Processing audio file: {0}/{1}".format(bucketName, keyName))
        
        # call start_transcription_job
        print('Calling start_transcription_job')

        mediaFormat = keyName[keyName.rindex('.')+1:len(keyName)]
        transcriptionJobName = str(uuid.uuid4())
        response = transcribe.start_transcription_job(
                    TranscriptionJobName = transcriptionJobName,
                    LanguageCode = 'en-US',
                    MediaFormat = mediaFormat,
                    Media={
                                'MediaFileUri': 's3://{0}/{1}'.format(bucketName,keyName)
                            },
                    OutputBucketName = bucketName
                    )

        transcribeResponse = None
        while True:
            print('Calling get_transcription_job...')
            transcribeResponse = transcribe.get_transcription_job(
                                TranscriptionJobName=transcriptionJobName
                        )
            print(transcribeResponse['TranscriptionJob']['TranscriptionJobStatus'] )
            if (transcribeResponse['TranscriptionJob']['TranscriptionJobStatus'] != 'IN_PROGRESS' and 
                transcribeResponse['TranscriptionJob']['TranscriptionJobStatus'] != 'QUEUED'):
                break
            time.sleep(3)
        
        if transcribeResponse is not None:
            if transcribeResponse['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                print('Success')
                s3location = transcribeResponse['TranscriptionJob']['Transcript']['TranscriptFileUri']
                # print(s3location)
                s3location = s3location.replace('https://s3.amazonaws.com/','')
                print ('Text extracted from audio. Proceeding to extract clinical entities from the text...')
                #get the S3 object
                bucket = s3.Bucket(bucketName)
                # print(s3location[s3location.index('/') + 1: len(s3location)])
                targetKeyName = s3location[s3location.index('/') + 1: len(s3location)]
                fileText = bucket.Object(targetKeyName).get()['Body'].read().decode("utf-8", 'ignore')
                # print(json.loads(fileText)['results']['transcripts'][0]['transcript'])
                # delete the transcribe output
                print ('Deleting transcribe output')
                bucket.Object(targetKeyName).delete()
                process_document(bucketName, keyName, fileText, 'Audio-file')
            else:
                print('Failure')
        else:
            print('Failure')


def process_pdf(messageBody):
    if messageBody is not None:
        
        bucketName = messageBody['bucketName']
        keyName = unquote_plus(messageBody['keyName'])
        
        print("Processing document: {0}/{1}".format(bucketName, keyName))
        
        # call detect_document_text
        print('Calling detect_document_text')

        response = textract.start_document_text_detection(
                    DocumentLocation={
                        'S3Object': {
                            'Bucket': bucketName,
                            'Name': keyName
                        }
                    })

        textractResponse = None
        while True:
            print('Calling get_document_text_detection...')
            textractResponse = textract.get_document_text_detection(
                            JobId=response['JobId'],
                            MaxResults=1000
                        )
            print(textractResponse['JobStatus'] )
            if textractResponse['JobStatus'] != 'IN_PROGRESS':
                break
            time.sleep(2)
        
        if textractResponse is not None:
            if textractResponse['JobStatus'] == 'SUCCEEDED':
                print('Success')
                textract_output = ''
                for Blocks in textractResponse["Blocks"]:
                    if Blocks['BlockType']=='LINE':
                        line = Blocks['Text']
                        textract_output = textract_output + line +'\n'
                print ('Text extracted from image. Proceeding to extract clinical entities from the text...')
                process_document(messageBody['bucketName'], messageBody['keyName'],textract_output, 'PDF-file')
            else:
                print('Failure')
        else:
            print('Failure')
                
        

        
def process_document(bucketName, keyName, fileText, assetType):
    if fileText != '':
        
        if assetType == '':
            assetType = 'Text-file'

        # comprehend medical has a input size limit of 20,000 characters.

        if len(fileText) > 20000:
            fileText = fileText[0:20000]

        
        # time in milliseconds
        timestamp = int(round(time.time() * 1000))

         # call detect_entities
        print('Calling detect_entities')

        # Call the detect_entities API to extract the entities
        testresult = hera.detect_entities(Text = fileText)

         # Create a list of entities
        testentities = testresult['Entities']

        Trait_List = []
        Attribute_List = []


        with table.batch_writer() as batch:
            # Create a loop to iterate through the individual entities
            for row in testentities:
                # Remove PHI from the extracted entites
                if row['Category'] != "PERSONAL_IDENTIFIABLE_INFORMATION":
                    
                    # Create a loop to iterate through each key in a row 
                    for key in row:
                        
                        # Create a list of traits
                        if key == 'Traits':
                            if len(row[key])>0:
                                Trait_List = []
                                for r in row[key]:
                                    Trait_List.append(r['Name'])
                        
                        # Create a list of Attributes
                        elif key == 'Attributes':
                            Attribute_List = []
                            for r in row[key]:
                                Attribute_List.append(r['Type']+':'+r['Text'])
            
                batch.put_item(
                        Item={
                            'ROWID': str(uuid.uuid4()),
                            'Location': bucketName + '/' + keyName,
                            'AssetType': assetType,
                            'Operation' : 'DETECT_ENTITIES',
                            'Tag': row['Text'],
                            'Confidence': decimal.Decimal(row['Score']) * 100,
                            'Detect_Entities_Type' : row['Type'],
                            'Detect_Entities_Category' : row['Category'],
                            'Detect_Entities_Trait_List' : str(Trait_List),
                            'Detect_Entities_Attribute_List' : str(Attribute_List),
                            'TimeStamp': timestamp
                            }
                        )
        print('Tags inserted in DynamoDB.')
    


def process_image(messageBody):
     if messageBody is not None:
        
        # time in milliseconds
        timestamp = int(round(time.time() * 1000))
        print("Processing Image: {0}/{1}".format(messageBody['bucketName'], messageBody['keyName']))
        
        # call detect_labels
        print('Calling detect_labels')
        response = rekognition.detect_labels(
                            Image={
                                'S3Object': {
                                    'Bucket': messageBody['bucketName'],
                                    'Name': messageBody['keyName']
                                }
                            }
                        )
                        
        # create data structure and insert in DDB
        labels = []
        faceDetails = []
        bIfPerson = False
        
        with table.batch_writer() as batch:
            for label in response['Labels']:
                batch.put_item(
                    Item={
                        'ROWID': str(uuid.uuid4()),
                        'Location': messageBody['bucketName'] + '/' + messageBody['keyName'],
                        'AssetType': 'Image',
                        'Operation' : 'DETECT_LABEL',
                        'Tag': label['Name'],
                        'Confidence': decimal.Decimal(label['Confidence']),
                        'TimeStamp': timestamp
                        }
                    )
                
                if (label['Name'] == 'Human' or label['Name'] == 'Person') and (float(label['Confidence']) > 80):
                    bIfPerson = True
                
                
            if bIfPerson: # person detected, call detect faces
                # call detect_faces
                print('Calling detect_faces')
                response = rekognition.detect_faces(
                            Image={
                                'S3Object': {
                                    'Bucket': messageBody['bucketName'],
                                    'Name': messageBody['keyName']
                                }
                            },
                            Attributes=['ALL']
                        )
                # print(json.dumps(response))        
                # faceDetails = response['FaceDetails']
                index = 1
                for faceDetail in response['FaceDetails']:
                    del faceDetail['BoundingBox']
                    del faceDetail['Landmarks']
                    del faceDetail['Pose']
                    del faceDetail['Quality']
                    faceDetailConfidence = faceDetail['Confidence']
                    del faceDetail['Confidence']
                    
                    for (k,v) in faceDetail.items():
                        if(k == 'Emotions'):
                            for emotion in v:
                                batch.put_item(
                                    Item={
                                        'ROWID': str(uuid.uuid4()),
                                        'Location': messageBody['bucketName'] + '/' + messageBody['keyName'],
                                        'AssetType': 'Image',
                                        'Operation' : 'DETECT_FACE',
                                        'Face_Id' : index,
                                        'Tag': emotion['Type'],
                                        # 'Value': v['Value'],
                                        'Confidence': decimal.Decimal(emotion['Confidence']),
                                        'TimeStamp': timestamp
                                        }
                                    )
                            continue
                        
                        if(k == 'AgeRange'):
                            batch.put_item(
                                    Item={
                                        'ROWID': str(uuid.uuid4()),
                                        'Location': messageBody['bucketName'] + '/' + messageBody['keyName'],
                                        'AssetType': 'Image',
                                        'Operation' : 'DETECT_FACE',
                                        'Face_Id' : index,
                                        'Tag': k + '_Low',
                                        'Value': str(v['Low']),
                                        'Confidence': decimal.Decimal(faceDetailConfidence),
                                        'TimeStamp': timestamp
                                        }
                                    )
                            
                            batch.put_item(
                                    Item={
                                        'ROWID': str(uuid.uuid4()),
                                        'Location': messageBody['bucketName'] + '/' + messageBody['keyName'],
                                        'AssetType': 'Image',
                                        'Operation' : 'DETECT_FACE',
                                        'Face_Id' : index,
                                        'Tag': k + '_High',
                                        'Value': str(v['High']),
                                        'Confidence': decimal.Decimal(faceDetailConfidence),
                                        'TimeStamp': timestamp
                                        }
                                    )
                            continue
                            
                        batch.put_item(
                                Item={
                                    'ROWID': str(uuid.uuid4()),
                                    'Location': messageBody['bucketName'] + '/' + messageBody['keyName'],
                                    'AssetType': 'Image',
                                    'Operation' : 'DETECT_FACE',
                                    'Face_Id' : index,
                                    'Tag': k,
                                    'Value': str(v['Value']),
                                    'Confidence': decimal.Decimal(v['Confidence']),
                                    'TimeStamp': timestamp
                                    }
                                )
                    index+=1
      

                # call detect_text
                print('Calling detect_text')
                response = rekognition.detect_text(
                                    Image={
                                        'S3Object': {
                                            'Bucket': messageBody['bucketName'],
                                            'Name': messageBody['keyName']
                                        }
                                    }
                                )
                # create data structure and insert in DDB
                # textDetections = []
                
                
                
                for text in response['TextDetections']:
                    if text['Type'] == 'LINE':
                        
                        # textDetections.append(text['DetectedText']+':'+str(text['Confidence']))
                        
                        # textDetections.append({
                        #     'DetectedText' : text['DetectedText'],
                        #     'Confidence' : text['Confidence']
                        #         }
                        # )
                        
                        batch.put_item(
                            Item={
                                'ROWID': str(uuid.uuid4()),
                                'Location': messageBody['bucketName'] + '/' + messageBody['keyName'],
                                'AssetType': 'Image',
                                'Operation' : 'DETECT_TEXT',
                                'Tag': text['DetectedText'],
                                'Confidence': decimal.Decimal(text['Confidence']),
                                'TimeStamp': timestamp
                                }
                            )
        
        print('Tags inserted in DynamoDB.')
        return 1
