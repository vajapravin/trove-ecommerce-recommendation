"""Generate a dataset of 1,020 realistic courses with real Unsplash images.

Generates `app/starter_catalog.json` containing 1,020 diverse, realistic products across 12 tech categories.
"""
from __future__ import annotations

import json
import os
import random

CATEGORIES_IMAGES = {
    "AI & Agents": [
        "https://images.unsplash.com/photo-1618401471353-b98afee0b2eb?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1509966756634-9c23dd6e6815?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1677442136019-21780efad99a?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=600&auto=format&fit=crop",
    ],
    "Machine Learning": [
        "https://images.unsplash.com/photo-1555949963-ff9fe0c870eb?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1527474305487-b87b222841cc?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=600&auto=format&fit=crop",
    ],
    "Data Engineering": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?w=600&auto=format&fit=crop",
    ],
    "Cloud & DevOps": [
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=600&auto=format&fit=crop",
    ],
    "Backend": [
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1587620962725-abab7fe55159?w=600&auto=format&fit=crop",
    ],
    "Frontend": [
        "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1547658719-da2b51169166?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1581291518633-83b4ebd1d83e?w=600&auto=format&fit=crop",
    ],
    "Mobile": [
        "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1526498460520-4c246339dccb?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1551650975-87deedd944c3?w=600&auto=format&fit=crop",
    ],
    "Cybersecurity": [
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1563986768494-4dee2763ff3f?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1510511459019-5dda7724fd87?w=600&auto=format&fit=crop",
    ],
    "System Design": [
        "https://images.unsplash.com/photo-1531403009284-440f080d1e12?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=600&auto=format&fit=crop",
    ],
    "Testing & QA": [
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=600&auto=format&fit=crop",
    ],
    "Interview Prep": [
        "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=600&auto=format&fit=crop",
    ],
    "Web3 & Crypto": [
        "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=600&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1622979135225-d2ba269bc1bd?w=600&auto=format&fit=crop",
    ],
}

