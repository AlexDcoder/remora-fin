# 🦈 Remora-Fin: AWS FinOps CLI

**Remora** é um kit de ferramentas FinOps de alto desempenho e leve para AWS. Assim como as rêmoras se fixam em tubarões para mantê-los limpos, esta CLI se anexa ao seu ambiente AWS para limpar custos, analisar gastos e detectar anomalias.

---

## 🚀 Funcionalidades Principais

* **📈 Gráficos Vetoriais:** Visualizações nativas em PDF (Barras e Linhas) sem dependências externas.
* **📂 Multi-formato:** Exportação para humanos (PDF, MD, Table) ou máquinas (JSON, Parquet, CSV).
* **🔍 Inteligência de Anomalias:** Identifica picos inesperados usando algoritmos do AWS Cost Explorer.
* **🔮 Análise Preditiva:** Previsão de gastos integrada para evitar sustos no fechamento da fatura.
* **🖥️ Terminal UI:** Dashboard interativo (TUI) para monitoramento em tempo real.

---

## 🔐 Configuração de Permissões (IAM)

Antes de usar a Remora, garanta que sua identidade AWS possui as permissões mínimas de **leitura**.

| Ação | Propósito |
| --- | --- |
| `ce:GetCostAndUsage` | Relatórios de custos e tendências. |
| `ce:GetAnomalies` | Detecção de picos de gastos e acesso a monitores. |
| `ce:GetCostForecast` | Projeções nativas de gastos. |
| `sts:GetCallerIdentity` | Identificação de conta e usuário atual. |
| `tagging:GetResources` | Verificação de conformidade de tags de recursos. |
| `organizations:ListAccounts` | Listagem de contas em ambientes multi-account. |

---

## 📊 Formatos de Exportação

O comando `report` suporta diversos formatos para visualização ou ingestão de dados:

| Formato | Argumento | Extensão | Descrição |
| --- | --- | --- | --- |
| **PDF** | `pdf` | `.pdf` | Documento profissional com gráficos vetoriais. |
| **Table** | `table` | `N/A` | Saída estilizada para o terminal (Padrão). |
| **Markdown** | `markdown` | `.md` | Tabelas formatadas para documentação/GitHub. |
| **JSON** | `json` | `.json` | Dados estruturados para integrações. |
| **CSV** | `csv` | `.csv` | Formato padrão para Excel/Spreadsheets. |
| **Parquet** | `parquet` | `.parquet` | Alta performance para análise de Big Data. |

---

## 🛠️ Comandos & Uso

### 📊 `report`

Gera relatórios abrangentes de custo e uso.

```bash
# Exemplo: Breakdown mensal em PDF dos últimos 30 dias
remora report --type breakdown --format pdf --output mensal.pdf

# Exemplo: Relatório de conta filtrado por serviço EC2
remora report --type account --service EC2 --format csv

```

| Argumento | Atalho | Padrão | Descrição |
| --- | --- | --- | --- |
| `--type` | `-t` | `breakdown` | Tipo: breakdown, trend, account. |
| `--days` | `-d` | `30` | Período de retrocesso em dias. |
| `--metric` | `-m` | `UnblendedCost` | Métrica (Blended, Amortized, Usage). |
| `--group-by` |  | `None` | Agrupar por: SERVICE, REGION, LINKED_ACCOUNT. |
| `--profile` | `-p` | `default` | Perfil do AWS CLI. |

---

### ⚠️ `anomalies`

Detecta e analisa desvios de custo no ambiente.

```bash
# Verifica anomalias de alta severidade nos últimos 60 dias
remora anomalies --days 60 --severity high --detail

```

---

### 🔮 `forecast`

Projeta gastos futuros com base em padrões históricos.

```bash
# Projeção para os próximos 30 dias com análise de cenários "what-if"
remora forecast --days 30 --scenarios --granularity MONTHLY

```

---

### 🖥️ `dashboard`

Inicia a Interface de Terminal Interativa (TUI).

```bash
# Dashboard em tempo real com tema claro
remora dashboard --theme light --days 60

```

---

### 🔑 `login`

Valida e configura o acesso ao ambiente AWS.

```bash
# Realiza um teste de conectividade e permissões
remora login --test

# Configuração interativa
remora login --configure

```

---

## 📝 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.

---