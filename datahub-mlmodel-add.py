# Accessed apache datahub version: 0.11.0
import logging
import datahub.emitter.mce_builder as builder
import datahub.metadata.schema_classes as models
import config;
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
# Imports for metadata model classes

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# gms_endpoint = "http://10.10.0.8:8080" # DEV - im VPN
# gms_endpoint = "http://10.12.0.8:8080" # PROD - im VPN
gms_endpoint = "http://localhost:8080" # via Port-Forwarding

# BearerToken = config.datahub_BearerToken_dev
BearerToken = config.datahub_BearerToken_prod
headers = { "Authorization": "Bearer " + BearerToken, 'Content-Type': 'application/json'}
# Initialize the DataHubGraph client
datahub_graph = DataHubGraph(DatahubClientConfig(server=gms_endpoint, extra_headers=headers))
# Create an emitter to DataHub over REST
emitter = DatahubRestEmitter(gms_server=gms_endpoint, extra_headers=headers)
emitter.test_connection()


###### Create ML-Example

# main dataset for the demo
claim_dataset_urn = builder.make_dataset_urn(
    name="db-claimsdb-replica.dbo.claim", platform="mssql", env="PROD"
)

#### create feature directly connected with dataset

feature_urn = builder.make_ml_feature_urn(
    feature_table_name="placeholder_ml_feature_table", # not used
    feature_name="example_ml_feature",
)

#  Create feature
event: MetadataChangeProposalWrapper = MetadataChangeProposalWrapper(
    entityType="mlFeature",
    changeType=models.ChangeTypeClass.UPSERT,
    entityUrn=feature_urn,
    aspectName="mlFeatureProperties",
    aspect=models.MLFeaturePropertiesClass(
        description="Represents the examplary ml feature which is directly connected to a dataset.",
        # attaching a source to a feature creates lineage between the feature
        # and the upstream dataset. This is how lineage between your data warehouse
        # and machine learning ecosystem is established.
        sources=[claim_dataset_urn],
        dataType="TIME",
    ),
)
emitter.emit(event)
log.info(f"Created feature {feature_urn}")


#### create feature table

myFeatureTableName = "claims_feature_table"
feature_table_urn = builder.make_ml_feature_table_urn(
    feature_table_name=myFeatureTableName, platform="Python"
)
existing_feature_table = datahub_graph.get_aspect(entity_urn=feature_table_urn, aspect_type=models.MLModelPropertiesClass)

# Create Feature table only if it does not exists (otherwise it will be overwritten)
if existing_feature_table is None:
    primary_key_urns = [
        builder.make_ml_primary_key_urn(
            feature_table_name=myFeatureTableName,
            primary_key_name="id",
        )]
    feature_urns = [
        builder.make_ml_feature_urn(
            feature_name="id", feature_table_name=myFeatureTableName
        ),
        builder.make_ml_feature_urn(
            feature_name="create_date", feature_table_name=myFeatureTableName
        ),
    ]
    
    feature_table_properties = models.MLFeatureTablePropertiesClass(
            description="Feature Table based on the claim table of claimsDB",
            # link your features to a feature table
            mlFeatures=feature_urns,
            # link your primary keys to the feature table
            mlPrimaryKeys=primary_key_urns,
        )
    
    # MCP creation
    event: MetadataChangeProposalWrapper = MetadataChangeProposalWrapper(
        entityType="mlFeatureTable",
        changeType=models.ChangeTypeClass.UPSERT,
        entityUrn=feature_table_urn,
        aspect=feature_table_properties
    )
    
    emitter.emit(event)
    log.info(f"Created term {feature_table_urn}")

else:
    log.info(f"Feature table {feature_table_urn} already exists, not overwriting it.")


#### add features to existing table

feature_urns = [
    builder.make_ml_feature_urn(
        feature_name="user_signup_date", feature_table_name=myFeatureTableName
    ),
    builder.make_ml_feature_urn(
        feature_name="user_last_active_date", feature_table_name=myFeatureTableName
    ),
]


# This code concatenates the new features with the existing features in the feature table.
# If you want to replace all existing features with only the new ones, you can comment out this line.
graph = DataHubGraph(DatahubClientConfig(server=gms_endpoint))
feature_table_properties = graph.get_aspect(
    entity_urn=feature_table_urn, aspect_type=MLFeatureTablePropertiesClass
)
if feature_table_properties:
    current_features = feature_table_properties.mlFeatures
    print("current_features:", current_features)
    if current_features:
        feature_urns += current_features

#### Create Dataset (SQL Server) ####
# myUrn = make_dataset_urn(platform="SQL Server", name="test_schema.sales", env="PROD")
# event: MetadataChangeProposalWrapper = MetadataChangeProposalWrapper(
#     entityUrn=myUrn,
#     aspect=SchemaMetadataClass(
#         schemaName="customer",  # not used
#         platform=make_data_platform_urn("mssql"),  # important <- platform must be an urn
#         version=0,  # when the source system has a notion of versioning of schemas, insert this in, otherwise leave as 0
#         hash="",  # when the source system has a notion of unique schemas identified via hash, include a hash, else leave it as empty string
#         platformSchema=OtherSchemaClass(rawSchema="test_schema"),
#         # lastModified=AuditStampClass(
#         #     time=1640692800000, actor="urn:li:corpuser:ingestion"
#         # ),
#         fields=[
#             SchemaFieldClass(
#                 fieldPath="address.zipcode",
#                 type=SchemaFieldDataTypeClass(type=StringTypeClass()),
#                 nativeDataType="VARCHAR(50)",  # use this to provide the type of the field in the source system's vernacular
#                 description="This is the zipcode of the address. Specified using extended form and limited to addresses in the United States",
#                 lastModified=AuditStampClass(
#                     time=1640692800000, actor="urn:li:corpuser:ingestion"
#                 ),
#             ),
#             SchemaFieldClass(
#                 fieldPath="address.street",
#                 type=SchemaFieldDataTypeClass(type=StringTypeClass()),
#                 nativeDataType="VARCHAR(100)",
#                 description="Street corresponding to the address",
#                 lastModified=AuditStampClass(
#                     time=1640692800000, actor="urn:li:corpuser:ingestion"
#                 ),
#             ),
#             SchemaFieldClass(
#                 fieldPath="last_sold_date",
#                 type=SchemaFieldDataTypeClass(type=DateTypeClass()),
#                 nativeDataType="Date",
#                 description="Date of the last sale date for this property",
#                 created=AuditStampClass(
#                     time=1640692800000, actor="urn:li:corpuser:ingestion"
#                 ),
#                 lastModified=AuditStampClass(
#                     time=1640692800000, actor="urn:li:corpuser:ingestion"
#                 ),
#             ),
#         ],
#     ),
# )