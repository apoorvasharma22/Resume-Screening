from __future__ import annotations

import re
from collections import Counter

_RAW = {
    "Programming Language": """
Python|python3
Java
JavaScript|ecmascript|es6
TypeScript
C++|cpp
C#|csharp|c sharp
C|c programming|c language
Go|golang|go lang
Rust
Kotlin
Swift
PHP
Ruby
Scala
R|r programming|r language|rstudio
MATLAB
Bash|shell scripting|bash scripting|shell script
SQL|t-sql|pl/sql|plsql
Dart
Perl
""",
    "Frontend": """
React|react.js|reactjs
Next.js|nextjs
Angular|angularjs|angular.js
Vue.js|vue|vuejs
Svelte
HTML|html5
CSS|css3
Sass|scss
Tailwind CSS|tailwind|tailwindcss
Bootstrap
Redux|redux toolkit
Webpack
Vite
jQuery
GraphQL
Storybook
Responsive Design|responsive web design
Accessibility|wcag|a11y
Web Performance|core web vitals
""",
    "Backend": """
Django|django rest framework|drf
Flask
FastAPI
Spring Boot|springboot
Spring|spring framework
Node.js|nodejs
Express.js|expressjs
NestJS|nest.js
.NET|dotnet|.net core|asp.net|asp.net core
Laravel
Ruby on Rails
Microservices|microservice architecture
REST APIs|rest api|restful api|restful apis|restful|rest services
gRPC
Celery
Kafka|apache kafka
RabbitMQ
Hibernate
WebSockets|websocket
Caching
API Design
Distributed Systems
System Design
Design Patterns
OOP|object oriented programming|object oriented design
Performance Optimization|performance tuning
OAuth|oauth2|oauth 2.0
JWT|json web tokens|json web token
""",
    "Database": """
PostgreSQL|postgres|postgre sql
MySQL
SQL Server|mssql|microsoft sql server
Oracle|oracle db|oracle database
MongoDB|mongo db|mongo
Redis
Elasticsearch|elastic search
Cassandra
DynamoDB
SQLite
Snowflake
BigQuery
Redshift
SQLAlchemy
NoSQL
MariaDB
Neo4j
Vector Databases|vector database|vector db|pgvector
FAISS
Pinecone
Database Design|schema design|data modeling|data modelling
""",
    "Cloud & DevOps": """
AWS|amazon web services
Azure|microsoft azure
GCP|google cloud|google cloud platform
Docker
Kubernetes|k8s
Terraform
Ansible
Jenkins
GitHub Actions
GitLab CI|gitlab ci/cd
CI/CD|cicd|continuous integration|continuous delivery|continuous deployment
Git
GitHub
Linux|unix
Nginx
Prometheus
Grafana
Helm
Serverless|aws lambda|lambda functions
EC2
Amazon S3
EKS
CloudFormation
ELK Stack|elk
Datadog
Infrastructure as Code|iac
Site Reliability|sre
Monitoring|observability
Networking|tcp/ip
Airflow|apache airflow
""",
    "Data & ML": """
Machine Learning
Deep Learning
NLP|natural language processing
Computer Vision
Pandas
NumPy
SciPy
scikit-learn|sklearn
TensorFlow
PyTorch
Keras
XGBoost|lightgbm
LLMs|llm|large language models|large language model
Generative AI|genai|gen ai
RAG|retrieval augmented generation
LangChain
Hugging Face|huggingface
OpenAI API|openai
Prompt Engineering
Statistics|statistical analysis|statistical modeling|statistical modelling
Data Analysis|data analytics
Data Visualization|data visualisation
Feature Engineering
A/B Testing|ab testing|a/b tests
Time Series|time series forecasting
MLOps|ml ops
MLflow
Tableau
Power BI|powerbi
Looker
Excel|microsoft excel|ms excel
ETL|etl pipelines|data pipelines|elt
Data Warehousing|data warehouse
Jupyter|jupyter notebook
Matplotlib
Seaborn
Reinforcement Learning
Recommendation Systems|recommender systems|recommendation engines
OpenCV
Spark|apache spark|pyspark
Hadoop
dbt
Data Structures|data structures and algorithms|dsa
Hypothesis Testing
Model Deployment
""",
    "Testing": """
Pytest|py.test
Unit Testing|unit tests
Selenium
Cypress
Jest
JUnit
Test Automation|automated testing
Postman
TDD|test driven development
Playwright
Integration Testing
""",
    "Mobile": """
Android
iOS
React Native
Flutter
""",
    "Practices & Tools": """
Agile
Scrum
Kanban
Jira
Confluence
Code Review|code reviews
Figma
UI/UX|ux design|user experience
Project Management
Cybersecurity|information security
OWASP
""",
    "Soft Skill": """
Leadership|team leadership
Communication|communication skills
Mentoring|mentorship
Stakeholder Management
Problem Solving
""",
    "Business": """
Recruitment|talent acquisition
Payroll
Onboarding
Employee Engagement
HRIS
Salesforce
SAP
SEO
Content Marketing
Financial Modeling|financial modelling
""",
}

