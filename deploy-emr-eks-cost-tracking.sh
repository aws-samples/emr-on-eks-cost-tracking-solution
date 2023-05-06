# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

if [ $# -eq 0 ]
  then
    echo "Please provide Region, Kubecost version, EKS cluster name, aws account id"
    return
fi

#The path under which CUR data is stored in S3 bucket
#For the structure this link https://docs.aws.amazon.com/cur/latest/userguide/understanding-report-versions.html
S3PREFIX=cur_data

#These buckets are created by the cloudformation deployed below
CUR_QUERY_RESULTS=aws-athena-query-results-cur-$1-$4
CUR_BUCKET=cost-data-$1-$4
CFN_STACK_NAME=cost-stack

#This cloudformation deploy buckets to store raw and athena query results 
#as well as set their resource policy
#Create Athena workgroup and the IAM policies needed by kubecost
#Create the glue database and glue crawler with its S3 trigger to start it 
#everytime new cur data is delivered to S3 bucket 
#create amazon managed prometheus and ECR repository
echo "Deploy base infrastructure"

aws cloudformation deploy --capabilities CAPABILITY_NAMED_IAM --template-file emr-eks-cost-cfn.yml --stack-name $CFN_STACK_NAME --parameter-overrides S3Bucket=$CUR_BUCKET S3Prefix=$S3PREFIX

#Create Cost and Usage Report
echo "Create cost and usage report"

aws cur put-report-definition \
    --report-definition "{
        \"ReportName\": \"cur_data\",
        \"TimeUnit\": \"HOURLY\",
        \"Format\": \"Parquet\",
        \"Compression\": \"Parquet\",
        \"AdditionalSchemaElements\": [\"RESOURCES\"],
        \"S3Bucket\": \"$CUR_BUCKET\",
        \"S3Prefix\": \"$S3PREFIX\",
        \"S3Region\": \"$1\",
        \"AdditionalArtifacts\": [\"ATHENA\"],
        \"RefreshClosedReports\": true,
        \"ReportVersioning\": \"OVERWRITE_REPORT\"
    }" \
    --region us-east-1


#Create Spot feed
echo "Create Spot feed"

aws ec2 create-spot-datafeed-subscription \
    --bucket $CUR_BUCKET \
    --prefix spot-feed \
    --region $1

#Get Amazon managed prometheus workspace id to be used in Helm values config
workspace_id=$(aws cloudformation --region eu-west-1 describe-stacks --stack-name $CFN_STACK_NAME --query "Stacks[0].Outputs[0].OutputValue")

#remove the double quotes from string
workspace_id=`sed -e 's/^"//' -e 's/"$//' <<<"$workspace_id"`

#Create the Helm values
echo "Creating Kubecost Helm values"

cat << EOF > config-values.yaml
global:
  amp:
    enabled: true
    prometheusServerEndpoint: http://localhost:8005/workspaces/$workspace_id
    remoteWriteService: https://aps-workspaces.${1}.amazonaws.com/workspaces/$workspace_id/api/v1/remote_write
    sigv4:
      region: ${1}

sigV4Proxy:
  region: ${1}
  host: aps-workspaces.${1}.amazonaws.com

kubecostModel:
  extraEnv:
  - name: LOG_LEVEL
    value: trace

kubecostProductConfigs:
  labelMappingConfigs:
    enabled: true
  athenaProjectID: "$4"
  athenaBucketName: "s3://aws-athena-query-results-cur-$1-$4"
  athenaRegion: $1
  athenaDatabase: athenacurcfn_c_u_r
  athenaTable: "$S3PREFIX"
  athenaWorkgroup: "emr-eks-cost-analysis"
  awsSpotDataRegion: $1
  awsSpotDataBucket: $CUR_BUCKET
  awsSpotDataPrefix: spot-feed
  projectID: "$4"
  clusterName: $3

EOF

echo "Deploying Kubecost"

helm upgrade -i kubecost \
oci://public.ecr.aws/kubecost/cost-analyzer --version $2 \
--namespace kubecost --create-namespace \
-f https://tinyurl.com/kubecost-amazon-eks \
-f config-values.yaml

echo "Create IRSA for Kubecost"

eksctl create iamserviceaccount \
    --name kubecost-cost-analyzer \
    --namespace kubecost \
    --cluster $3 --region $1 \
    --attach-policy-arn arn:aws:iam::$4:policy/kubecost-amp-policy \
    --attach-policy-arn arn:aws:iam::$4:policy/kubecost-cur-policy \
    --override-existing-serviceaccounts \
    --approve

eksctl create iamserviceaccount \
    --name kubecost-prometheus-server \
    --namespace kubecost \
    --cluster $3 --region $1 \
    --attach-policy-arn arn:aws:iam::$4:policy/kubecost-policy \
    --override-existing-serviceaccounts \
    --approve

echo "Restarting Kubecost Pods"
kubectl rollout restart deployment/kubecost-prometheus-server -n kubecost
kubectl rollout restart deployment/kubecost-cost-analyzer -n kubecost

#Get ECR URI to upload docker image for emr-eks compute cost exporter
ECR_URI=$(aws cloudformation --region $1 describe-stacks --stack-name $CFN_STACK_NAME --query "Stacks[0].Outputs[1].OutputValue")

ECR_URI=`sed -e 's/^"//' -e 's/"$//' <<<"$ECR_URI"`

echo "Get ECR login credentials"
aws ecr get-login-password --region $1 | docker login --username AWS --password-stdin $ECR_URI

echo "Building docker container"
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t $ECR_URI:v1 \
    -f Dockerfile \
    --push .

echo "Create namespace"
kubectl create namespace emr-eks-cost-tracking

echo "Create IRSA for emr-eks-cost-exporter pod"
eksctl create iamserviceaccount \
    --name emr-eks-cost-tracking-sa \
    --namespace emr-eks-cost-tracking \
    --cluster $3 --region $1 \
    --attach-policy-arn arn:aws:iam::$4:policy/kubecost-s3-exporter-policy \
    --approve

#Updating the k8s manifest with ECR URI
sed "s/ECR_IMAGE/$(echo $ECR_URI:v1 | sed 's/\//\\\//g')/g" k8s/job-definition-template.ytpl > k8s/job-definition-template.yml

#Provide the bucket where cost data is going to be stored
sed "s/CUR_BUCKET/$CUR_BUCKET/g" k8s/job-definition-template.yml > k8s/job-definition.yml

echo "Create CRON job for emr-eks-cost-exporter"
kubectl apply -f k8s/job-definition.yml

rm k8s/job-definition-template.yml

echo "=============="
echo "To connect to kubecost Dashboard please use the folllowing command:"
echo "kubectl port-forward --namespace kubecost deployment/kubecost-cost-analyzer 9090"
echo "On your browswe visit: http://localhost:9090/"
echo " "
echo "Compute cost data is stored in s3://cost-data-$1-$4/compute_cost"
echo "Cost and Usage report is stored in s3://cost-data-$1-$4/cur_data/cur_data/cur_data/"
echo "Compute cost data can be queried in athena using glue database 'athenacurcfn_c_u_r' and table 'compute cost' "
echo "=============="