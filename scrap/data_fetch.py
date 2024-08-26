import requests
import sys

def execute_kubecost_allocation_api(kubecost_api_endpoint, start, end, granularity, aggregate, logger):

    """Executes Kubecost Allocation API on a a 1h window, example 08:00 to 09:00

    :param kubecost_api_endpoint: the Kubecost API endpoint, in format of "http://<service>.<namespace>:<port>"
    :param start: the start time for calculating Kubecost Allocation API window
    :param end: the end time for calculating Kubecost Allocation API window
    :param granularity: the user input time granularity, to use for calculating the step (daily or hourly)
    :return: the Kubecost Allocation API query "data" list
    """

    window = f'{start.strftime("%Y-%m-%dT%H:%M:%SZ")},{end.strftime("%Y-%m-%dT%H:%M:%SZ")}'

    logger.info(f"Querying Kubecost Allocation API for data between {start} and {end} with aggregate {aggregate}")

    #The aggregate is used to query Kubecost only on EMR on EKS related data
    #It uses labels that are for Virtual Cluster Id and Job Id
    #aggregate = "pod,label:emr-containers.amazonaws.com/job.id,label:emr-containers.amazonaws.com/virtual-cluster-id"

    step = granularity

    accumulate=False

    #Query Kubecost API
    try:       
        params = {"window": window, "aggregate": aggregate, "accumulate": accumulate, "step": step}

        r = requests.get(f"{kubecost_api_endpoint}/model/allocation/compute", params=params, timeout=30)

        if not list(filter(None, r.json()["data"])):
            logger.info("No allocation data found in kubecost")
            return None

        return r.json()["data"]
    
    except requests.exceptions.ConnectionError as error:
        logger.error(f"Error connecting to Kubecost Allocation API: {error}")
        sys.exit(1)

def execute_kubecost_assets_api(kubecost_api_endpoint, start, end, logger):
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
    params = {"window": window, "accumulate": accumulate, "filterCategories": "compute", "filterTypes": "Node"}
    
    try:
        r = requests.get(f"{kubecost_api_endpoint}/model/assets", params=params, timeout=120)

        if not list(filter(None, r.json()["data"])):
                logger.info("No data found")
                return None

        return r.json()["data"]
    
    except requests.exceptions.ConnectionError as error:
        logger.error(f"Error connecting to Kubecost Allocation API: {error}")
        sys.exit(1)
