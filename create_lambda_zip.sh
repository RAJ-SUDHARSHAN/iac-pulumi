#!/bin/bash

# Define the name of the virtual environment and the lambda function directory
VENV="venv_lambda"
LAMBDA_DIR="/Users/rajsudharshan/studies/PG/Universities/Northeastern_University/Courses_and_Assignments/CSYE6225-Network_Strct_Cloud_computing/Raj-Sudharshan_Vidyalatha-Natarajan_002100399_09/serverless"
ZIP_PATH="$(pwd)"

# Navigate to the lambda function directory
cd $LAMBDA_DIR

# Zip the dependencies from the virtual environment
cd $VENV/lib/python3.11/site-packages/
zip -r $ZIP_PATH/lambda_function .

# Add the lambda function code to the zip
cd $LAMBDA_DIR
zip $ZIP_PATH/lambda_function.zip app.py

# Remove the virtual environment
cd $ZIP_PATH
rm -rf $VENV