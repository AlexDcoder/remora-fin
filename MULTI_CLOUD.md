# 🌍 Planejamento para Suporte Multi-Cloud no Remora-Fin

Este documento descreve a estratégia e o roteiro para expandir o **Remora-Fin** além da AWS, integrando suporte para outros provedores de nuvem como **Microsoft Azure** e **Google Cloud Platform (GCP)**.

---

## 🎯 Objetivo

Transformar o Remora-Fin em uma ferramenta de FinOps agnóstica de nuvem, permitindo que usuários gerenciem custos e visualizem métricas de múltiplos provedores através de uma interface unificada.

---

## 🏗️ Mudanças Arquiteturais

Atualmente, o projeto é fortemente acoplado ao SDK da AWS (`boto3`). Para suportar outros provedores, implementaremos os seguintes padrões:

### 1. Camada de Abstração de Provedor
Criaremos interfaces base (`Abstract Base Classes`) para os principais serviços:
- `BaseCostService`: Métodos comuns para consulta de custos e uso.
- `BaseForecastService`: Interface para previsões de gastos.
- `BaseAnomalyService`: Detecção de anomalias cross-cloud.

### 2. Fábrica de Sessões (Cloud Provider Factory)
O `AWSSession` atual será evoluído para um sistema de gestão de sessões dinâmico que identifica o provedor ativo com base na configuração do usuário.

### 3. Esquemas de Dados Padronizados
Utilizaremos os schemas em `remora_fin.schemas` para garantir que, independentemente da origem (AWS, Azure, GCP), os dados sejam processados de forma idêntica pelo motor de análise **Polars**.

---

## 📚 Bibliotecas Recomendadas

Para cada novo provedor, utilizaremos os SDKs oficiais para garantir compatibilidade e acesso total às APIs de faturamento:

### 🔵 Microsoft Azure
- **`azure-mgmt-costmanagement`**: Para consultas detalhadas de custos e exportação de dados.
- **`azure-identity`**: Autenticação moderna via Azure CLI, Managed Identity ou Service Principals.
- **`azure-mgmt-consumption`**: Detalhes de consumo por recurso.

### 🟡 Google Cloud Platform (GCP)
- **`google-cloud-billing`**: Gerenciamento e visualização de contas de faturamento.
- **`google-cloud-monitoring`**: Métricas de uso correlacionadas a custo.
- **`google-cloud-storage`**: Para processar exportações de faturamento em larga escala (BigQuery/GCS).

### ⚙️ Utilitários
- **`libcloud`**: Pode ser explorado para abstrações básicas de computação (EC2/VMs), embora para FinOps os SDKs nativos sejam preferíveis devido à complexidade das APIs de Billing.

---

## 🗺️ Roteiro de Implementação (Roadmap)

### Fase 1: Refatoração e Abstração (Curto Prazo)
- [ ] Isolar a lógica atual da AWS em `remora_fin.services.aws`.
- [ ] Criar as interfaces abstratas `BaseCostService` e `BaseForecastService`.
- [ ] Implementar o `AWSService` como a primeira implementação concreta dessas interfaces.

### Fase 2: Integração Azure (Médio Prazo)
- [ ] Implementar `AzureSession` para gestão de credenciais.
- [ ] Desenvolver `AzureCostService` utilizando a API de Cost Management.
- [ ] Adaptar o comando `remora-fin report` para aceitar a flag `--provider azure`.

### Fase 3: Integração GCP (Médio Prazo)
- [ ] Implementar `GCPSession` e autenticação via ADC (Application Default Credentials).
- [ ] Desenvolver `GCPCostService` integrando com exportações do BigQuery ou Cloud Billing API.

### Fase 4: Dashboard Unificado (Longo Prazo)
- [ ] Evoluir o `remora-fin dashboard` (TUI) para exibir uma visão consolidada de todos os provedores configurados.
- [ ] Suporte a "Unit Economics" entre nuvens (ex: custo por transação global).

---

## 🤝 Como Contribuir
Se você tem experiência com as APIs de faturamento do Azure ou GCP, sinta-se à vontade para abrir uma issue ou propor uma RFC para as interfaces de abstração.
