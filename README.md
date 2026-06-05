# 🦈 Remora-Fin: High-Performance AWS FinOps CLI

**Remora-Fin** is a lightweight, high-performance FinOps toolkit for AWS. Built with Polars and Textual, it attaches to your AWS environment to analyze spending, detect anomalies, and export professional-grade reports.

---

## 🚀 Key Features

* **📈 Vector Graphics:** Native PDF visualizations (Bars & Lines) with zero external dependencies.
* **📂 High-Speed Analysis:** Powered by **Polars** for near-instant processing of large billing datasets.
* **🔍 Anomaly Intelligence:** Identify unexpected cost spikes using AWS Cost Explorer algorithms.
* **🔮 Predictive Analysis:** Integrated spending forecasts to avoid end-of-month surprises.
* **🖥️ Terminal UI:** Interactive dashboard (TUI) with a high-performance **UI Facade** and internal caching for ultra-responsive navigation.
* **🏗️ Registry Architecture:** Dynamically managed AWS inventory via a centralized resource registry, making it easy to extend monitoring to new services.
* **🔒 Privacy First:** All data processing happens locally on your machine. Remora-Fin never sends your billing data to external servers.

---

## 📦 Installation

Install Remora-Fin using `pip` or `uv`:

```bash
# Using uv (Recommended)
uv tool install remora-fin

# Using pip
pip install remora-fin
```

---

## 🔐 IAM Permissions

Remora-Fin requires **read-only** access to AWS Cost Explorer, Organizations, and various resource metadata for the dashboard inventory.

### Option 1: Managed Policy (Recommended)
Attach the AWS managed policy **`ReadOnlyAccess`** to your IAM user or role. This is the simplest way to ensure all features work correctly.

### Option 2: Granular Permissions
If you prefer a least-privilege approach, ensure your IAM identity has the following permissions:

| Service | Action | Purpose |
| --- | --- | --- |
| **Cost Explorer** | `ce:GetCostAndUsage` | Cost reports and trends. |
| | `ce:GetAnomalies` | Cost spike detection and monitor access. |
| | `ce:GetCostForecast` | Native spend projections. |
| **Security Token** | `sts:GetCallerIdentity` | Current account and user identification. |
| **Organizations** | `organizations:ListAccounts` | Multi-account environment support. |
| **Tagging** | `tag:GetResources` | Governance and tag compliance scoring. |
| **Inventory** | `ec2:DescribeInstances` | EC2 Instance tracking. |
| | `s3:ListAllMyBuckets` | S3 Bucket inventory. |
| | `rds:DescribeDBInstances` | RDS Database tracking. |
| | `lambda:ListFunctions` | Serverless function monitoring. |
| | `cloudfront:ListDistributions` | Edge delivery tracking. |
| | `dynamodb:ListTables` | NoSQL table inventory. |
| | `elasticache:DescribeCacheClusters` | In-memory cache tracking. |
| | `elasticmapreduce:ListClusters` | Big data cluster inventory. |
| | `redshift:DescribeClusters` | Data warehouse tracking. |
| | `sagemaker:ListNotebookInstances` | ML notebook monitoring. |
| | `sns:ListTopics` | Pub/Sub topic inventory. |
| | `sqs:ListQueues` | Message queue tracking. |
| | `kms:ListKeys` | KMS Key tracking. |
| | `secretsmanager:ListSecrets` | Secrets Manager tracking. |

---

## 🛠️ Commands & Usage

### 📊 `report`

Generate comprehensive cost and usage reports.

| Argument | Shortcut | Type / Choices | Default | Description |
| --- | --- | --- | --- | --- |
| `--type` | `-t` | `breakdown`, `trend`, `account`, `full` | `full` | Report type. |
| `--format` | `-f` | `pdf`, `excel`, `csv`, `markdown` | `pdf` | Output format. |
| `--days` | `-d` | `int` | `30` | Lookback period in days. |
| `--start` | | `YYYY-MM-DD` | | Start date. |
| `--end` | | `YYYY-MM-DD` | | End date. |
| `--metric` | | `UnblendedCost`, `BlendedCost`, `NetUnblendedCost`, `AmortizedCost`, `UsageQuantity` | `UnblendedCost` | Cost metric. |
| `--group-by` | | `SERVICE`, `LINKED_ACCOUNT`, `REGION`, `USAGE_TYPE` | | Group results by dimension. |
| `--service` | `-s` | `string` | | Filter by one or more AWS services (e.g., `ec2 s3`). Supports smart aliases. |
| `--include-charts` | | flag | `True` | Include visual charts in the report. |
| `--chart-labels` | | flag | `True` | Show minimalistic X and Y axis values on charts. |
| `--output` | `-o` | `path` | | Output file path. |
| `--profile` | `-p` | `string` | | AWS profile name. |
| `--region` | `-r` | `string` | | AWS region. |

