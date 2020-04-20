# aws-ai-veeva-integation
A integration between Veeva Vault and AWS, levaraging AWS AI services to intelligently analyze images, PDFs and audio assets.
# Deployment and Execution

## Prerequisites

1. Download and install the latest version of Python for your OS from [here](https://www.python.org/downloads/). We shall be using Python 3.8 and above.

2. You will be needing [AWS CLI version 2](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) as well. If you already have AWS CLI, please upgrade to a minimum version of 2.0.5 follwing the instructions on the link above.

## Instructions

This code depends on a bunch of libraries (not included in this distribution) which you will have to install yourself.  The code comes with a SAM template, which you can use to deploy the entire solution.

1. Download the contents of this repository on your local machine (say: project-directory)
2. The solution is implemented in python, so make sure you have a working python environment on your local machine.
3. Open a command prompt, navigate to the project directory. Navigate to the /code/lib sub directory and install the following libraries: 
    1. ```bash
        pip install requests_aws4auth --target .
        ```

4. Create a S3 bucket for deployment (note: use the same region throughout the following steps, I have used us-east-1, you can replace it with the region of your choice. Refer to the [region table](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) for service availability.)
    1. ```bash
        aws s3 mb s3://avai_cf-2020-us-east-1 --region us-east-1
        ```

5. Navigate to the /code/source sub directory. Package the contents and prepare deployment package using the following command
    1. ```bash
        aws cloudformation package --template-file CF_Template.yaml --output-template-file CF_Template_output.yaml --s3-bucket avai_cf-2020-us-east-1 --region us-east-1
        ```
6. The SAM template will also create a lambda function which will poll the Veeva domain at regular intervals. Replace the placeholders in the below command with username, password and dbname, and deploy the package:
    1. ```bash 

        aws cloudformation deploy  --template-file CF_Template_output.yaml --capabilities CAPABILITY_IAM  --region us-east-1 --parameter-overrides VeevaDomainNameParameter=demodomainname VeevaDomainUserNameParameter=username VeevaDomainPasswordParameter=password --stack-name AVAI_demo
        ```
7. If you want to make changes to the Lambda functions, you can do so on your local machine and redeploy them using the steps 5 through 6 above. The package and deploy commands take care of zipping up the new Lambda files (along with the dependencies) and uploading them to AWS for execution.

## Further Reading:
1. Blogpost: [Analyze and tag assets stored in Veeva Vault using Amazon AI services](http://aws.amazon.com/)

## License

This library is licensed under the Apache 2.0 License. 
