# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

CREATE EXTERNAL TABLE `compute_cost`(
  `start` string, 
  `end` string, 
  `minutes` bigint, 
  `cpucores` double, 
  `cpucorerequestaverage` bigint, 
  `cpucoreusageaverage` double, 
  `cpucorehours` double, 
  `cpucost` double, 
  `cpucostadjustment` bigint, 
  `cpuefficiency` double, 
  `gpucount` bigint, 
  `gpuhours` bigint, 
  `gpucost` bigint, 
  `gpucostadjustment` bigint, 
  `networktransferbytes` double, 
  `networkreceivebytes` double, 
  `networkcost` bigint, 
  `networkcrosszonecost` bigint, 
  `networkcrossregioncost` bigint, 
  `networkinternetcost` bigint, 
  `networkcostadjustment` bigint, 
  `loadbalancercost` bigint, 
  `loadbalancercostadjustment` bigint, 
  `pvbytes` bigint, 
  `pvbytehours` bigint, 
  `pvcost` bigint, 
  `pvs` string, 
  `pvcostadjustment` bigint, 
  `rambytes` double, 
  `rambyterequestaverage` bigint, 
  `rambyteusageaverage` double, 
  `rambytehours` double, 
  `ramcost` double, 
  `ramcostadjustment` bigint, 
  `ramefficiency` double, 
  `externalcost` bigint, 
  `sharedcost` bigint, 
  `totalcost` double, 
  `totalefficiency` double, 
  `properties.cluster` string, 
  `properties.container` string, 
  `properties.namespace` string, 
  `instance_id` string, 
  `properties.labels.emr_containers_amazonaws_com_component` string, 
  `emr_eks_subscription_id` string, 
  `properties.labels.spark_role` string, 
  `spark_version` string, 
  `capacity_type` string, 
  `pod_name` string, 
  `job_id` string, 
  `vc_id` string)
ROW FORMAT DELIMITED 
  FIELDS TERMINATED BY ',' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION
  's3://cost-data-REGION-ACCOUNT_ID/compute_cost/'
TBLPROPERTIES (
  'CrawlerSchemaDeserializerVersion'='1.0', 
  'CrawlerSchemaSerializerVersion'='1.0', 
  'UPDATED_BY_CRAWLER'='ComputeCostCrawler', 
  'areColumnsQuoted'='false',
  'classification'='csv', 
  'columnsOrdered'='true', 
  'compressionType'='none', 
  'delimiter'=',', 
  'skip.header.line.count'='1', 
  'typeOfData'='file')