# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import sys
import requests
import datetime
import pandas as pd
from itertools import chain
import uuid
import boto3
import os
import logging

s3_bucket_name = os.environ["S3_BUCKET_NAME"]
s3_prefix = os.environ["S3_PREFIX"]
kube_cost_endpoint = os.environ["KUBECOST_API_ENDPOINT"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

logger.info(s3_bucket_name)
logger.info(s3_prefix)
logger.info(kube_cost_endpoint)

def export_to_s3(file_name):
    """Uploads the Kubecost extracted data to an S3 bucket.

    :param file_name: the file used to upload the CSV file
    :return:
    """

    #Initialize the s3 client, SDK will use IRSA credentials by default
    s3 = boto3.client('s3')

    logger.info("upload to s3")

    s3.upload_file(file_name, s3_bucket_name, f"{s3_prefix}/{file_name}")

def execute_kubecost_allocation_api(kubecost_api_endpoint, start, end, granularity):

    """Executes Kubecost Allocation API on a a 1h window, example 08:00 to 09:00

    :param kubecost_api_endpoint: the Kubecost API endpoint, in format of "http://<service>.<namespace>:<port>"
    :param start: the start time for calculating Kubecost Allocation API window
    :param end: the end time for calculating Kubecost Allocation API window
    :param granularity: the user input time granularity, to use for calculating the step (daily or hourly)
    :return: the Kubecost Allocation API query "data" list
    """

    window = f'{start.strftime("%Y-%m-%dT%H:%M:%SZ")},{end.strftime("%Y-%m-%dT%H:%M:%SZ")}'

    logger.info(window)

    #The aggregate is used to query Kubecost only on EMR on EKS related data
    #It uses labels that are for Virtual Cluster Id and Job Id
    aggregate = "pod,label:emr-containers.amazonaws.com/job.id,label:emr-containers.amazonaws.com/virtual-cluster-id"

    step = granularity

    accumulate=False

    #Query Kubecost API
    try:       
        params = {"window": window, "aggregate": aggregate, "accumulate": accumulate, "step": step}

        r = requests.get(f"{kubecost_api_endpoint}/model/allocation", params=params, timeout=30)

        if not list(filter(None, r.json()["data"])):
            logger.info("No data found")
            sys.exit()

        return r.json()["data"]
    
    except requests.exceptions.ConnectionError as error:
        logger.error(f"Error connecting to Kubecost Allocation API: {error}")
        sys.exit(1)

def clean_allocation_data(kubecost_allocation_data):

    #List all the keys from the data object return by kubecost
    #Keys contain a pair defined by job_id and virtual_cluster_id
    list_keys = list(set(chain.from_iterable(sub.keys() for sub in kubecost_allocation_data)))

    list_keys = [item for item in list_keys if '__unallocated__' not in item and '__idle__' not in item]

    #convert dict to panda dataframe
    if list_keys:
        df = pd.DataFrame.from_records(kubecost_allocation_data)
    else:
        logger.info('No EMR on EKS data found, exiting')
        sys.exit()

    logger.info(f'List of job/vc tuple {list_keys}')

    #Transforming columns in the dataframe to new list of df 
    all_dfs = [df[key] for key in list_keys]

    #Transforming list to rows in a single df
    df = pd.concat(all_dfs)

    #Flatten the json
    df = pd.json_normalize(df)
    
    df[['pod_name', 'job_id', 'vc_id']] = df['name'].str.split('/', expand=True)

    df = df.rename(columns={'properties.providerID': 'instance_id'})

    df = df.drop(columns=['name'])

    return df

def execute_kubecost_assets_api(kubecost_api_endpoint, start, end):
    """Executes Kubecost Assets API on a a 1h window, example 08:00 to 09:00

    :param kubecost_api_endpoint: the Kubecost API endpoint, in format of "http://<service>.<namespace>:<port>"
    :param start: the start time for calculating Kubecost Allocation API window
    :param end: the end time for calculating Kubecost Allocation API window
    :return: the Kubecost Allocation API query "data" list
    """

    accumulate=False

    # Calculate window
    window = f'{start.strftime("%Y-%m-%dT%H:%M:%SZ")},{end.strftime("%Y-%m-%dT%H:%M:%SZ")}'

    # Executing Kubecost Allocation API call (On-demand query)
    logger.info(f"Querying Kubecost Assets API for data between {start} and {end}")
    params = {"window": window, "accumulate": accumulate, "filterCategories": "Compute", "filterTypes": "Node"}
    
    try:
        r = requests.get(f"{kubecost_api_endpoint}/model/assets", params=params, timeout=120)

        if not list(filter(None, r.json()["data"])):
                logger.info("No data found")
                sys.exit()

        return r.json()["data"]
    
    except requests.exceptions.ConnectionError as error:
        logger.error(f"Error connecting to Kubecost Allocation API: {error}")
        sys.exit(1)

    

def clean_asset_data (asset_data):

    #List all the keys from the data object return by kubecost
    list_keys = list(set(chain.from_iterable(sub.keys() for sub in asset_data)))

    #load dict into df
    df = pd.DataFrame.from_records(asset_data)

    #Transforming columns in the dataframe to new list of dfs
    all_dfs = [df[key] for key in list_keys]

    #Transforming list to rows in a single df
    df = pd.concat(all_dfs)

    #Flatten the json
    df = pd.json_normalize(df)
    
    df_columns_list = df.columns.values.tolist()
    
    #get the instances created by managed nodegroup
    #We need to do this because of different label created by karpenter
    #we also need to make sure the CA label for capacity type exist
    df_mng = pd.DataFrame()

    cluster_autoscaler_label = 'labels.label_eks_amazonaws_com_capacityType'

    if cluster_autoscaler_label in df_columns_list:
        df_mng = df.dropna(subset=[cluster_autoscaler_label])
        df_mng = df_mng.rename(columns={cluster_autoscaler_label: 'capacity_type'})
    
    df_karpenter = pd.DataFrame()

    karpenter_label = 'labels.label_karpenter_sh_capacity_type'

    #get the instances created by karpenter
    #we also need to make sure the karpenter label for capacity type exist
    if karpenter_label in df_columns_list:
        df_karpenter = df.dropna(subset=[karpenter_label])
        df_karpenter = df_karpenter.rename(columns={karpenter_label: 'capacity_type'})

    #check if there is data in dfs and
    # concatenate all the dfs into a single one

    if df_karpenter.empty and df_mng.empty:
        sys.exit()
    elif df_karpenter.empty:
        df = df_mng
    elif df_mng.empty:
        df = df_karpenter
    else:
        df = pd.concat([df_karpenter, df_mng])

    #select only two columns that are of interest
    df = df[['properties.providerID','capacity_type']]

    #unify how spot and on-demand are written, this is due to differences
    #between karpenter and managed nodegroup
    df['capacity_type'] = df['capacity_type'].str.lower()
    df['capacity_type'] = df["capacity_type"].str.replace('-', '_')

    return df



def main():

    #Define time interval
    start = datetime.datetime.now() - datetime.timedelta(hours=1)
    start = start.replace(microsecond=0, second=0, minute=0)
    end = datetime.datetime.now() - datetime.timedelta(hours=0)
    end = end.replace(microsecond=0, second=0, minute=0)

    # #get asset data, these are ec2 instances
    asset_data = execute_kubecost_assets_api(kube_cost_endpoint, start, end)
    
    # #clean the data, get only columns needed and rename column for capacity type
    cleaned_asset_data = clean_asset_data(asset_data)
    cleaned_asset_data = cleaned_asset_data.rename(columns={'properties.providerID': 'instance_id'})

    #get allocation data, these are cost of emr on eks pods
    kubecost_allocation_data = execute_kubecost_allocation_api(kube_cost_endpoint, 
                                                               start,
                                                                end, 
                                                                "1h")

    #clean the data and get only columns needed
    cleaned_allocation_data = clean_allocation_data(kubecost_allocation_data)
    cleaned_allocation_data = cleaned_allocation_data.rename(columns={'properties.providerID': 'instance_id'})
    
    # #Join the two df on instance_id
    df = cleaned_allocation_data.join(cleaned_asset_data.set_index('instance_id'), on='instance_id', validate='m:1')

    #generate filename
    file_name = uuid.uuid1()

    #write to local file
    df.to_csv(f"{file_name}.csv", index=False)
    
    #upload to S3
    export_to_s3(file_name=f"{file_name}.csv")

if __name__ == "__main__":
    main()