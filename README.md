# Remora-Fin: AWS FinOps (CLI)

remora is a lightweight, high-performance FinOps toolkit for AWS. Just as the remora fish hitches a ride on larger sharks to keep them clean, this library attaches to your AWS environment to clean up costs, analyze spend, and detect anomalies.

---

## Permissions and IAM Configuration

Before using Remora, ensure your AWS identity (User or Role) has the following minimum permissions. Remora only requires read-only access to Cost Explorer and Identity services.

| Action | Purpose |
| :--- | :--- |
| ce:GetCostAndUsage | Required for cost reports and trends. |
| ce:GetAnomalies | Required for detecting spend spikes. |
| ce:GetAnomalyMonitors | Required to list active cost monitors. |
| ce:GetCostForecast | Required for native spend projections. |
| sts:GetCallerIdentity | Required to identify the user and account. |
| tagging:GetResources | Required to check resource tag compliance. |
| organizations:ListAccounts | Required to list accounts in the organization. |

---

## Supported Export Formats

The `report` command supports the following formats for saving or viewing data.

| Format | Argument | Extension | Description |
| :--- | :--- | :--- | :--- |
| Table | table | N/A | Styled terminal output (Default). |
| PDF | pdf | .pdf | Professional document with vector bar/line charts. |
| Markdown | markdown | .md | Documentation-ready text with Markdown tables. |
| JSON | json | .json | Raw machine-readable data for integrations. |
| CSV | csv | .csv | Standard spreadsheet format. |
| Parquet | parquet | .parquet | High-performance columnar storage for big data. |

---

## Commands & Usage

### report
Generate comprehensive cost and usage reports in multiple formats.

| Argument | Shorthand | Description | Default |
| :--- | :--- | :--- | :--- |
| --type | -t | Type of report: breakdown, trend, account | breakdown |
| --format | -f | Output format (see Supported Formats table above) | table |
| --output | -o | File path to save the report (required for PDF/Parquet) | None |
| --days | -d | Number of days to look back | 30 |
| --metric | -m | AWS Cost metric: UnblendedCost, AmortizedCost, BlendedCost, NetUnblendedCost | UnblendedCost |
| --profile | -p | AWS CLI profile name | default |
| --region | -r | AWS region | us-east-1 |

**Example:**
`remora report --type breakdown --format pdf --output monthly_spend.pdf --days 30`

---

### anomalies
Detect and analyze cost spikes in your AWS environment.

| Argument | Shorthand | Description | Default |
| :--- | :--- | :--- | :--- |
| --days | -d | Number of days to check for anomalies | 60 |
| --format | -f | Output format: table, json | table |
| --profile | -p | AWS CLI profile name | default |

**Example:**
`remora anomalies --days 14 --format table`

---

### forecast
Predict future spend based on historical patterns.

| Argument | Shorthand | Description | Default |
| :--- | :--- | :--- | :--- |
| --days | -d | Number of days to forecast into the future | 30 |
| --metric | -m | Metric to forecast | UnblendedCost |
| --profile | -p | AWS CLI profile name | default |

**Example:**
`remora forecast --days 30 --profile production`

---

### dashboard
Launch an interactive Terminal User Interface (TUI) for real-time cost monitoring.

| Argument | Shorthand | Description | Default |
| :--- | :--- | :--- | :--- |
| --theme | None | UI theme: dark, light | dark |
| --profile | -p | AWS CLI profile name | default |

**Example:**
`remora dashboard --theme dark`

---

### login
Authenticate and verify AWS credentials for use with Remora.

| Argument | Shorthand | Description | Default |
| :--- | :--- | :--- | :--- |
| --test | None | Perform a connectivity test after authentication | False |
| --profile | -p | AWS CLI profile name | default |

**Example:**
`remora login --profile dev-account --test`

---

## Features
* **Vector Charts:** Native PDF visualizations (Bar charts for usage, Line charts for cost trends) without external dependencies.
* **Multi-Format:** Export data for humans (PDF, Markdown, Table) or machines (JSON, Parquet, CSV).
* **Anomaly Intelligence:** Identifies unexpected spend spikes using AWS Cost Explorer algorithms.
* **Predictive Analysis:** Built-in forecasting to prevent end-of-month bill shock.
