# 🍯 HoneyHive Cookbooks

**A comprehensive collection of integration examples for AI observability and evaluation with HoneyHive**

[Website](https://honeyhive.ai) • [Documentation](https://docs.honeyhive.ai) • [Community](https://discord.com/invite/vqctGpqA97) • [Blog](https://www.honeyhive.ai/blog)

## 📋 Overview

This repository contains a collection of cookbooks and examples for integrating various tools, frameworks, and services with HoneyHive for comprehensive AI observability and evaluation. Each cookbook provides practical guidance and code examples to help you implement effective tracing and evaluation for your AI systems.

## 🧰 Available Cookbooks

### 🔍 RAG (Retrieval-Augmented Generation)

| Cookbook | Description |
|----------|-------------|
| [qdrant-cookbook](./qdrant-cookbook) | Integration with Qdrant vector database for RAG pipelines |
| [zilliz-honeyhive](./zilliz-honeyhive) | Integration with Zilliz (Milvus) vector database |
| [rag-chromadb-cookbook-python](./rag-chromadb-cookbook-python) | Integration with ChromaDB for RAG pipelines |

### 🔗 Framework Integrations

| Cookbook | Description |
|----------|-------------|
| [langchain-python](./langchain-python) | Integration examples with LangChain in Python |
| [langchain-typescript](./langchain-typescript) | Integration examples with LangChain in TypeScript |
| [llamaindex-python](./llamaindex-python) | Integration with LlamaIndex in Python |
| [nextjs-quickstart](./nextjs-quickstart) | Basic Next.js integration with HoneyHive |
| [nextjs-quickstart-with-sentry](./nextjs-quickstart-with-sentry) | Next.js integration with both HoneyHive and Sentry |

### 💼 Domain-Specific Evaluations

| Cookbook | Description |
|----------|-------------|
| [claims-summarizer-python](./claims-summarizer-python) | Process and summarize claims data using Python |
| [claims-transcript-summarizer-js](./claims-transcript-summarizer-js) | Process and summarize transcript data for claims |
| [text2sql-evals](./text2sql-evals) | Evaluate Text-to-SQL model performance |

### 🎓 Academic Benchmarks

| Cookbook | Description |
|----------|-------------|
| [putnam-evaluation-python](./putnam-evaluation-python) | Evaluation examples using Putnam dataset |
| [putnam-evaluation-async-python](./putnam-evaluation-async-python) | Asynchronous evaluation with Putnam dataset |

### 📚 Getting Started & Learning

| Cookbook | Description |
|----------|-------------|
| [observability-tutorial-python](./observability-tutorial-python) | Basic observability tutorial in Python |
| [observability-tutorial-ts](./observability-tutorial-ts) | Basic observability tutorial in TypeScript |

### 🤖 LLM Provider Integrations

| Cookbook | Description |
|----------|-------------|
| [mistral-cookbook](./mistral-cookbook) | Integration with Mistral AI's models and API |

## 🚀 Getting Started

Each cookbook contains its own README with specific instructions. To get started:

1. **HoneyHive Account**: Sign up at [honeyhive.ai](https://honeyhive.ai) and get your API key
2. **Clone the Repository**:
   ```bash
   git clone https://github.com/honeyhiveai/cookbook.git
   cd cookbook
   ```
3. **Choose a Cookbook**: Navigate to the cookbook that matches your use case and follow its README

## 🛠️ Requirements

Depending on the cookbook you're using, you'll need:

- **Python 3.8+** for Python examples
- **Node.js** for JavaScript and TypeScript examples
- **Jupyter Notebook** support for notebook examples
- **API Keys** for relevant services (HoneyHive, OpenAI, etc.)

## 👥 Contributing

We welcome contributions from the community! To contribute:

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/new-example`
3. Commit your changes: `git commit -m 'Add a new example'`
4. Push to the branch: `git push origin feature/new-example`
5. Submit a pull request

## 🤝 Support

For questions or issues:
- [Open an issue](https://github.com/honeyhiveai/cookbook/issues/new)
- Contact the HoneyHive team at support@honeyhive.ai
- Visit [honeyhive.ai](https://honeyhive.ai)

---

Powered by **HoneyHive** - Modern AI Observability & Evaluation