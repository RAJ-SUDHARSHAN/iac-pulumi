# Infrastructure as Code with Pulumi

## Local Setup

### Clone the Repository

```bash
git clone git@github.com:RAJ-SUDHARSHAN/iac-pulumi.git
cd iac-pulumi
```

### Setup Virtual Environment and Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure Environment Variables:
```bash
CIDR_BLOCK=<vpc-cidr-block>
TAG_BASE_NAME=<tag-base-name>
PUBLIC_ROUTE_CIDR_BLOCK=<public-route-cidr-block>
MAX_NUM_AZS=<max-number-of-availability-zones>
PUBLIC_SUBNET_CIDR_BLOCK0=<public-subnet-0-cidr-block>
PUBLIC_SUBNET_CIDR_BLOCK1=<public-subnet-1-cidr-block>
PUBLIC_SUBNET_CIDR_BLOCK2=<public-subnet-2-cidr-block>
PRIVATE_SUBNET_CIDR_BLOCK0=<private-subnet-0-cidr-block>
PRIVATE_SUBNET_CIDR_BLOCK1=<private-subnet-1-cidr-block>
PRIVATE_SUBNET_CIDR_BLOCK2=<private-subnet-2-cidr-block>
```