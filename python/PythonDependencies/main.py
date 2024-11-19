"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

"""
main.py
~~~~~~~~~~~~~~~~~~~
This module:
    1. Creates the execution environment and specify 3rd-party Python dependencies
    2. Sets any special configuration for local mode (e.g. when running in the IDE)
    3. Retrieves the runtime configuration
    4. Defines and register a UDF that will validate your schema (using Glue Schema Registry validation)
    5. Creates a source table to generate data using DataGen connector
    6. Creates a view from a query that uses the UDF
    7. Creates a sink table to Kinesis Data Streams and inserts into the sink table from the view
"""

from pyflink.table import EnvironmentSettings, TableEnvironment, DataTypes
from pyflink.table.udf import udf
import os
import boto3
import json
from jsonschema import validate
import logging
import pyflink
import pathlib
from botocore.exceptions import ClientError

glue_client = boto3.client('glue')

def create_schema_if_not_exists(registry_name, schema_name, schema_definition):
    try:
        # try to read schema
        glue_client.get_schema(
            SchemaId={
                'RegistryName': registry_name,
                'SchemaName': schema_name
            }
        )
        print(f"Schema '{schema_name} ' already exists.")
    except glue_client.exceptions.EntityNotFoundException:
        

#
# glue_client = boto3.client('glue')
#
# def create_schema_if_not_exists(registry_name, schema_name, schema_definition):
#     try:
#         # Try to get the schema
#         glue_client.get_schema(
#             SchemaId={
#                 'RegistryName': registry_name,
#                 'SchemaName': schema_name,
#             }
#         )
#         print(f"Schema '{schema_name}' already exists.")
#     except glue_client.exceptions.EntityNotFoundException:
#         # If the schema doesn't exist, create it
#         try:
#             response = glue_client.create_schema(
#                 RegistryId={'RegistryName': registry_name},
#                 SchemaName=schema_name,
#                 DataFormat='JSON',
#                 Compatibility='BACKWARD',
#                 SchemaDefinition=json.dumps(schema_definition)
#             )
#             print(f"Schema '{schema_name}' created successfully.")
#             return response['SchemaVersionId']
#         except ClientError as e:
#             print(f"Error creating schema: {e}")
#             raise
#
# def get_schema_from_glue(registry_name, schema_name, schema_version='latest'):
#     try:
#         response = glue_client.get_schema_version(
#             SchemaId={
#                 'RegistryName': registry_name,
#                 'SchemaName': schema_name,
#             },
#             SchemaVersionNumber={'LatestVersion': True} if schema_version == 'latest' else {'VersionNumber': schema_version}
#         )
#         return json.loads(response['SchemaDefinition'])
#     except ClientError as e:
#         print(f"Error fetching schema: {e}")
#         raise
#
# # Define your schema
# schema_definition = {
#     "type": "object",
#     "properties": {
#         "seed_time": {
#             "type": "string",
#             "format": "date-time"
#         },
#         "a_number": {
#             "type": "integer",
#             "minimum": 0,
#             "maximum": 100
#         }
#     },
#     "required": ["seed_time", "a_number"]
# }
#
# # Create the schema if it doesn't exist
# registry_name = 'your_registry_name'
# schema_name = 'random_numbers'
# create_schema_if_not_exists(registry_name, schema_name, schema_definition)
#
# # Fetch the schema
# schema = get_schema_from_glue(registry_name, schema_name)
#
# def validate_schema(record_string):
#     try:
#         record = json.loads(record_string)
#         validate(instance=record, schema=schema)
#         return True
#     except Exception as e:
#         print(f"Validation error: {str(e)}")
#         return False

# You can then use this function in your Flink UDF

#################################################################################
# 1. Creates the execution environment and specify 3rd-party Python dependencies
#################################################################################

env_settings = EnvironmentSettings.in_streaming_mode()
table_env = TableEnvironment.create(env_settings)

# Point Flink runtime to the requirement.txt containing 3rd-party Python dependencies
# If required, Managed Service for Apache Flink will install these dependencies on the cluster.
python_source_dir = str(pathlib.Path(__file__).parent)
table_env.set_python_requirements(requirements_file_path="file:///" + python_source_dir + "/requirements.txt")

##############################################
# 2. Set special configuration for local mode
##############################################

# Location of the configuration file when running on Managed Flink.
# NOTE: this is not the file included in the project, but a file generated by Managed Flink, based on the
# application configuration.
APPLICATION_PROPERTIES_FILE_PATH = "/etc/flink/application_properties.json"

# Set the environment variable IS_LOCAL=true in your local development environment,
# or in the run profile of your IDE: the application relies on this variable to run in local mode (as a standalone
# Python application, as opposed to running in a Flink cluster).
# Differently from Java Flink, PyFlink cannot automatically detect when running in local mode
is_local = (
    True if os.environ.get("IS_LOCAL") else False
)

# This would be done once when the job starts
glue_client = boto3.client('glue')

def get_schema_from_glue():
    response = glue_client.get_table(
        DatabaseName='your_database_name',
        TableName='random_numbers'
    )
    columns = response['Table']['StorageDescriptor']['Columns']

    properties = {}
    for column in columns:
        if column['Name'] == 'seed_time':
            properties[column['Name']] = {
                "type": "string",
                "format": "date-time"
            }
        elif column['Name'] == 'a_number':
            properties[column['Name']] = {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
            }

    return {
        "type": "object",
        "properties": properties,
        "required": [col['Name'] for col in columns]
    }

# Fetch the schema once at the start of the job
schema = get_schema_from_glue()



