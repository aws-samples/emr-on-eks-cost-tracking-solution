# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

CREATE VIEW emr_eks_cost AS

SELECT
    split_part(line_item_resource_id, '/', 5) as job_id,
    split_part(line_item_resource_id, '/', 3) as vc_id, 
    sum(line_item_blended_cost) as cost,
    'emr-uplift' as category
FROM athenacurcfn_c_u_r.cur_data
WHERE product_product_family='EMR Containers'
GROUP BY line_item_resource_id

UNION

SELECT 
    job_id,
    vc_id,
    sum(cast(totalcost as decimal(13,5))) as cost,
    'compute' as category
FROM "athenacurcfn_c_u_r"."compute_cost"
group by job_id, vc_id;