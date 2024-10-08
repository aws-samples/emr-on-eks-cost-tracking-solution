import pandas as pd
import numpy as np
from itertools import chain
import sys
import json
import os

required_columns = ['properties.container', 'properties.labels.emr_containers_amazonaws_com_component',
                    'properties.labels.spark_role','spark_version']


def clean_allocation_data(kubecost_allocation_data, logger):

    #List all the keys from the data object return by kubecost
    #Keys contain a pair defined by job_id and virtual_cluster_id
    list_keys = list(set(chain.from_iterable(sub.keys() for sub in kubecost_allocation_data)))

    list_keys = [item for item in list_keys if '__unallocated__' not in item and '__idle__' not in item]

    #convert dict to panda dataframe
    if list_keys:
        df = pd.DataFrame.from_records(kubecost_allocation_data)
    else:
        return None

    logger.info(f'List of job/vc tuple {list_keys}')

    #Transforming columns in the dataframe to new list of df 
    all_dfs = [df[key] for key in list_keys]

    #Transforming list to rows in a single df
    df = pd.concat(all_dfs)

    #Flatten the json
    df = pd.json_normalize(df)
    
    df[['pod_name', 'job_id', 'vc_id']] = df['name'].str.split('/', expand=True)

    df = df.rename(columns={'properties.providerID': 'instance_id'})

    df = df.rename(columns={'properties.labels.eks_subscription_amazonaws_com_emr_internal_id': 'emr_eks_subscription_id'})
    
    df = df.drop(columns=['name'])

    missing_columns = [col for col in required_columns if col not in df.columns]
  
    if missing_columns:
        for col in missing_columns:
            df[col] = None

    return df

def clean_allocation_data_operator(kubecost_allocation_data, logger):

    #List all the keys from the data object return by kubecost
    #Keys contain a pair defined by job_id and virtual_cluster_id
    list_keys = list(set(chain.from_iterable(sub.keys() for sub in kubecost_allocation_data)))

    list_keys = [item for item in list_keys if '__unallocated__' not in item and '__idle__' not in item]

    #convert dict to panda dataframe
    if list_keys:
        df = pd.DataFrame.from_records(kubecost_allocation_data)
    else:
        return None

    #Transforming columns in the dataframe to new list of df 
    all_dfs = [df[key] for key in list_keys]

    #Transforming list to rows in a single df
    df = pd.concat(all_dfs)

    #Flatten the json
    df = pd.json_normalize(df)
    operator_missing_columns = [col for col in required_columns if col not in df.columns]
    if operator_missing_columns:
        for col in operator_missing_columns:
            df[col] = None

    # if ('properties.labels.node_kubernetes_io_instance_type' in df.columns):
    #     df = df.drop(columns=['properties.labels.node_kubernetes_io_instance_type'])
    # else:
    #     logger.info('node_kubernetes_io_instance_type column dose not exist')
    # if 'properties.labels.emr_containers_amazonaws_com_component' not in df.columns:
    #    df['properties.labels.emr_containers_amazonaws_com_component'] = np.nan
    #    df['properties.labels.spark_role'] = np.nan

    if ('properties.labels.eks_subscription_amazonaws_com_emr_internal_id' in df.columns and 'properties.labels.emr_containers_amazonaws_com_resource_type' not in df.columns):
        logger.info('Dropping jobs with spark-submit or start job run, emr_internal_id not supported for these modes by the solution')
        df.dropna(inplace=True)
        return None
    elif ('properties.labels.eks_subscription_amazonaws_com_emr_internal_id' in df.columns and 'properties.labels.emr_containers_amazonaws_com_resource_type' in df.columns):
        logger.info('Dropping jobs with spark-submit or start job run, emr_internal_id not supported for these modes by the solution')
        df.dropna(subset=['properties.labels.emr_containers_amazonaws_com_resource_type'], inplace=True)
    else:
        logger.info('Found spark operator submitted jobs only')

    df[['pod_name', 'emr_eks_subscription_id']] = df['name'].str.split('/', expand=True)

    #if the operator is running without any job, 
    # we want to make sure to create the spark version column
    # as it is not present in the operator as a label
    if 'properties.labels.spark_version' not in df.columns:
        df['spark_version'] = np.nan
    else:
        df['spark_version'] = df['properties.labels.spark_version']

    df = df.rename(columns={'properties.providerID': 'instance_id'})
    df = df.drop(columns=['name'])

    return df
    

def clean_asset_data (asset_data, logger):

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

    cluster_autoscaler_label = 'labels.eks_amazonaws_com_capacityType'

    if cluster_autoscaler_label in df_columns_list:
        df_mng = df.dropna(subset=[cluster_autoscaler_label])
        df_mng = df_mng.rename(columns={cluster_autoscaler_label: 'capacity_type'})
    
    df_karpenter = pd.DataFrame()

    karpenter_label = 'labels.karpenter_sh_capacity_type'

    #get the instances created by karpenter
    #we also need to make sure the karpenter label for capacity type exist
    if karpenter_label in df_columns_list:
        df_karpenter = df.dropna(subset=[karpenter_label])
        df_karpenter = df_karpenter.rename(columns={karpenter_label: 'capacity_type'})

    #check if there is data in dfs and
    # concatenate all the dfs into a single one
    if df_karpenter.empty and df_mng.empty:
        logger.info(f'karpenter and managed node groups are both empty')
        sys.exit()
    elif df_karpenter.empty:
        df = df_mng
    elif df_mng.empty:
        df = df_karpenter
    else:
        df = pd.concat([df_karpenter, df_mng])

    #select only two columns that are of interest
    df = df[['properties.providerID','capacity_type']]

    # df = df.rename(columns={'properties.labels.node_kubernetes_io_instance_type': 'instace_type'})

    #unify how spot and on-demand are written, this is due to differences
    #between karpenter and managed nodegroup
    df['capacity_type'] = df['capacity_type'].str.lower()
    df['capacity_type'] = df["capacity_type"].str.replace('-', '_')

    return df