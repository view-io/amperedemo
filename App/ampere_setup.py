#!/usr/bin/python3

import requests
import uuid
import logging
from urllib.parse import urlparse
import json
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
base_url = 'http://host.docker.internal:9000'
tenant_id = '00000000-0000-0000-0000-000000000000'
urls = [
    'http://localhost/docs/sales/',
    'http://localhost/docs/marketing/',
    'http://localhost/docs/engineering/',
    'http://localhost/docs/humanresources/',
    'http://localhost/docs/research/'
]

# API token
token = 'mXCNtMWDsW0/pr+IwRFUjZScG7NggOjghJ2ITFe4+I4Am424DVh6aG8wz/WcVibLMiXcBhpGVfubOyLN002FZqjGB67zVr201SV7x4FGKe0hzPisH9eDlHgjh3yU4pkBpy+ar5dUsSfkHqYl8tWXk9eyNR5typ4bhGpiMPle8e2jfapipQEiuKKT2n14/KtEqic3I4G+IXylnbGLEl7orKafaZ/aYJtoeoajce9cr2KQ5FjfX8Gi6JQR8j+oKyc9rqP3AqKz/290LbMT2joGKeSUaSyjbIoynlpnyioWwUM0SimYLVi8KQO0wGieIYg1M202Ye6xDneYFqpPUNn7+8pCE4Hwr/8PHOo6KnaERTTqxH6nB5Nw9S+gMVDKpoJUNpqLiQy+ZCekN/HYMCuHFCpQIV8U5jGXgJW5ufHyIql9j9Wwr3XXCA6rs4YPTpOz'


def make_api_call(endpoint, method, body):
    logger.info(f"Making {method} request to {base_url}{endpoint}")
    response = requests.request(
        method,
        f"{base_url}{endpoint}",
        json=body,
        headers={
            'Content-Type': 'application/json',
            'x-token': token
        }
    )
    response.raise_for_status()
    return response.json()['GUID']


def generate_uuid():
    return str(uuid.uuid4())


def create_vector_repo(name):
    vector_guid = generate_uuid()
    body = {
        "Name": f"{name}-knowledge-base",
        "TenantGUID": tenant_id,
        "RepositoryType": "Pgvector",
        "Model": "sentence-transformers/all-MiniLM-L6-v2",
        "Dimensionality": 384,
        "DatabaseHostname": "pgvector",
        "DatabaseName": "vectordb",
        "SchemaName": "public",
        "DatabaseTable": f"view-{vector_guid}",
        "DatabasePort": 5432,
        "DatabaseUser": "postgres",
        "DatabasePassword": "password"
    }
    guid = make_api_call(f"/Config/v1.0/tenants/{tenant_id}/vectorrepositories", 'PUT', body)
    return guid, vector_guid


def create_metadata_rule(name):
    endpoint = f"/Config/v1.0/tenants/{tenant_id}/metadatarules"
    url = f"{base_url}{endpoint}"

    body = {
        "Name": f"{name}-metadata-rule",
        "BucketGUID": "00000000-0000-0000-0000-000000000000",
        "ContentType": "*",
        "MaxContentLength": 134217728,
        "ProcessingEndpoint": f"http://nginx-processor:8000/v1.0/tenants/{tenant_id}/processing",
        "ProcessingAccessKey": "default",
        "CleanupEndpoint": f"http://nginx-processor:8000/v1.0/tenants/{tenant_id}/processing/cleanup",
        "CleanupAccessKey": "default",
        "MinChunkContentLength": 2,
        "MaxChunkContentLength": 2048,
        "MaxTokensPerChunk": 256,
        "ShiftSize": 1920,
        "ImageTextExtraction": True,
        "TopTerms": 25,
        "CaseInsensitive": True,
        "IncludeFlattened": True,
        "DataCatalogEndpoint": "http://nginx-lexi:8000/",
        "DataCatalogAccessKey": "default",
        "DataCatalogType": "Lexi",
        "DataCatalogCollection": tenant_id,
        "GraphRepositoryGUID": tenant_id
    }

    headers = {
        'Content-Type': 'application/json',
        'x-token': token
    }

    # Debug logging
    logger.info(f"Making API call to create metadata rule:")
    logger.info(f"URL: {url}")
    logger.info(f"Method: PUT")
    logger.info(f"Headers: {json.dumps(headers, indent=2)}")
    logger.info(f"Payload: {json.dumps(body, indent=2)}")

    try:
        response = requests.put(url, json=body, headers=headers)

        # Debug logging for response
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {json.dumps(dict(response.headers), indent=2)}")
        logger.info(f"Response content: {response.text}")

        response.raise_for_status()
        return response.json()['GUID']
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating metadata rule: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response content: {e.response.text}")
        exit()


