import base64
import json
import os

import pulumi
import pulumi_aws as aws
import pulumi_gcp as gcp
from dotenv import load_dotenv

load_dotenv()


# Fetching environment variables with error handling
def get_env_variable(var_name):
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Environment variable {var_name} not set!")
    return value


CIDR_BLOCK = get_env_variable("CIDR_BLOCK")
TAG_BASE_NAME = get_env_variable("TAG_BASE_NAME")
PUBLIC_ROUTE_CIDR_BLOCK = get_env_variable("PUBLIC_ROUTE_CIDR_BLOCK")
MAX_NUM_AZS = int(get_env_variable("MAX_NUM_AZS"))

my_vpc = aws.ec2.Vpc(
    "my_vpc",
    cidr_block=CIDR_BLOCK,
    instance_tenancy="default",
    tags={
        "Name": f"{TAG_BASE_NAME}-my-vpc",
    },
)

availability_zones = aws.get_availability_zones()
num_azs = min(len(availability_zones.names), MAX_NUM_AZS)

public_rt = aws.ec2.RouteTable(
    "public-route-table",
    vpc_id=my_vpc.id,
    tags={
        "Name": f"{TAG_BASE_NAME}-public-rt",
    },
)

private_rt = aws.ec2.RouteTable(
    "private-route-table",
    vpc_id=my_vpc.id,
    tags={
        "Name": f"{TAG_BASE_NAME}-private-rt",
    },
)

igw = aws.ec2.InternetGateway(
    "igw",
    vpc_id=my_vpc.id,
    tags={
        "Name": f"{TAG_BASE_NAME}-igw",
    },
)

public_route = aws.ec2.Route(
    "public-route",
    route_table_id=public_rt.id,
    destination_cidr_block=PUBLIC_ROUTE_CIDR_BLOCK,
    gateway_id=igw.id,
)

public_subnets = []
private_subnets = []

for i in range(num_azs):
    public_subnet = aws.ec2.Subnet(
        f"public_subnet-{i}",
        vpc_id=my_vpc.id,
        cidr_block=get_env_variable(f"PUBLIC_SUBNET_CIDR_BLOCK{i}"),
        availability_zone=availability_zones.names[i],
        map_public_ip_on_launch=True,
        tags={
            "Name": f"{TAG_BASE_NAME}-public_subnet-{i}",
        },
    )
    public_subnets.append(public_subnet)

    aws.ec2.RouteTableAssociation(
        f"public_subnet-{i}-rt-association",
        subnet_id=public_subnet.id,
        route_table_id=public_rt.id,
    )

    private_subnet = aws.ec2.Subnet(
        f"private_subnet-{i}",
        vpc_id=my_vpc.id,
        cidr_block=get_env_variable(f"PRIVATE_SUBNET_CIDR_BLOCK{i}"),
        availability_zone=availability_zones.names[i],
        map_public_ip_on_launch=False,
        tags={
            "Name": f"{TAG_BASE_NAME}-private_subnet-{i}",
        },
    )
    private_subnets.append(private_subnet)

    aws.ec2.RouteTableAssociation(
        f"private_subnet-{i}-rt-association",
        subnet_id=private_subnet.id,
        route_table_id=private_rt.id,
    )

SG_CIDR_BLOCK = get_env_variable("SG_CIDR_BLOCK")
APP_INGRESS_PORTS = list(map(int, get_env_variable("APP_INGRESS_PORTS").split(",")))
APP_EGRESS_PORT = int(get_env_variable("APP_EGRESS_PORT"))
DB_INGRESS_PORT = int(get_env_variable("DB_INGRESS_PORT"))
DB_EGRESS_PORT = int(get_env_variable("DB_EGRESS_PORT"))
LB_INGRESS_PORTS = list(map(int, get_env_variable("LB_INGRESS_PORTS").split(",")))
LB_EGRESS_PORT = int(get_env_variable("LB_EGRESS_PORT"))