TOPICS_PER_CATEGORY = {
    "AI & Agents": [
        "Autonomous Agent Architecture", "LangGraph State Machines", "RAG Vector Retrieval",
        "LLM Tool Use & Function Calling", "Prompt Engineering Mastery", "Multi-Agent Collaboration",
        "AI Alignment & Guardrails", "Fine-Tuning Llama 3 & Open Source LLMs", "AI Software Engineering Copilot",
        "Embedding Search Systems", "Semantic Search Optimization", "Generative AI Agents in Enterprise",
        "ReAct & Reflexion Patterns", "Agent Evaluation Frameworks", "LangChain Production Systems"
    ],
    "Machine Learning": [
        "Deep Learning with PyTorch", "TensorFlow Production Pipelines", "Computer Vision with OpenCV",
        "Natural Language Processing with Transformers", "Reinforcement Learning Fundamentals",
        "Feature Engineering & Selection", "ML Model Evaluation & Monitoring", "MLOps with MLflow",
        "Time Series Forecasting", "Gradient Boosting with XGBoost & LightGBM", "Unsupervised Clustering",
        "Neural Network Architecture Design", "Edge AI & TensorRT Deployment", "Bayesian Optimization"
    ],
    "Data Engineering": [
        "Data Engineering with dbt & Snowflake", "Apache Spark Big Data Processing", "Real-Time Streaming with Kafka",
        "Modern Data Warehousing", "Data Pipeline Orchestration with Airflow", "Lakehouse Architecture with Iceberg",
        "ETL vs ELT Mastery", "SQL Query Optimization at Scale", "Data Quality & Observability with Monte Carlo",
        "BigQuery Analytics & Partitioning", "Data Mesh Design", "CDC & Event-Driven Ingestion"
    ],
    "Cloud & DevOps": [
        "Kubernetes Administration & Helm", "Terraform Infrastructure as Code", "AWS Cloud Solutions Architect",
        "Docker Containerization Deep Dive", "CI/CD Automation with GitHub Actions", "Site Reliability Engineering (SRE)",
        "GCP Cloud Native Architecture", "Azure DevOps & Pipeline Management", "Cloud Security & Compliance",
        "Service Mesh with Istio & Envoy", "Prometheus & Grafana Observability", "Serverless Architecture with AWS Lambda"
    ],
    "Backend": [
        "Production FastAPI Masterclass", "Node.js & Express Microservices", "Go Concurrent Backend Systems",
        "Django REST Framework & PostgreSQL", "Spring Boot Enterprise Architecture", "GraphQL API Design with Apollo",
        "gRPC & Protocol Buffers", "Distributed Caching with Redis", "Database Sharding & Replication",
        "Event-Driven Microservices with RabbitMQ", "Rust High-Performance Systems", "Authentication & JWT Security"
    ],
    "Frontend": [
        "Next.js App Router Mastery", "React 19 Server Components", "TypeScript Advanced Types & Patterns",
        "Vue 3 & Pinia State Management", "Modern CSS & Tailwind UI Design", "Web Performance & Core Web Vitals",
        "Angular Enterprise Applications", "Micro-Frontends Architecture", "Web Workers & Offline PWA",
        "State Machines with XState", "Component Testing with Storybook", "Responsive Web Accessibility (a11y)"
    ],
    "Mobile": [
        "Flutter Cross-Platform Mobile Apps", "React Native & Expo Architecture", "iOS Development with Swift & SwiftUI",
        "Android App Engineering with Kotlin", "Mobile UI/UX Design System", "Offline Sync & Realm Mobile DB",
        "Mobile CI/CD with Fastlane", "Native C++ Interop on Mobile", "ARKit & Augmented Reality Apps",
        "Mobile Security & Secure Storage"
    ],
    "Cybersecurity": [
        "Ethical Hacking & Penetration Testing", "Web Application Vulnerability Assessment (OWASP)",
        "Network Defense & Wireshark", "Cloud Threat Detection & Incident Response", "Applied Cryptography & TLS",
        "DevSecOps & Code Security Auditing", "Zero Trust Architecture", "SOC Analysis & SIEM Log Monitoring",
        "Malware Reverse Engineering", "IAM Identity & Access Governance"
    ],
    "System Design": [
        "System Design Interview Preparation", "Distributed Systems Patterns", "Designing Scalable Web Applications",
        "Consistency Models & CAP Theorem", "API Gateway Architecture", "High Availability & Disaster Recovery",
        "Domain-Driven Design (DDD)", "Microservices Resiliency & Circuit Breakers", "Load Balancing Strategies"
    ],
    "Testing & QA": [
        "Playwright End-to-End Automation", "Pytest Advanced Test Framework", "Selenium Web Automation with Python",
        "API Automation Testing with Postman & Bruno", "Contract Testing with Pact", "Performance Testing with Locust & k6",
        "TDD Test Driven Development", "Behavior Driven Development (BDD) with Cucumber"
    ],
    "Interview Prep": [
        "Data Structures & Algorithms in Python", "Cracking the Coding Interview Bootcamp",
        "LeetCode Patterns & Problem Solving", "Behavioral Interview & Leadership Tactics",
        "Object-Oriented Design Interviews", "Mock Technical Interviews & Resume Review"
    ],
    "Web3 & Crypto": [
        "Solidity Smart Contract Engineering", "Ethereum DApp Development with Hardhat",
        "DeFi Protocol Architecture", "Rust Smart Contracts on Solana", "Zero-Knowledge Proofs & zkSNARKs",
        "NFT Smart Contracts & IPFS", "Web3 Security & Smart Contract Auditing"
    ],
}

LEVELS = ["beginner", "intermediate", "advanced"]


def generate_1000_products() -> list[dict]:
    random.seed(42)  # Deterministic seed
    products = []
    pid = 1

    for category, topics in TOPICS_PER_CATEGORY.items():
        images = CATEGORIES_IMAGES[category]

        # Generate ~85 products per category to reach > 1000 total products
        for i in range(85):
            topic = topics[i % len(topics)]
            level = LEVELS[i % 3]
            img_url = images[i % len(images)]

            variation_prefixes = [
                "Mastering", "Comprehensive Guide to", "Hands-On", "Advanced", "Building",
                "Practical", "Production-Ready", "From Zero to Hero:", "Architecting", "Deep Dive into"
            ]
            prefix = variation_prefixes[i % len(variation_prefixes)]

            title = f"{prefix} {topic}"
            if i >= len(topics):
                title += f" (Part {(i // len(topics)) + 1})"

            desc = (
                f"Master {topic.lower()} with practical projects and expert guidance. "
                f"This course covers core principles, real-world patterns, and production techniques tailored for {level} engineers."
            )

            tags_list = [category.lower().replace(" ", "-"), level, topic.lower().split()[0]]
            tags_str = ",".join(tags_list)
            price = float(random.choice([29, 39, 49, 59, 69, 79, 89, 99]))

            products.append({
                "title": title,
                "description": desc,
                "category": category,
                "level": level,
                "price": price,
                "tags": tags_str,
                "image_url": img_url,
            })
            pid += 1

    return products


if __name__ == "__main__":
    prods = generate_1000_products()
    out_path = os.path.join(os.path.dirname(__file__), "..", "starter_catalog.json")
    out_path = os.path.abspath(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(prods, f, indent=2)
    print(f"Generated {len(prods)} products saved to {out_path}")