def create_embedding_rule(name, vector_repo_guid):
    body = {
        "TenantGUID": tenant_id,
        "BucketGUID": "00000000-0000-0000-0000-000000000000",
        "Name": f"{name}-embeddings-rule",
        "ContentType": "*",
        "GraphRepositoryGUID": tenant_id,
        "VectorRepositoryGUID": vector_repo_guid,
        "ProcessingEndpoint": f"http://nginx-processor:8000/v1.0/tenants/{tenant_id}/processing",
        "ProcessingAccessKey": "default",
        "EmbeddingsServerUrl": "http://nginx-embeddings:8000/",
        "EmbeddingsServerApiKey": "default",
        "EmbeddingsGenerator": "LCProxy",
        "EmbeddingsGeneratorUrl": "http://nginx-lcproxy:8000/",
        "EmbeddingsGeneratorApiKey": "",
        "BatchSize": 512,
        "MaxGeneratorTasks": 32,
        "MaxRetries": 3,
        "MaxFailures": 3,
        "VectorStoreUrl": "http://nginx-vector:8000/",
        "VectorStoreAccessKey": "default",
        "MaxContentLength": 16777216
    }
    return make_api_call(f"/Config/v1.0/tenants/{tenant_id}/embeddingsrules", 'PUT', body)


def create_repository(name, url):
    api_hostname = urlparse(base_url).hostname
    updated_url = urlparse(url)._replace(netloc=api_hostname).geturl()
    body = {
        "Name": name,
        "WebAuthentication": "None",
        "WebUsername": "",
        "WebPassword": "",
        "WebApiKeyHeader": "",
        "WebApiKey": "",
        "WebBearerToken": "",
        "WebUserAgent": "view",
        "WebStartUrl": updated_url,
        "WebFollowLinks": True,
        "WebFollowRedirects": True,
        "WebIncludeSitemap": True,
        "WebRestrictToChildUrls": True,
        "WebRestrictToSameDomain": True,
        "WebMaxDepth": 3,
        "WebMaxParallelTasks": 2,
        "WebCrawlDelayMs": 12,
        "RepositoryType": "Web",
        "TenantGUID": tenant_id,
        "OwnerGUID": tenant_id
    }
    return make_api_call(f"/Crawler/v1.0/tenants/{tenant_id}/datarepositories", 'PUT', body)


def create_crawl_plan(name, metadata_rule_guid, embedding_rule_guid, repository_guid):
    body = {
        "Name": name,
        "CrawlFilterGUID": tenant_id,
        "CrawlScheduleGUID": tenant_id,
        "MetadataRuleGUID": metadata_rule_guid,
        "EmbeddingsRuleGUID": embedding_rule_guid,
        "ProcessAdditions": True,
        "ProcessDeletions": True,
        "ProcessUpdates": True,
        "DataRepositoryGUID": repository_guid,
        "TenantGUID": tenant_id,
        "EnumerationDirectory": "./enumerations/",
        "EnumerationsToRetain": 16,
        "MaxDrainTasks": 4
    }
    return make_api_call(f"/Crawler/v1.0/tenants/{tenant_id}/crawlplans", 'PUT', body)