lb_security_group = aws.ec2.SecurityGroup(
    "load_balancer_security_group",
    vpc_id=my_vpc.id,
    description="Security group for Load balancer",
    ingress=[
        {
            "protocol": "tcp",
            "from_port": port,
            "to_port": port,
            "cidr_blocks": [SG_CIDR_BLOCK],
        }
        for port in LB_INGRESS_PORTS
    ],
    egress=[
        {
            "protocol": "-1",
            "from_port": LB_EGRESS_PORT,
            "to_port": LB_EGRESS_PORT,
            "cidr_blocks": [SG_CIDR_BLOCK],
        }
    ],
    tags={
        "Name": f"{TAG_BASE_NAME}-lb_security_group",
    },
)

app_security_group = aws.ec2.SecurityGroup(
    "application_security_group",
    vpc_id=my_vpc.id,
    description="Security group for application",
    ingress=[
        # Allow SSH
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": [SG_CIDR_BLOCK],
        },
        # Allow application traffic from load balancer
        {
            "protocol": "tcp",
            "from_port": 5000,
            "to_port": 5000,
            "security_groups": [lb_security_group.id],
        },
    ],
    egress=[
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"],
        }
    ],
    tags={
        "Name": f"{TAG_BASE_NAME}-webapp_security_group",
    },
)


db_security_group = aws.ec2.SecurityGroup(
    "db_security_group",
    vpc_id=my_vpc.id,
    description="Security group for RDS database",
    ingress=[
        {
            "protocol": "tcp",
            "from_port": DB_INGRESS_PORT,
            "to_port": DB_INGRESS_PORT,
            "security_groups": [app_security_group.id],
        }
    ],
    egress=[
        {
            "protocol": "-1",
            "from_port": DB_EGRESS_PORT,
            "to_port": DB_EGRESS_PORT,
            "cidr_blocks": [SG_CIDR_BLOCK],
        }
    ],
    tags={
        "Name": f"{TAG_BASE_NAME}-db_security_group",
    },
)


db_param_grp = aws.rds.ParameterGroup(
    "rds-parameter-group",
    family="postgres15",
    description="Custom parameter group for csye6225",
    tags={
        "Name": f"{TAG_BASE_NAME}-parameter-group",
    },
)

db_subnet_group = aws.rds.SubnetGroup(
    "db_subnet_group",
    subnet_ids=[subnet.id for subnet in private_subnets],
    tags={
        "Name": f"{TAG_BASE_NAME}-db-subnet-group",
    },
)

RDS_DB_NAME = get_env_variable("RDS_DB_NAME")
RDS_ENGINE = get_env_variable("RDS_ENGINE")
RDS_ENGINE_VERSION = get_env_variable("RDS_ENGINE_VERSION")
RDS_INSTANCE_CLASS = get_env_variable("RDS_INSTANCE_CLASS")
RDS_STORAGAE = get_env_variable("RDS_STORAGAE")
RDS_IDENTIFIER = get_env_variable("RDS_IDENTIFIER")
RDS_USERNAME = get_env_variable("RDS_USERNAME")
RDS_DB_PASSWORD = get_env_variable("RDS_DB_PASSWORD")
RDS_MULTI_AZ = get_env_variable("RDS_MULTI_AZ")
RDS_PUBLICLY_ACCESSIBLE = get_env_variable("RDS_PUBLICLY_ACCESSIBLE")
RDS_PORT = get_env_variable("RDS_PORT")
USERDATA_USER = get_env_variable("USERDATA_USER")
USERDATA_GROUP = get_env_variable("USERDATA_GROUP")

rds_instance = aws.rds.Instance(
    "csye6225-rds-instance",
    db_name=RDS_DB_NAME,
    allocated_storage=RDS_STORAGAE,
    engine=RDS_ENGINE,
    engine_version=RDS_ENGINE_VERSION,
    instance_class=RDS_INSTANCE_CLASS,
    identifier=RDS_IDENTIFIER,
    parameter_group_name=db_param_grp.name,
    username=RDS_USERNAME,
    password=RDS_DB_PASSWORD,
    skip_final_snapshot=True,
    vpc_security_group_ids=[db_security_group.id],
    db_subnet_group_name=db_subnet_group.name,
    tags={
        "Name": f"{TAG_BASE_NAME}-rds-instance",
    },
    multi_az=RDS_MULTI_AZ,
    publicly_accessible=RDS_PUBLICLY_ACCESSIBLE,
)


