# 🦈 Remora-Fin: High-Performance AWS FinOps CLI

**Remora-Fin** is a lightweight, high-performance FinOps toolkit for AWS. Built with Polars and Textual, it attaches to your AWS environment to analyze spending, detect anomalies, and export professional-grade reports.

---

## 🚀 Key Features

* **📈 Vector Graphics:** Native PDF visualizations (Bars & Lines) with zero external dependencies.
* **📂 High-Speed Analysis:** Powered by **Polars** for near-instant processing of large billing datasets.
* **🔍 Anomaly Intelligence:** Identify unexpected cost spikes using AWS Cost Explorer algorithms.
* **🔮 Predictive Analysis:** Integrated spending forecasts to avoid end-of-month surprises.
* **🖥️ Terminal UI:** Interactive dashboard (TUI) for real-time cost monitoring.
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

## 🛠️ Commands & Usage

### 📊 `report`

Generate comprehensive cost and usage reports.

| Argument | Shortcut | Type / Choices | Default | Description |
| --- | --- | --- | --- | --- |
| `--type` | `-t` | `breakdown`, `trend`, `account` | `breakdown` | Report type. |
| `--format` | `-f` | `pdf`, `table`, `json`, `csv`, `parquet`, `markdown` | `pdf` | Output format. |
| `--days` | `-d` | `int` | `30` | Lookback period in days. |
| `--start` | | `YYYY-MM-DD` | | Start date. |
| `--end` | | `YYYY-MM-DD` | | End date. |
| `--metric` | | `UnblendedCost`, `BlendedCost`, `NetUnblendedCost`, `AmortizedCost`, `UsageQuantity` | `UnblendedCost` | Cost metric. |
| `--group-by` | | `SERVICE`, `LINKED_ACCOUNT`, `REGION`, `USAGE_TYPE` | | Group results by dimension. |
| `--service` | `-s` | `string` | | Filter by AWS service. |
| `--output` | `-o` | `path` | | Output file path. |
| `--profile` | `-p` | `string` | | AWS profile name. |
| `--region` | `-r` | `string` | | AWS region. |

```bash
# Generate a monthly breakdown in PDF for the last 30 days
remora-fin report --type breakdown --format pdf --output monthly_report.pdf

# Get a CSV report filtered by EC2 service
remora-fin report --type account --service EC2 --format csv
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

## 🔐 IAM Permissions

Remora-Fin requires **read-only** access to AWS Cost Explorer and Organizations. Ensure your IAM identity has the following permissions:

| Action | Purpose |
| --- | --- |
| `ce:GetCostAndUsage` | Cost reports and trends. |
| `ce:GetAnomalies` | Cost spike detection and monitor access. |
| `ce:GetCostForecast` | Native spend projections. |
| `sts:GetCallerIdentity` | Current account and user identification. |
| `organizations:ListAccounts` | Multi-account environment support. |

---

## 🌍 Multi-Cloud Support (Coming Soon)

We are planning to expand Remora-Fin to support Azure and GCP. See our [Multi-Cloud Roadmap](MULTI_CLOUD.md) for more details.

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.