if is_local:
    # Load the configuration from the json file included in the project
    APPLICATION_PROPERTIES_FILE_PATH = "application_properties.json"

    # Point to the fat-jar generated by Maven, containing all jar dependencies (e.g. connectors)
    CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
    table_env.get_config().get_configuration().set_string(
        "pipeline.jars",
        # For local development (only): use the fat-jar containing all dependencies, generated by `mvn package`
        "file:///" + CURRENT_DIR + "/target/pyflink-dependencies.jar",
    )

    # Show the PyFlink home directory and the directory where logs will be written, when running locally
    print("PyFlink home: " + os.path.dirname(os.path.abspath(pyflink.__file__)))
    print("Logging directory: " + os.path.dirname(os.path.abspath(pyflink.__file__)) + '/log')

# Utility method, extracting properties from the runtime configuration file
def get_application_properties():
    if os.path.isfile(APPLICATION_PROPERTIES_FILE_PATH):
        with open(APPLICATION_PROPERTIES_FILE_PATH, "r") as file:
            contents = file.read()
            properties = json.loads(contents)
            return properties
    else:
        print('A file at "{}" was not found'.format(APPLICATION_PROPERTIES_FILE_PATH))

# Utility method, extracting a property from a property group
def property_map(props, property_group_id):
    for prop in props:
        if prop["PropertyGroupId"] == property_group_id:
            return prop["PropertyMap"]


#####################################
# 3. Retrieve runtime configuration
#####################################

props = get_application_properties()

# Get name and region of the Kinesis stream from application configuration
output_stream_name = property_map(props, "OutputStream0")["stream.name"]
output_stream_region = property_map(props, "OutputStream0")["aws.region"]
logging.info(f"Output stream: {output_stream_name}, region: {output_stream_region}")

# Get Bedrock model_id and region from application configuration
model_id = property_map(props, "Bedrock")["model.id"]
model_region = property_map(props, "Bedrock")["aws.region"]
logging.info(f"Bedrock model: {model_id}, region: {model_region}")

###################################################################
# 4.  Defines and register a UDF that uses boto3 to invoke Bedrock
###################################################################


@udf(input_types=[DataTypes.INT()], result_type=DataTypes.STRING())
def ask_bedrock_for_fun_fact(a_number):
    import boto3
    import botocore

    client = boto3.client("bedrock-runtime", region_name=model_region)

    user_message = f"Give me a fun fact about the number '{a_number}'"
    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]

    try:
        # Send the message to the model, using a basic inference configuration.
        response = client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 512, "temperature": 0.5, "topP": 0.9},
        )

        # Extract and print the response text.
        response_text = response["output"]["message"]["content"][0]["text"]
        return response_text

    except (botocore.exceptions.ClientError, Exception) as e:
        error_reason = f"ERROR: Can't invoke {model_id}  Reason: {e}"
        return error_reason


# Register the UDF
table_env.create_temporary_system_function("ask_bedrock_for_fun_fact", ask_bedrock_for_fun_fact)



# Fetch the schema once at the start of the job
schema = get_schema_from_glue()

@udf(result_type=DataTypes.BOOLEAN())
def validate_schema(record_string):
    try:
        record = json.loads(record_string)
        validate(instance=record, schema=schema)
        return True
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return False

# Usage in Flink job
table_env.create_temporary_function("validate_schema", validate_schema)

def main():

    #################################################
    # 5. Define input table using datagen connector
    #################################################

    # In a real application, this table will probably be connected to a source stream, using for example the 'kinesis'
    # connector.

    table_env.execute_sql("""
                CREATE TABLE random_numbers (
                    seed_time TIMESTAMP(3),
                    a_number INT
                  )
                  WITH (
                    'connector' = 'datagen',
                    'rows-per-second' = '1',
                    'fields.a_number.min' = '0',
                    'fields.a_number.max' = '100'
                  )
        """)

    ###################################################
    # 6. Creates a view from a query that uses the UDF
    ###################################################

    table_env.execute_sql("""
            CREATE TEMPORARY VIEW fun_facts
            AS
            SELECT seed_time, a_number, validate_schema(CAST(ROW(seed_time, a_number) AS STRING)) AS is_valid
            FROM random_numbers
    """)

    #################################################
    # 7. Define sink table using kinesis connector
    #################################################

#     table_env.execute_sql(f"""
#             CREATE TABLE output (
#                 seed_time TIMESTAMP(3),
#                 a_number INT,
#                 fun_fact STRING
#               )
#               PARTITIONED BY (a_number)
#               WITH (
#                 'connector' = 'kinesis',
#                 'stream' = '{output_stream_name}',
#                 'aws.region' = '{output_stream_region}',
#                 'sink.partitioner-field-delimiter' = ';',
#                 'sink.batch.max-size' = '5',
#                 'format' = 'json',
#                 'json.timestamp-format.standard' = 'ISO-8601'
#               )
#         """)

    # For local development purposes, you might want to print the output to the console, instead of sending it to a
    # Kinesis Stream. To do that, you can replace the sink table using the 'kinesis' connector, above, with a sink table
    # using the 'print' connector. Comment the statement immediately above and uncomment the one immediately below.

    table_env.execute_sql("""
        CREATE TABLE output (
                seed_time TIMESTAMP(3),
                a_number INT,
                fun_fact STRING
              )
              WITH (
                'connector' = 'print'
              )
    """)


    # Executing an INSERT INTO statement will trigger the job
    table_result = table_env.execute_sql("""
            INSERT INTO output
            SELECT seed_time, a_number, fun_fact
                FROM fun_facts
    """)

    # When running locally, as a standalone Python application, you must instruct Python not to exit at the end of the
    # main() method, otherwise the job will stop immediately.
    # When running the job deployed in a Flink cluster or in Amazon Managed Service for Apache Flink, the main() method
    # must end once the flow has been defined and handed over to the Flink framework to run.
    if is_local:
        table_result.wait()


if __name__ == "__main__":
    main()
