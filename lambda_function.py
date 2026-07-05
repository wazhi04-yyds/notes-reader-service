import os  # 🆕 Imported to read environment targets
import json
import boto3
import pymysql
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret():
    """
    Retrieve database credentials. Supports environment variable overrides for CI/CD.
    """
    # 🆕 ENTERPRISE PATTERN: Fallback to hardcoded values if environment variables aren't set
    secret_name = os.environ.get("SECRET_NAME", "notes-app/database/credentials")
    region_name = os.environ.get("AWS_REGION", "eu-north-1")
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    
    try:
        logger.info("Retrieving secret from Secrets Manager...")
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        logger.info("Successfully retrieved secret from Secrets Manager")
    except ClientError as e:
        logger.error(f"Error retrieving secret: {e}")
        raise e
    
    return json.loads(get_secret_value_response['SecretString'])

def get_database_connection():
    """
    Create and return a database connection using configurations.
    """
    try:
        # 🆕 ENVIRONMENT CHECK: If we are running local CI/CD tests, skip AWS entirely
        if os.environ.get("EXECUTION_ENV") == "LOCAL_TEST":
            logger.info("CI/CD Mode: Mocking database connection string...")
            return pymysql.connect(
                host="127.0.0.1", # Points to your local Docker Compose MySQL
                user="test_user",
                password="test_password",
                database="notes_app_test",
                port=3306
            )

        # Standard AWS Cloud Execution Path
        secret = get_secret()
        logger.info(f"Connecting to database host: {secret['host']}")
        
        return pymysql.connect(
            host=secret['host'],
            user=secret['username'],
            password=secret['password'],
            database=secret.get('dbname', 'notes_app'),
            port=secret.get('port', 3306),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            ssl={'ssl_disabled': False},
            connect_timeout=10
        )
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise e
def get_notes_from_database(connection, search_term=None, limit=None, offset=None):
    """
    Retrieve notes from the database with optional filtering
    """
    try:
        with connection.cursor() as cursor:
            # Base SQL query
            sql = "SELECT * FROM note"
            params = []
            
            # Add search filter if provided
            if search_term:
                sql += " WHERE note_content LIKE %s"
                params.append(f"%{search_term}%")
                logger.info(f"Searching for notes containing: '{search_term}'")
            
            # Add ordering
            sql += " ORDER BY created_at DESC"
            
            # Add limit if provided
            if limit:
                sql += " LIMIT %s"
                params.append(limit)
                
            # Add offset if provided
            if offset:
                sql += " OFFSET %s"
                params.append(offset)
            
            logger.info(f"Executing SQL: {sql}")
            logger.info(f"With parameters: {params}")
            
            cursor.execute(sql, params)
            notes = cursor.fetchall()
            
            logger.info(f"Retrieved {len(notes)} notes from database")
            return notes
            
    except Exception as e:
        logger.error(f"Error retrieving notes: {e}")
        raise e

def lambda_handler(event, context):
    """
    Main Lambda handler function
    """
    logger.info(f"=== NOTES READER SERVICE STARTED ===")
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    connection = None
    
    try:
        # 🆕 EXTRACT QUERY PARAMETERS
        query_params = event.get('queryStringParameters') or {}
        search_term = query_params.get('search')
        limit = query_params.get('limit')
        offset = query_params.get('offset')
        
        # Convert string parameters to integers if provided
        if limit:
            limit = int(limit)
        if offset:
            offset = int(offset)
            
        logger.info(f"Query parameters - search: '{search_term}', limit: {limit}, offset: {offset}")
        
        # Get database connection
        connection = get_database_connection()
        
        # 🆕 GET NOTES WITH FILTERING
        notes = get_notes_from_database(
            connection, 
            search_term=search_term, 
            limit=limit, 
            offset=offset
        )
        
        # Return successful response
        response = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'data': notes,
                'count': len(notes),
                'search_term': search_term,
                'limit': limit,
                'offset': offset,
                'message': f'Successfully retrieved {len(notes)} notes'
            }, default=str)
        }
        
        logger.info(f"=== SUCCESS: Returning {len(notes)} notes ===")
        return response
        
    except Exception as e:
        logger.error(f"=== ERROR: {type(e).__name__}: {e} ===")
        
        # Return error response
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'message': 'Internal server error',
                'error': str(e),
                'error_type': type(e).__name__
            })
        }
    
    finally:
        # Close database connection
        if connection:
            try:
                connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

# 🆕 THIS ALLOWS "RUN PYTHON FILE IN TERMINAL" TO WORK
if __name__ == "__main__":
    import os
    print("=========================================")
    print(" Running Notes Reader Service Locally... ")
    print("=========================================")
    
    # Force the code to use local testing configurations
    os.environ["EXECUTION_ENV"] = "LOCAL_TEST"
    
    # Simulate a fake incoming AWS API Gateway event hitting your Lambda function
    mock_aws_event = {
        "queryStringParameters": {
            "search": "meeting",
            "limit": "5",
            "offset": "0"
        }
    }
    
    # Run the handler function and print the final API output response string
    final_response = lambda_handler(mock_aws_event, None)
    print("\n--- LAMBDA OUTPUT RESPONSE ---")
    print(json.dumps(final_response, indent=4))