# CycleLink Infrastructure

This directory contains the infrastructure-as-code (IaC) configuration for the CycleLink project, managed using [OpenTofu](https://opentofu.org/) (a fork of Terraform).

## Prerequisites
Before you start, you must install the following tools on your local machine:

### 1. OpenTofu
OpenTofu is used to provision and manage our cloud infrastructure.

**macOS:**
```bash
brew install opentofu
```

*(For other operating systems, refer to the [official installation guide](https://opentofu.org/docs/intro/install/)).*

### 2. AWS CLI
We use AWS to host our infrastructure. The AWS CLI allows OpenTofu to authenticate and manage your resources.

**macOS:**
```bash
brew install awscli
```

### 3. AWS Credentials
You will need your own AWS Access Keys to interact with the AWS account.
1. Log in to the AWS Console.
2. Go to **IAM (Identity and Access Management)** -> **Users** -> *Select your user* -> **Security credentials**.
3. Create an Access Key.

Once you have your credentials, run the following command in your terminal:
```bash
aws configure
```

You will be prompted to enter the following:
- **AWS Access Key ID**: `YOUR_ACCESS_KEY`
- **AWS Secret Access Key**: `YOUR_SECRET_KEY`
- **Default region name**: `ap-southeast-1` *(This is our default region)*
- **Default output format**: `json`

## Getting Started

Now that the required tools and access are set up, you can initialize the project.
This repository is structured into environments to separate **development** and **production** infrastructure safely. The environments call a reusable configuration defined in the `modules/core` folder.

### Step 1: Navigate to your Environment

For local development, navigate to the `dev` environment folder:

```bash
cd environments/dev
```

### Step 2: Initialize OpenTofu
You need to run this command when you first clone the repository, or if you add new providers/modules to the `.tf` files. It downloads the required provider plugins (like AWS).

```bash
tofu init
```

### Step 3: Validate the Configuration
Ensure your configuration files are syntactically valid and internally consistent:
```bash
tofu validate
```

### Step 4: Plan Changes
This command compares your configuration (`.tf` files) with the actual state of the infrastructure in AWS. It tells you exactly **what it will create, modify, or destroy** without actually doing it.

```bash
tofu plan
```
Always review the output of `tofu plan` carefully!

### Step 5: Apply Changes
Once you are satisfied with the plan, you can apply your changes to provision the resources.

```bash
tofu apply
```
It will show you the plan again and ask for confirmation before modifying anything on AWS.

## How to Add a New Resource

Instead of modifying the environment directly, you should define your resources in the shared module.

1. **Find the Resource in the Provider Documentation**: Go to the [AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs) and find the resource you want to create (e.g., `aws_s3_bucket`, `aws_instance`).
2. **Write the Configuration in the Core Module**: Open `modules/core/main.tf` and declare the resource block. Use the `var.environment` variable to ensure resource names are unique per environment. For example:
   ```hcl
   resource "aws_s3_bucket" "my_new_bucket" {
     bucket = "cyclelink-${var.environment}-unique-bucket-name"
   }
   ```
3. **Run `tofu plan`**: Execute `tofu plan` in your `environments/dev` terminal. OpenTofu will display a plan indicating exactly what changes will take place.
4. **Run `tofu apply`**: If the plan looks correct, run `tofu apply` to make the actual changes to your AWS account.

## Connecting Code to Infrastructure

When OpenTofu provisions a resource (like a database or an S3 bucket), AWS assigns it a dynamic endpoint or ID. Your application code needs these values to interact with the resources. 

1. **Output the Resource in the Module**: Open `modules/core/outputs.tf` and define an output:
   ```hcl
   output "bucket_name" {
     value = aws_s3_bucket.my_new_bucket.bucket
   }
   ```
2. **Retrieve the Output**: Run `tofu apply`. At the end of the process, OpenTofu will print the requested values to your terminal:
   ```text
   Outputs:

   bucket_name = "cyclelink-dev-unique-bucket-name"
   ```
3. **Configure Your Environment**: Copy these output values into your backend's `.env` file so your application code can use them during local development:
   ```env
   # ../../.env
   S3_BUCKET_NAME=cyclelink-dev-unique-bucket-name
   ```

## Useful Resources
- [OpenTofu Documentation](https://opentofu.org/docs/)
- [AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
