from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import os
import pyodbc  # For SQL Server database connectivity

# Set your Azure Blob Storage connection string and container name
connection_string = "DefaultEndpointsProtocol=https;AccountName=eucondms;AccountKey=--Key1-or-Key2--;BlobEndpoint=https://eucondms.blob.core.windows.net/;QueueEndpoint=https://eucondms.queue.core.windows.net/;TableEndpoint=https://eucondms.table.core.windows.net/;FileEndpoint=https://eucondms.file.core.windows.net/;"
container_name = "dms"

# Specify the local directory where you want to save the files
local_directory = "/mnt/c/Users/PrV/Downloads/Inputmanagement-Sample"

# Create a BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

# Get a ContainerClient
container_client = blob_service_client.get_container_client(container_name)

# Function to download files from specific folders
def download_files_from_folders_with_ids(source_container_client, local_directory, folder_ids):
    for folder_id in folder_ids:
        # Define the folder prefix based on your folder naming convention
        folder_prefix = f"{folder_id}/"
        
        # List blobs with the specified prefix (folder)
        blob_list = list(source_container_client.list_blobs(name_starts_with=folder_prefix))
        
        for blob in blob_list:
            # Get the source blob properties
            source_blob_client = source_container_client.get_blob_client(blob.name)
            
            # Define the local file path to save the file
            local_file_path = os.path.join(local_directory, blob.name)
            
            # Ensure the directory structure exists before saving the file
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            # Download the blob to the local file
            with open(local_file_path, "wb") as local_file:
                download_stream = source_blob_client.download_blob()
                local_file.write(download_stream.readall())

# Function to extract folder IDs from SQL Server
def extract_folder_ids_from_sql_server():
    # Set up your SQL Server database connection
    server = 'dbs-claimsdb-replica.ms.eucon.local'
    database = 'db-claimsdb-replica'
    username = '--Username--'
    password = '--Password--'

    # Create a connection to the SQL Server database
    conn = pyodbc.connect(f'DRIVER=ODBC Driver 18 for SQL Server;SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes')
    
    # Create a cursor object
    cursor = conn.cursor()

    # Execute your SQL query to extract folder IDs
    query = "select top 1000 message_id, product_line from claim where product_line = 'SMART_INBOX' and create_date > convert(datetime, '2023-01-01', 121) order by NEWID()"
    cursor.execute(query)

    # Fetch the folder IDs into a list
    folder_ids = [row[0] for row in cursor.fetchall()]

    # Close the database connection
    conn.close()

    return folder_ids

# Extract folder IDs from SQL Server
folder_ids = extract_folder_ids_from_sql_server()

# Download files from folders with specific IDs to the local directory
download_files_from_folders_with_ids(container_client, local_directory, folder_ids)

print("Files from specific folders copied successfully!")