custom_role = aws.iam.Role(
    "custom_role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com",
                    },
                }
            ],
        }
    ),
    tags={
        "Name": f"{TAG_BASE_NAME}-custom_role",
    },
)


cloudwatch_instance_profile = aws.iam.InstanceProfile(
    "cloudwatch_instance_profile",
    role=custom_role.name,
    tags={
        "Name": f"{TAG_BASE_NAME}-instance_profile",
    },
)

cloudwatch_policy_attachment = aws.iam.RolePolicyAttachment(
    "cloudwatch_role_policy_attachment",
    role=custom_role.name,
    policy_arn="arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
)

aws.iam.RolePolicyAttachment(
    "sns_policy_attachment",
    role=custom_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSNSFullAccess",
)

log_policy_document = aws.iam.get_policy_document(
    statements=[
        aws.iam.GetPolicyDocumentStatementArgs(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=["arn:aws:logs:*:*:*"],
        )
    ]
)

log_policy = aws.iam.Policy("logPolicy", policy=log_policy_document.json)

log_policy_attachment = aws.iam.RolePolicyAttachment(
    "logPolicyAttachment", role=custom_role.name, policy_arn=log_policy.arn
)


lambda_role = aws.iam.Role(
    "csye6225-lambda-role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags={"Name": f"{TAG_BASE_NAME}-lambda_role"},
)

aws.iam.RolePolicyAttachment(
    "lambda_execution_policy_attachment",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)


sns_topic = aws.sns.Topic(
    "userUpdates",
    tags={
        "Name": f"{TAG_BASE_NAME}-userUpdates",
    },
)


my_bucket = gcp.storage.get_bucket(name=os.getenv("GCP_BUCKET_NAME"))
gcp_service_account = gcp.serviceaccount.Account(
    "csye6225_gcp_service_Account",
    account_id=os.getenv("GCP_SERVICE_ACCOUNT_ID"),
    display_name=f"{TAG_BASE_NAME}-gcp-service-account",
)

gcp_key = gcp.serviceaccount.Key(
    "gcp_key",
    service_account_id=gcp_service_account.name,
)

gcp_role_binding = gcp_service_account.email.apply(
    lambda email: gcp.storage.BucketIAMBinding(
        "csye6225_gcp_role_binding",
        bucket=my_bucket.name,
        role="roles/storage.objectUser",
        members=[f"serviceAccount:{email}"],
    )
)

email_tracking_table = aws.dynamodb.Table(
    "email_tracking_table",
    attributes=[
        aws.dynamodb.TableAttributeArgs(name="id", type="S"),
    ],
    hash_key="id",
    billing_mode="PROVISIONED",
    read_capacity=5,
    write_capacity=5,
    tags={
        "Name": f"{TAG_BASE_NAME}-email_tracking",
    },
)

dynamodb_policy_document = aws.iam.get_policy_document(
    statements=[
        aws.iam.GetPolicyDocumentStatementArgs(
            actions=["dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[email_tracking_table.arn],
        )
    ]
)


dynamodb_policy = aws.iam.Policy(
    "lambda_dynamodb_policy",
    policy=dynamodb_policy_document.json,
)

aws.iam.RolePolicyAttachment(
    "lambda_dynamodb_policy_attachment",
    role=lambda_role.name,
    policy_arn=dynamodb_policy.arn,
)


lambda_function = aws.lambda_.Function(
    "lambda_function",
    code=pulumi.FileArchive("./lambda_function.zip"),
    role=lambda_role.arn,
    handler="app.lambda_handler",
    runtime="python3.11",
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "GCP_BUCKET_NAME": os.getenv("GCP_BUCKET_NAME"),
            "GCP_SERVICE_ACCOUNT_ID": os.getenv("GCP_SERVICE_ACCOUNT_ID"),
            "SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY"),
            "GCP_KEY": gcp_key.private_key.apply(lambda key: key),
            "DYNAMODB_TABLE_NAME": email_tracking_table.name.apply(lambda name: name),
        },
    ),
)

