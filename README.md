# 🦈 Remora-Fin: High-Performance AWS FinOps CLI

**Remora** is a lightweight, high-performance FinOps toolkit for AWS. Built with Polars and Textual, it attaches to your AWS environment to analyze spending, detect anomalies, and export professional-grade reports.

---

## 🚀 Key Features

* **📈 Vector Graphics:** Native PDF visualizations (Bars & Lines) with zero external dependencies.
* **📂 High-Speed Analysis:** Powered by **Polars** for near-instant processing of large billing datasets.
* **🔍 Anomaly Intelligence:** Identify unexpected cost spikes using AWS Cost Explorer algorithms.
* **🔮 Predictive Analysis:** Integrated spending forecasts to avoid end-of-month surprises.
* **🖥️ Terminal UI:** Interactive dashboard (TUI) for real-time cost monitoring.
* **🔒 Privacy First:** All data processing happens locally on your machine. Remora never sends your billing data to external servers.

---

## 📦 Installation

Install Remora using `pip` or `uv`:

```bash
# Using uv (Recommended)
uv tool install remora

# Using pip
pip install remora

```

---

## 🛠️ Commands & Usage

### 📊 `report`

Generate comprehensive cost and usage reports.

| Argument | Shortcut | Default | Description |
| --- | --- | --- | --- |
| `--type` | `-t` | `breakdown` | Report type: `breakdown`, `trend`, `account`. |
| `--format` | `-f` | `table` | Output: `pdf`, `json`, `csv`, `parquet`, `markdown`. |
| `--days` | `-d` | `30` | Lookback period in days. |
| `--group-by` |  | `SERVICE` | Agrupar por: `SERVICE`, `REGION`, `LINKED_ACCOUNT`. |

```bash
# Generate a monthly breakdown in PDF for the last 30 days
remora report --type breakdown --format pdf --output monthly_report.pdf

# Get a CSV report filtered by EC2 service
remora report --type account --service EC2 --format csv

```

### 🖥️ `dashboard`

Launch the interactive Terminal User Interface.

```bash
remora dashboard --days 60

```

### 🔐 `login`

Configure and test AWS credentials.

```bash
# Configure interactively
remora login --configure

# Test existing credentials
remora login --test
```

### 👤 `profile`

View current remora configuration and AWS session identity.

```bash
remora profile
```

---

## 🔐 IAM Permissions

Remora requires **read-only** access to AWS Cost Explorer and Organizations. Ensure your IAM identity has the following permissions:

| Action | Purpose |
| --- | --- |
| `ce:GetCostAndUsage` | Cost reports and trends. |
| `ce:GetAnomalies` | Cost spike detection and monitor access. |
| `ce:GetCostForecast` | Native spend projections. |
| `sts:GetCallerIdentity` | Current account and user identification. |
| `organizations:ListAccounts` | Multi-account environment support. |

---

## 🌍 Multi-Cloud Support (Coming Soon)

We are planning to expand Remora to support Azure and GCP. See our [Multi-Cloud Roadmap](MULTI_CLOUD.md) for more details.

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