RELATED_GROUPS = [
    {"MySQL", "PostgreSQL", "SQL Server", "Oracle", "MariaDB", "SQLite"},
    {"AWS", "Azure", "GCP"},
    {"React", "Angular", "Vue.js", "Svelte", "Next.js"},
    {"TensorFlow", "PyTorch", "Keras"},
    {"Django", "Flask", "FastAPI"},
    {"Jenkins", "GitHub Actions", "GitLab CI", "CI/CD"},
    {"Kubernetes", "Docker", "Helm"},
    {"Kafka", "RabbitMQ"},
    {"Redis", "MongoDB", "DynamoDB", "Cassandra", "NoSQL"},
    {"Terraform", "CloudFormation", "Ansible", "Infrastructure as Code"},
    {"Tableau", "Power BI", "Looker"},
    {"Java", "Kotlin", "Scala"},
    {"Spring Boot", "Spring", "Hibernate"},
    {"Jest", "Cypress", "Playwright", "Selenium", "Pytest", "JUnit"},
    {"Snowflake", "BigQuery", "Redshift", "Data Warehousing"},
    {"Prometheus", "Grafana", "Datadog", "Monitoring", "ELK Stack"},
    {"LangChain", "RAG", "LLMs", "Generative AI", "OpenAI API", "Hugging Face", "Prompt Engineering"},
    {"Machine Learning", "Deep Learning", "NLP", "Computer Vision", "scikit-learn"},
    {"Spark", "Hadoop", "Airflow", "ETL", "dbt"},
    {"Node.js", "Express.js", "NestJS"},
    {"Android", "iOS", "React Native", "Flutter"},
]

CATEGORY: dict[str, str] = {}
ALIAS_TO_CANON: dict[str, str] = {}

for _cat, _block in _RAW.items():
    for _line in _block.strip().splitlines():
        _line = _line.strip()
        if not _line:
            continue
        _canon, *_aliases = _line.split("|")
        CATEGORY[_canon] = _cat
        for _a in [_canon, *_aliases]:
            ALIAS_TO_CANON[_a.lower()] = _canon

ALL_SKILLS = sorted(CATEGORY)
_RELATED: dict[str, set[str]] = {}
for _g in RELATED_GROUPS:
    for _s in _g:
        _RELATED.setdefault(_s, set()).update(_g - {_s})

_LEFT = r"(?<![A-Za-z0-9+#])"
_RIGHT = r"(?![A-Za-z0-9+#])"


def _alias_pattern(alias: str) -> str:
    parts = [re.escape(p) for p in re.split(r"[ \-]+", alias) if p]
    return r"[\s\-]+".join(parts)


AMBIGUOUS_PLAIN = {"go", "c", "r", "excel", "oracle", "spring"}

_ALIASES_SORTED = sorted((a for a in ALIAS_TO_CANON if a not in AMBIGUOUS_PLAIN), key=len, reverse=True)
_MASTER_RE = re.compile(_LEFT + "(" + "|".join(_alias_pattern(a) for a in _ALIASES_SORTED) + ")" + _RIGHT, re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"[\s\-]+", " ", s.strip().lower())


_NORM_ALIAS_TO_CANON = {_norm(k): v for k, v in ALIAS_TO_CANON.items()}


def canonical_skill(raw: str) -> str:
    raw = raw.strip()
    return _NORM_ALIAS_TO_CANON.get(_norm(raw), raw)


def skill_category(skill: str) -> str:
    return CATEGORY.get(canonical_skill(skill), "Other")


def related_skills(skill: str) -> set[str]:
    return _RELATED.get(canonical_skill(skill), set())


def extract_skills(text: str) -> list[str]:
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for m in _MASTER_RE.finditer(text):
        canon = _NORM_ALIAS_TO_CANON[_norm(m.group(1))]
        counts[canon] += 1
        first_seen.setdefault(canon, m.start())
    return sorted(counts, key=lambda s: (-counts[s], first_seen[s]))


def find_skills(text: str) -> list[tuple[str, int, int]]:
    return [(_NORM_ALIAS_TO_CANON[_norm(m.group(1))], m.start(), m.end()) for m in _MASTER_RE.finditer(text)]


def text_mentions(skill: str, text: str) -> bool:
    canon = canonical_skill(skill)
    names = {a for a, c in ALIAS_TO_CANON.items() if c == canon and a not in AMBIGUOUS_PLAIN}
    if canon.lower() not in AMBIGUOUS_PLAIN:
        names.add(canon.lower())
    if not names:
        return False
    pattern = _LEFT + "(?:" + "|".join(_alias_pattern(n) for n in sorted(names, key=len, reverse=True)) + ")" + _RIGHT
    return re.search(pattern, text, re.IGNORECASE) is not None

