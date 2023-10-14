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

for i in range(num_azs):
    public_subnet = aws.ec2.Subnet(
        f"public_subnet-{i}",
        vpc_id=my_vpc.id,
        cidr_block=get_env_variable(f"PUBLIC_SUBNET_CIDR_BLOCK{i}"),
        availability_zone=availability_zones.names[i],
        tags={
            "Name": f"{TAG_BASE_NAME}-public_subnet-{i}",
        },
    )

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
        tags={
            "Name": f"{TAG_BASE_NAME}-private_subnet-{i}",
        },
    )

    aws.ec2.RouteTableAssociation(
        f"private_subnet-{i}-rt-association",
        subnet_id=private_subnet.id,
        route_table_id=private_rt.id,
    )
