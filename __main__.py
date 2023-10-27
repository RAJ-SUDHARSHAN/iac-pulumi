import os
import pulumi
import pulumi_aws as aws
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

app_security_group = aws.ec2.SecurityGroup(
    "application_security_group",
    vpc_id=my_vpc.id,
    description="Security group for application",
    ingress=[
        {
            "protocol": "tcp",
            "from_port": port,
            "to_port": port,
            "cidr_blocks": [SG_CIDR_BLOCK],
        }
        for port in APP_INGRESS_PORTS
    ],
    egress=[
        {
            "protocol": "-1",
            "from_port": APP_EGRESS_PORT,
            "to_port": APP_EGRESS_PORT,
            "cidr_blocks": [SG_CIDR_BLOCK],
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
RDS_STORGAE = get_env_variable("RDS_STORGAE")
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
    allocated_storage=RDS_STORGAE,
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


def generate_user_data_script(rds_endpoint):
    return f"""#!/bin/bash
ENV_FILE="/opt/webapp.properties"
echo "DB_USERNAME={RDS_USERNAME}" > $ENV_FILE
echo "DB_PASSWORD={RDS_DB_PASSWORD}" >> $ENV_FILE
echo "DB_HOSTNAME={rds_endpoint}" >> $ENV_FILE
echo "FLASK_APP={get_env_variable('FLASK_APP')}" >> $ENV_FILE
echo "FLASK_DEBUG={get_env_variable('FLASK_DEBUG')}" >> $ENV_FILE
echo "DATABASE_URL=postgresql://{RDS_USERNAME}:{RDS_DB_PASSWORD}@{rds_endpoint}/{RDS_DB_NAME}" >> $ENV_FILE
echo "CSV_PATH={get_env_variable('CSV_PATH')}" >> $ENV_FILE
chown {USERDATA_USER}:{USERDATA_GROUP} $ENV_FILE
sudo chown -R {USERDATA_USER}:{USERDATA_GROUP} /opt/webapp/
sudo chown {USERDATA_USER}:{USERDATA_GROUP} /opt/users.csv
chmod 400 $ENV_FILE
sudo systemctl daemon-reload
sudo systemctl start csye6225
"""


user_data_script = rds_instance.endpoint.apply(generate_user_data_script)

app_instance = aws.ec2.Instance(
    "app_instance",
    ami=get_env_variable("AMI_ID"),
    instance_type=get_env_variable("INSTANCE_TYPE"),
    key_name=get_env_variable("KEY_NAME"),
    vpc_security_group_ids=[app_security_group.id],
    subnet_id=public_subnets[0].id,
    root_block_device={
        "volume_size": int(get_env_variable("ROOT_VOLUME_SIZE")),
        "volume_type": get_env_variable("ROOT_VOLUME_TYPE"),
        "delete_on_termination": get_env_variable("DELETE_ON_TERMINATION"),
    },
    tags={
        "Name": f"{TAG_BASE_NAME}-app_instance",
    },
    disable_api_termination=get_env_variable("DISABLE_API_TERMINATION"),
    opts=pulumi.ResourceOptions(depends_on=[rds_instance]),
    user_data=user_data_script,
)
