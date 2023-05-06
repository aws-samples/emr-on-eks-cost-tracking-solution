# Emr Eks Cost Tracking

This repository contains a series of automation to help in the deployment of a cost tracking solution for EMR on EKS.

## Deploy

First execute `deploy-emr-eks-cost-tracking.sh` the script expect the following in this order: region, kubecost version, eks cluster name, and account id.

`sh deploy-emr-eks-cost-tracking.sh REGION KUBECOST-VERSION EKS-CLUSTER-NAME ACCOUNT-ID`

Example

`sh deploy-emr-eks-cost-tracking.sh eu-west-1 1.102.0 emreks 111111111`

## What is deployed

### Amazon Managed Prometheus

Use by Kubecost to store metrics.

### IAM Roles

### Glue crawlers, tables and database

A Glue database used to encompass all tables that store cost data.

Two glue tables:

    * One used to store information about CUR data
    * Used to store the compute cost related to each job

A Glue crawler:

    * Used to crawler CUR data and update the table partitions

### Lambda function
A lambda function to trigger the glue craweler everytime there 
is new data put by Cost and Usage Report. 

### S3 buckets

Two S3 buckets:

    * cost-data-REGION-ACCOUNT_ID: used to store cost data
    * aws-athena-query-results-cur-REGION-ACCOUNT_ID: used to store Athena query results

### Athena Workgroup:

An Amazon Athena workgroup named: emreks-compute-cost-exporter.
This workgroup is use by Kubecost to query CUR data.

### Cost and Usage Report:
Used by Kubecost and to get cost by Job in EMR on EKS. 

### Spot feed:
Used to get spot price data and used by Kubecost.


## Destroy

To delete all the resources created. First empty these two s3 buckets `cost-data-REGION-ACCOUNT_ID` and `aws-athena-query-results-cur-REGION-ACCOUNT_ID`, then Athena workgroup `emr-eks-cost-analysis` and last empty the ECR repository with the name `emreks-compute-cost-exporter`. Execute the following file `destroy-emr-eks-cost-tracking.sh`.

`sh destroy-emr-eks-cost-tracking.sh REGION EKS-CLUSTER-NAME`

Example

`sh destroy-emr-eks-cost-tracking.sh eu-west-1 emreks`

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