def create_assistant_config(name, vector_guid):
    body = {
        "Name": name,
        "SystemPrompt": "You are an AI assistant augmented with a retrieval system. Carefully analyze the provided pieces of context and the user query at the end. \n\nRely primarily on the provided context for your response. If the context is not enough for you to answer the question, please politely explain that you do not have enough relevant information to answer. \n\nDo not try to make up an answer. Do not attempt to answer using general knowledge.",
        "EmbeddingModel": "sentence-transformers/all-MiniLM-L6-v2",
        "MaxResults": 15,
        "VectorDatabaseName": "vectordb",
        "VectorDatabaseTable": f"view-{vector_guid}",
        "VectorDatabaseHostname": "pgvector",
        "VectorDatabasePort": 5432,
        "VectorDatabaseUser": "postgres",
        "VectorDatabasePassword": "password",
        "GenerationProvider": "ollama",
        "GenerationModel": "qwen2.5:0.5b",
        "GenerationApiKey": "",
        "Temperature": 0.1,
        "TopP": 0.95,
        "MaxTokens": 501,
        "OllamaHostname": f"ollama-{name}",
        "OllamaPort": 11434,
        "UseCitations": False,
        "ContextSort": False,
        "SortBySimilarity": True,
        "ContextScope": 0,
        "Rerank": False,
        "RerankModel": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "RerankTopK": 3,
        "RerankLevel": "Chunk",
        "ChatOnly": False
    }
    return make_api_call(f"/Assistant/v1.0/tenants/{tenant_id}/assistant/configs", 'POST', body)


def setup():
    logger.info("Starting setup...")
    results = {}

    for url in urls:
        url_parts = url.split('/')
        name = url_parts[-2] or 'default'
        logger.info(f"Processing {url}")

        try:
            url_result = {}

            # Create Vector Repo
            vector_repo_guid, vector_guid = create_vector_repo(name)
            logger.info(f"Vector Repo GUID: {vector_repo_guid}")
            url_result['vector_repo_guid'] = vector_repo_guid
            url_result['vector_guid'] = vector_guid

            # Create Metadata Rule with enhanced debugging
            metadata_rule_guid = create_metadata_rule(name)
            logger.info(f"Metadata Rule GUID: {metadata_rule_guid}")
            url_result['metadata_rule_guid'] = metadata_rule_guid

            # Create Embedding Rule
            embedding_rule_guid = create_embedding_rule(name, vector_repo_guid)
            logger.info(f"Embedding Rule GUID: {embedding_rule_guid}")
            url_result['embedding_rule_guid'] = embedding_rule_guid

            # Create Repository
            repository_guid = create_repository(name, url)
            logger.info(f"Repository GUID: {repository_guid}")
            url_result['repository_guid'] = repository_guid

            # Create Crawl Plan
            crawl_plan_guid = create_crawl_plan(name, metadata_rule_guid, embedding_rule_guid, repository_guid)
            logger.info(f"Crawl Plan GUID: {crawl_plan_guid}")
            url_result['crawl_plan_guid'] = crawl_plan_guid

            # Create Assistant Config
            assistant_config_guid = create_assistant_config(name, vector_guid)
            logger.info(f"Assistant Config GUID: {assistant_config_guid}")
            url_result['assistant_config_guid'] = assistant_config_guid

            logger.info(f"Completed processing for {url}")
            results[url] = url_result

        except Exception as error:
            logger.error(f"Error processing {url}: {error}")
            results[url] = {'error': str(error)}

    logger.info("Setup completed.")

    # Save results to shared/config.json
    config_dir = 'shared'
    config_file = os.path.join(config_dir, 'config.json')

    # Ensure the directory exists
    os.makedirs(config_dir, exist_ok=True)

    try:
        with open(config_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {config_file}")
    except Exception as e:
        logger.error(f"Error saving results to {config_file}: {str(e)}")

    return results


if __name__ == "__main__":
    setup_results = setup()
    print("Setup Results:", setup_results)
