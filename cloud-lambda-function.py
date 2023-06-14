import json
import boto3
import uuid

img_formats = ["jpg", "jpeg", "png"]
output_bucket = "outputbucketcloudproject"
s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")
dynamodb=boto3.resource('dynamodb',region_name="us-east-1")
table=dynamodb.Table('cloudtable')

class Label:
    """Label class: Objects identified in an image
        - name [string]       : name of the object
        - confidence [double] : confidence of the model
    """
    def __init__(self, name, confidence):
        self.name = name
        self.confidence = confidence

    def __str__(self):
        return '<Name: %s, Confidence: %s>' % (self.name, self.confidence)
    
    def to_json(self):
        return json.dumps(self, default = lambda o: o.__dict__)

        
class Response():
    """Response class: image coming from the S3 PUT event and analyzed with AWS Rekognition
        - name [string]          : name of the S3 object
        - size [string]          : size in bytes
        - input_bucket [string]  : name of the bucket
        - creation_date [string] : datetime of object loading event
        - max_labels [int]       : max number of labels to detect
        - min_confidence [int]   : confidence threshold
        - labels [list]          : list of Label objects
    """
    def __init__(self, name, size, input_bucket, creation_date, max_labels, min_confidence):
        self.name = name
        self.size = size
        self.input_bucket = input_bucket
        self.creation_date = creation_date
        self.max_labels = max_labels
        self.min_confidence = min_confidence
        self.labels = self.detect_labels()
        
    def detect_labels(self):
        '''Call to AWS Rekognition for object detection'''
        print("Call to AWS Rekognition for object detection on image '{}'".format(self.name))
        response = rekognition.detect_labels(
          Image = {
            "S3Object": {
              "Bucket" : self.input_bucket,
              "Name" : self.name
              }
          },
          MaxLabels = self.max_labels,
          MinConfidence = self.min_confidence
        )
        labels = []
        [labels.append(Label(obj["Name"], obj["Confidence"])) for obj in response["Labels"]] 
        return labels
    
    def __str__(self):
        return '<name: %s (%s bytes) - bucket: %s>' % (self.name, self.size, self.input_bucket)
    
    def to_json(self):
        return json.dumps(self, default = lambda o: o.__dict__)


def save_analysis(obj):
    response = s3.put_object(
          Body = json.dumps(obj.to_json()),
          Bucket = output_bucket,
          Key = obj.name + '.json'
        )

def checkImage(name):
    response1=table.get_item(Key={"inputImage":str(name)})
    if "Item" in response1.keys():
        return 1
    
def lambda_handler(event, context):
    '''Method run by Lambda when the function is invoked''' 

    name = event["Records"][0]["s3"]["object"]["key"]

    if not any(format in name.lower() for format in img_formats):
        print("Unprocessable Entity: input object must be a jpg or png.")
        return {
          "statusCode": 422,
          "body" : json.dumps("Unprocessable Entity: input object must be a jpg or png.")
        }
    else:
        if checkImage(name):
            return {
              "statusCode": 200,
            }
        else:
            obj = Response(
                name = name,
                size = event["Records"][0]["s3"]["object"]["size"],
                input_bucket = event["Records"][0]["s3"]["bucket"]["name"],
                creation_date = event["Records"][0]["eventTime"],
                max_labels = 10,
                min_confidence = 70
            )

            print("Labels found: ")
            [print(label) for label in obj.labels]
           
            save_analysis(obj)
            response=table.put_item(    Item={
                "inputImage":name
            }
            )
            return {
              "statusCode": 200,
              "body" : json.dumps("Object {} analyzed successfully!".format(obj.name))
            }