```bash
# Generate a monthly breakdown in PDF for the last 30 days
remora-fin report --type breakdown --format pdf --output monthly_report.pdf

# Generate a dedicated report for EC2 and S3 with axis labels
remora-fin report --service ec2 s3 --type full --format pdf --chart-labels
```

### 🔍 `anomalies`

Detect and display AWS cost anomalies using ML-based detection.

| Argument | Shortcut | Type / Choices | Default | Description |
| --- | --- | --- | --- | --- |
| `--days` | `-d` | `int` | `30` | Lookback period (max 90). |
| `--start` | | `YYYY-MM-DD` | | Start date. |
| `--end` | | `YYYY-MM-DD` | | End date. |
| `--severity` | | `low`, `medium`, `high`, `critical` | | Filter by severity. |
| `--monitor-arn` | | `string` | | Filter by specific monitor ARN. |
| `--detail` | | flag | | Show detailed anomaly list. |
| `--json` | | flag | | Output as JSON. |
| `--profile` | `-p` | `string` | | AWS profile name. |
| `--region` | `-r` | `string` | | AWS region. |

```bash
# Detect anomalies in the last 60 days
remora-fin anomalies --days 60 --severity high
```

### 🔮 `forecast`

Predict future AWS costs using ML-based forecasting.

| Argument | Shortcut | Type / Choices | Default | Description |
| --- | --- | --- | --- | --- |
| `--days` | `-d` | `int` | `30` | Days to forecast (max 365). |
| `--start` | | `YYYY-MM-DD` | | Forecast start date. |
| `--end` | | `YYYY-MM-DD` | | End date. |
| `--metric` | | `UnblendedCost`, `BlendedCost`, `NetUnblendedCost`, `AmortizedCost`, `UsageQuantity` | `UnblendedCost` | Metric to forecast. |
| `--granularity` | | `DAILY`, `MONTHLY` | `DAILY` | Forecast granularity. |
| `--group-by-type`| | `DIMENSION`, `TAG`, `COST_CATEGORY` | | Group forecast by type. |
| `--group-by-key` | | `SERVICE`, `LINKED_ACCOUNT`, `REGION`, `USAGE_TYPE`, `INSTANCE_TYPE`, `PLATFORM` | | Group forecast by key. |
| `--scenarios` | | flag | | Show what-if scenario analysis. |
| `--json` | | flag | | Output as JSON. |
| `--profile` | `-p` | `string` | | AWS profile name. |
| `--region` | `-r` | `string` | | AWS region. |

```bash
# Forecast next 30 days of spend
remora-fin forecast --days 30 --scenarios
```

### 🖥️ `dashboard`

Launch the interactive Terminal User Interface.

| Argument | Shortcut | Type / Choices | Default | Description |
| --- | --- | --- | --- | --- |
| `--days` | `-d` | `int` | | Default period in days. |
| `--theme` | | `dark`, `light` | | UI theme. |
| `--profile` | `-p` | `string` | | AWS profile name. |
| `--region` | `-r` | `string` | | AWS region. |

```bash
remora-fin dashboard --days 60 --theme dark
```

### 🔐 `login`

Configure and test AWS credentials.

| Argument | Shortcut | Type / Choices | Default | Description |
| --- | --- | --- | --- | --- |
| `--profile` | `-p` | `string` | `default` | AWS profile name. |
| `--region` | `-r` | `string` | | AWS region. |
| `--test` | `-t` | flag | | Test existing credentials. |
| `--configure` | `-c` | flag | | Interactive configuration. |

```bash
# Configure interactively
remora-fin login --configure

# Test existing credentials
remora-fin login --test
```

### 👤 `profile`

View current remora-fin configuration and AWS session identity.

```bash
remora-fin profile
```

---
## 🤝 Contributing

Contributions are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🛠️ Development

Remora-Fin uses [uv](https://github.com/astral-sh/uv) for high-performance dependency management and multi-version Python testing.

### Testing across Python versions

You can easily run the test suite against different Python versions without manual installation:

```bash
# Test with Python 3.11
uv run --python 3.11 pytest tests/

# Test with Python 3.12 (Default)
uv run --python 3.12 pytest tests/

# Test with Python 3.13
uv run --python 3.13 pytest tests/
```

If a specific Python version is not found on your system, `uv` will automatically download and manage it for you.

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.