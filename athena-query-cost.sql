# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

SELECT 
    job_id, 
    sum(cost) as cost,
    vc_id
    
FROM "athenacurcfn_c_u_r"."emr_eks_cost" 

WHERE job_id = '000000031p3s4hj6js9'

GROUP BY job_id, vc_id;