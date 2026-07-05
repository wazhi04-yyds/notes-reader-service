FROM public.ecr.aws/lambda/python:3.11

# Copy the application script into the AWS Lambda task environment root
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Install dependencies directly inside the container environment
COPY requirements.txt .
RUN pip install -r requirements.txt

# Set the operational entry point to your specific handler function
CMD [ "lambda_function.lambda_handler" ]