aws.lambda_.Permission(
    "sns_invoke_permission",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="sns.amazonaws.com",
    source_arn=sns_topic.arn,
)
sns_subscription = aws.sns.TopicSubscription(
    "lambdaSubscription",
    topic=sns_topic.arn,
    protocol="lambda",
    endpoint=lambda_function.arn,
)


def generate_user_data_script(rds_endpoint, sns_arn):
    return f"""#!/bin/bash
ENV_FILE="/opt/webapp.properties"
echo "DB_USERNAME={RDS_USERNAME}" > $ENV_FILE
echo "DB_PASSWORD={RDS_DB_PASSWORD}" >> $ENV_FILE
echo "DB_HOSTNAME={rds_endpoint}" >> $ENV_FILE
echo "FLASK_APP={get_env_variable('FLASK_APP')}" >> $ENV_FILE
echo "FLASK_DEBUG={get_env_variable('FLASK_DEBUG')}" >> $ENV_FILE
echo "DATABASE_URL=postgresql://{RDS_USERNAME}:{RDS_DB_PASSWORD}@{rds_endpoint}/{RDS_DB_NAME}" >> $ENV_FILE
echo "CSV_PATH={get_env_variable('CSV_PATH')}" >> $ENV_FILE
echo "AWS_REGION={get_env_variable('AWS_REGION')}" >> $ENV_FILE
echo "SNS_TOPIC_ARN={sns_arn}" >> $ENV_FILE
chown {USERDATA_USER}:{USERDATA_GROUP} $ENV_FILE
sudo chown -R {USERDATA_USER}:{USERDATA_GROUP} /opt/webapp/
sudo chown {USERDATA_USER}:{USERDATA_GROUP} /opt/users.csv
sudo chown csye6225:csye6225 /var/log/webapp/csye6225.log
chmod 400 $ENV_FILE
sudo systemctl daemon-reload
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -c file:/opt/cloudwatch-config.json \
    -s
sudo systemctl enable amazon-cloudwatch-agent
sudo systemctl start amazon-cloudwatch-agent
sudo systemctl start csye6225
"""


combined_output = pulumi.Output.all(rds_instance.endpoint, sns_topic.arn)

# Use apply to generate the user data script with both values
user_data_script = combined_output.apply(
    lambda args: generate_user_data_script(args[0], args[1])
)

# Encode the user data script
user_data_encoded = user_data_script.apply(
    lambda ud: base64.b64encode(ud.encode()).decode()
)


asg_launch_template = aws.ec2.LaunchTemplate(
    "asg_launch_template",
    block_device_mappings=[
        aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
            device_name="/dev/xvda",
            ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                volume_size=25,
                volume_type=get_env_variable("ROOT_VOLUME_TYPE"),
                delete_on_termination=get_env_variable("DELETE_ON_TERMINATION"),
            ),
        )
    ],
    network_interfaces=[
        aws.ec2.LaunchTemplateNetworkInterfaceArgs(
            associate_public_ip_address=True,
            security_groups=[app_security_group.id],
            # subnet_id=public_subnets[0].id,
        )
    ],
    disable_api_termination=get_env_variable("DISABLE_API_TERMINATION"),
    iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
        arn=cloudwatch_instance_profile.arn,
    ),
    image_id=get_env_variable("AMI_ID"),
    instance_initiated_shutdown_behavior="terminate",
    instance_type=get_env_variable("INSTANCE_TYPE"),
    key_name=get_env_variable("KEY_NAME"),
    # vpc_security_group_ids=[app_security_group.id],
    tag_specifications=[
        aws.ec2.LaunchTemplateTagSpecificationArgs(
            resource_type="instance",
            tags={
                "Name": f"{TAG_BASE_NAME}-launch_template-instance",
            },
        )
    ],
    tags={
        "Name": f"{TAG_BASE_NAME}-launch-template",
    },
    update_default_version=True,
    # opts=pulumi.ResourceOptions(depends_on=[rds_instance]),
    user_data=user_data_encoded,
)


