# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import sys
import datetime
import pandas as pd
import numpy as np
from itertools import chain
import uuid
import boto3
import os
import logging
from data_fetch import execute_kubecost_allocation_api, execute_kubecost_assets_api
import data_clean

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

# List of columns you want to keep
desired_columns = [
    "start", "end", "minutes", "cpuCores", "cpuCoreRequestAverage",
    "cpuCoreUsageAverage", "cpuCoreHours", "cpuCost", "cpuCostAdjustment",
    "cpuEfficiency", "gpuCount", "gpuHours", "gpuCost", "gpuCostAdjustment",
    "networkTransferBytes", "networkReceiveBytes", "networkCost",
    "networkCrossZoneCost", "networkCrossRegionCost", "networkInternetCost",
    "networkCostAdjustment", "loadBalancerCost", "loadBalancerCostAdjustment",
    "pvBytes", "pvByteHours", "pvCost", "pvs", "pvCostAdjustment", "ramBytes",
    "ramByteRequestAverage", "ramByteUsageAverage", "ramByteHours", "ramCost",
    "ramCostAdjustment", "ramEfficiency", "externalCost", "sharedCost",
    "totalCost", "totalEfficiency", "properties.cluster",
    "properties.container", "properties.namespace",
    "instance_id", "properties.labels.emr_containers_amazonaws_com_component",
    "emr_eks_subscription_id", "properties.labels.spark_role",
    "spark_version", "capacity_type", "pod_name", "job_id", "vc_id"]


def main():

    #Define time interval
    start = datetime.datetime.now() - datetime.timedelta(hours=2)
    start = start.replace(microsecond=0, second=0, minute=0)
    end = datetime.datetime.now() - datetime.timedelta(hours=1)
    end = end.replace(microsecond=0, second=0, minute=0)

    # #get asset data, these are ec2 instances
    asset_data = execute_kubecost_assets_api(kube_cost_endpoint, start, end, logger=logger)
    
    if(asset_data is None):
        logger.info ("No asset and EMR on EKS data found existing")
        sys.exit()
    
    # #clean the data, get only columns needed and rename column for capacity type
    cleaned_asset_data = data_clean.clean_asset_data(asset_data)
    cleaned_asset_data = cleaned_asset_data.rename(columns={'properties.providerID': 'instance_id'})

    aggregate_api_method = "pod,label:emr-containers.amazonaws.com/job.id,label:emr-containers.amazonaws.com/virtual-cluster-id"
    aggregate_other_method = "pod,label:eks-subscription.amazonaws.com/emr.internal.id"
            
    #get allocation data, these are cost of emr on eks pods
    kubecost_allocation_data = execute_kubecost_allocation_api(kube_cost_endpoint, 
                                                               start,
                                                                end, 
                                                                "1h", aggregate_api_method, logger=logger)
    
    kubecost_allocation_data_operator = execute_kubecost_allocation_api(kube_cost_endpoint, 
                                                               start,
                                                                end, 
                                                                "1h", aggregate_other_method, logger=logger)
    
    if kubecost_allocation_data_operator is None and kubecost_allocation_data is None:
        sys.exit()

    cleaned_allocation_data = data_clean.clean_allocation_data(kubecost_allocation_data, logger=logger)

    cleaned_allocation_data_operator = data_clean.clean_allocation_data_operator(kubecost_allocation_data_operator, logger=logger)

    if kubecost_allocation_data_operator is None and cleaned_allocation_data_operator is None:
        logger.info('No EMR on EKS data found, exiting')
        sys.exit()

    cost_df = pd.DataFrame(columns=desired_columns)

    # #Join the two df on instance_id
    if (cleaned_allocation_data is not None):

        df_job_api_method = cleaned_allocation_data.join(cleaned_asset_data.set_index('instance_id'), on='instance_id', validate='m:1')     
        df_job_api_method['emr_eks_subscription_id'] = np.NaN
        cost_df = pd.concat([cost_df, df_job_api_method[desired_columns]], ignore_index=True)

    if (cleaned_allocation_data_operator is not None):

        df_job_other_methods = cleaned_allocation_data_operator.join(cleaned_asset_data.set_index('instance_id'), on='instance_id', validate='m:1')
        df_job_other_methods[['job_id', 'vc_id']] = np.NaN

        cost_df = pd.concat([cost_df, df_job_other_methods[desired_columns]], ignore_index=True)

    


    #generate filename
    file_name = uuid.uuid1()

    #write to local file
    cost_df.to_csv(f"{file_name}.csv", index=False)
    
    #upload to S3
    export_to_s3(file_name=f"{file_name}.csv")

if __name__ == "__main__":
    main()