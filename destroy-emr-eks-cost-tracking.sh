# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

if [ $# -eq 0 ]
  then
    echo "Please provide Region and EKS cluster name"
    return
fi

helm uninstall kubecost -n kubecost

eksctl delete iamserviceaccount \
    --name kubecost-prometheus-server \
    --cluster $2 \
    --region $1 \
    --namespace kubecost

eksctl delete iamserviceaccount \
    --name kubecost-cost-analyzer \
    --cluster $2 \
    --region $1 \
    --namespace kubecost

eksctl delete iamserviceaccount \
    --name emr-eks-cost-tracking-sa \
    --cluster $2 \
    --region $1 \
    --namespace emr-eks-cost-tracking

aws cur delete-report-definition --report-name cur_data --region us-east-1

kubectl delete -f k8s/job-definition.yml

kubectl delete namespace emr-eks-cost-tracking

aws cloudformation delete-stack --stack-name cost-stack