"""Payload reduzido do Learn Catalog API e regras de mapeamento para a taxonomia pequena dos testes."""


def catalog_payload():
    return {
        "learningPaths": [
            {"uid": "learn.fabric.lakehouse", "title": "Implement a Lakehouse with Microsoft Fabric",
             "summary": "<p>Build a <b>lakehouse</b> with OneLake and Delta tables.</p>",
             "levels": ["intermediate"], "products": ["fabric"], "duration_in_minutes": 421,
             "url": "https://learn.microsoft.com/en-us/training/paths/implement-lakehouse/?WT.mc_id=api_CatalogApi"},
            {"uid": "learn.foundry.agents", "title": "Develop AI agents on Azure",
             "summary": "Build agentic solutions with Foundry Agent Service.",
             "levels": ["intermediate", "advanced"], "products": ["foundry-agent-service"],
             "duration_in_minutes": 240,
             "url": "https://learn.microsoft.com/en-us/training/paths/develop-ai-agents/"},
            {"uid": "learn.dbx.spark", "title": "Use Apache Spark in Azure Databricks",
             "summary": "Process data with PySpark.", "levels": ["beginner"],
             "products": ["azure-databricks"], "duration_in_minutes": 0,
             "url": "https://learn.microsoft.com/en-us/training/paths/spark-databricks/"},
            {"uid": "learn.excel", "title": "Excel basics", "summary": "Spreadsheets",
             "levels": ["beginner"], "products": ["office-excel"], "duration_in_minutes": 60,
             "url": "https://learn.microsoft.com/en-us/training/paths/excel/"},
            {"uid": "learn.nolevel", "title": "Fabric mystery", "summary": "lakehouse",
             "levels": [], "products": ["fabric"], "url": "https://learn.microsoft.com/x"},
            {"uid": "learn.nourl", "title": "Fabric lakehouse without url", "summary": "lakehouse",
             "levels": ["beginner"], "products": ["fabric"]},
            {"uid": "learn.nulls", "title": "Broken entry", "summary": None, "levels": None,
             "products": None, "url": None},
        ],
        "courses": [
            {"uid": "course.dp-600t00", "title": "Implementing analytics solutions using Microsoft Fabric",
             "summary": "warehouse and lakehouse", "levels": ["intermediate"], "products": ["fabric"],
             "duration_in_hours": 24, "url": "https://learn.microsoft.com/en-us/training/courses/dp-600t00/"},
        ],
        "certifications": [
            {"uid": "certification.fabric-data-engineer-associate",
             "title": "Microsoft Certified: Fabric Data Engineer Associate",
             "subtitle": "<p>Design and deploy data engineering solutions.</p>",
             "levels": ["intermediate"], "exams": [],
             "url": "https://learn.microsoft.com/en-us/credentials/certifications/fabric-data-engineer-associate/?WT.mc_id=api_CatalogApi"},
            {"uid": "certification.multi-agent-ai-solutions-expert",
             "title": "Microsoft Certified: Multi-Agent AI Solutions Expert",
             "subtitle": "Build multi-agent AI solutions.", "levels": ["advanced"],
             "exams": ["exam.ai-500"],
             "url": "https://learn.microsoft.com/en-us/credentials/certifications/multi-agent-ai-solutions-expert/"},
        ],
        "exams": [
            {"uid": "exam.ai-500", "title": "Designing and Implementing Multi-Agent AI Solutions",
             "subtitle": "Multi-agent", "levels": ["advanced"], "products": ["microsoft-foundry"],
             "url": "https://learn.microsoft.com/en-us/credentials/exams/ai-500/"},
        ],
    }


MAPPING_YAML = """
version: 1
tracks:
  fabric: {products: [fabric]}
  foundry: {products: [microsoft-foundry, foundry-agent-service]}
  databricks: {products: [azure-databricks]}
skills:
  fabric.lakehouse: {keywords: [lakehouse, onelake], strong: ["fabric data engineer"]}
  fabric.pipelines: {keywords: [pipeline, pipelines]}
  foundry.agents: {keywords: [agent, agents, agentic, multi agent], strong: ["multi agent ai solutions"]}
  foundry.models: {keywords: [deploy, deployment]}
  databricks.spark: {keywords: [spark, pyspark]}
"""