alb = aws.lb.LoadBalancer(
    "csye6225-alb",
    internal=False,
    load_balancer_type="application",
    security_groups=[lb_security_group.id],
    subnets=[subnet.id for subnet in public_subnets],
    enable_deletion_protection=False,
    tags={
        "Name": f"{TAG_BASE_NAME}-load_balancer",
    },
)

target_group = aws.lb.TargetGroup(
    "csye6225-target-group",
    port=5000,
    protocol="HTTP",
    vpc_id=my_vpc.id,
    health_check={
        "enabled": True,
        "healthy_threshold": 2,
        "interval": 30,
        "path": "/healthz",
        "protocol": "HTTP",
    },
)

cert_arn = aws.acm.get_certificate(domain=os.getenv("CERT_DOMAIN"), statuses=["ISSUED"])


front_end_listener = aws.lb.Listener(
    "csye6225_frontEndListener",
    load_balancer_arn=alb.arn,
    port=443,
    protocol="HTTPS",
    ssl_policy="ELBSecurityPolicy-2016-08",
    certificate_arn=cert_arn.arn,
    default_actions=[
        aws.lb.ListenerDefaultActionArgs(
            type="forward",
            target_group_arn=target_group.arn,
        )
    ],
)

asg = aws.autoscaling.Group(
    "csye6225_asg",
    # availability_zones=availability_zones.names,
    default_cooldown=60,
    desired_capacity=1,
    max_size=3,
    min_size=1,
    launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
        id=asg_launch_template.id,
        version="$Latest",
    ),
    vpc_zone_identifiers=[subnet.id for subnet in public_subnets],
    health_check_grace_period=300,
    health_check_type="EC2",
    target_group_arns=[target_group.arn],
    opts=pulumi.ResourceOptions(depends_on=[rds_instance, asg_launch_template]),
    tags=[
        aws.autoscaling.GroupTagArgs(
            key="asg-key",
            value=f"{TAG_BASE_NAME}-asg",
            propagate_at_launch=True,
        )
    ],
    instance_refresh=aws.autoscaling.GroupInstanceRefreshArgs(
        strategy="Rolling",
        # triggers=
    ),
)

scale_out_policy = aws.autoscaling.Policy(
    "csye6225_asg_scale_out_policy",
    scaling_adjustment=1,
    adjustment_type="ChangeInCapacity",
    autoscaling_group_name=asg.name,
)

scale_in_policy = aws.autoscaling.Policy(
    "csye6225_asg_scale_in_policy",
    scaling_adjustment=-1,
    adjustment_type="ChangeInCapacity",
    autoscaling_group_name=asg.name,
)

# CloudWatch Alarms for Auto Scaling
scale_out_alarm = aws.cloudwatch.MetricAlarm(
    "csye6225_scale_out_alarm",
    comparison_operator="GreaterThanOrEqualToThreshold",
    evaluation_periods=2,
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    period=60,
    statistic="Average",
    threshold=5,
    alarm_description="Scale up if CPU > 5%",
    dimensions={"AutoScalingGroupName": asg.name},
    alarm_actions=[scale_out_policy.arn],
)

scale_in_alarm = aws.cloudwatch.MetricAlarm(
    "csye6225_scale_in_alarm",
    comparison_operator="LessThanOrEqualToThreshold",
    evaluation_periods=2,
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    period=60,
    statistic="Average",
    threshold=3,
    alarm_description="Scale down if CPU < 3%",
    dimensions={"AutoScalingGroupName": asg.name},
    alarm_actions=[scale_in_policy.arn],
)


HOSTED_ZONE_NAME = get_env_variable("HOSTED_ZONE_NAME")
HOSTED_ZONE_ID = get_env_variable("HOSTED_ZONE_ID")

a_record = aws.route53.Record(
    "a_record",
    zone_id=HOSTED_ZONE_ID,
    name=HOSTED_ZONE_NAME,
    type="A",
    # ttl=60,
    opts=pulumi.ResourceOptions(depends_on=[alb]),
    # records=[alb.id],
    allow_overwrite=True,
    aliases=[
        aws.route53.RecordAliasArgs(
            name=alb.dns_name,
            zone_id=alb.zone_id,
            evaluate_target_health=True,
        )
    ],
)
