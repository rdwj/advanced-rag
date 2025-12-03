# Contributing to Advanced RAG

Thank you for your interest in contributing to Advanced RAG! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building something together.

## Getting Started

### Prerequisites

- Python 3.11+
- Go 1.21+
- Podman (not Docker)
- Access to OpenAI API or compatible endpoint

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd advanced-rag

# Set up Python environment
cd adaptive-semantic-chunking
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build the Go chunker
cd services/chunker_service
go build -o ../../bin/chunker ./cmd/chunker
```

## Project Structure

```
advanced-rag/
├── adaptive-semantic-chunking/   # Main pipeline
│   ├── services/                 # Microservices
│   └── python/                   # Python modules and scripts
├── retrieval-mcp/                # MCP server for agents
├── databases/                    # Vector store configurations
├── docs/                         # Documentation
└── manifests/                    # OpenShift deployment
```

## Development Guidelines

### Code Style

**Python:**
- 4-space indentation
- Type hints required
- snake_case for functions/variables
- CapWords for classes
- Run `ruff` or `flake8` before committing

**Go:**
- Run `gofmt` on all changes
- Follow standard Go conventions
- Table-driven tests preferred

### Container Standards

- Use `Containerfile`, not `Dockerfile`
- Use Podman, not Docker
- Base images: Red Hat UBI (`registry.redhat.io/ubi9/*`)
- Build with `--platform linux/amd64` for OpenShift compatibility

### Testing

```bash
# Python tests
cd adaptive-semantic-chunking
pytest python/tests/

# Go tests
cd services/chunker_service
go test ./...

# MCP server tests
cd retrieval-mcp
make test
```

### Commit Messages

- Use imperative mood: "Add feature" not "Added feature"
- Keep subject line under 50 characters
- Include context in body when needed
- Reference issues when applicable

Example:
```
Add heading-aware chunking to Go chunker

Implements break_on_headings option that segments text at heading
lines. Heading text is preserved in chunk metadata.

Fixes #123
```

## Pull Request Process

1. **Fork and branch**: Create a feature branch from `main`
2. **Make changes**: Follow the coding guidelines
3. **Test**: Run tests locally and ensure they pass
4. **Document**: Update docs if adding new features
5. **PR description**: Explain what and why, not just how

### PR Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated if needed
- [ ] No secrets or credentials committed
- [ ] Container builds work with `--platform linux/amd64`

## Microservices Development

Each service follows a consistent structure:

```
services/<name>/
├── app.py              # FastAPI entrypoint
├── lib/                # Business logic
├── Containerfile       # Container definition
├── requirements.txt    # Dependencies
├── manifests/          # OpenShift YAML
└── README.md           # Service docs
```

### Adding a New Service

1. Create the directory structure above
2. Implement `/healthz` endpoint
3. Add Containerfile using UBI base image
4. Create OpenShift manifests
5. Document environment variables
6. Add tests

### Building and Testing Services

```bash
# Build locally
podman build --platform linux/amd64 -t my-service:latest -f Containerfile .

# Test locally
python app.py

# Deploy to OpenShift
oc apply -f manifests/ -n advanced-rag
```

## Vector Store Backends

When adding features, ensure compatibility with all three backends:
- Milvus (default)
- PGVector
- Meilisearch

Test with each backend before submitting PRs that touch vector store code.

## Documentation

- Keep docs in `docs/` directory
- Use Markdown format
- Update getting-started.md for new setup steps
- Document new environment variables

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Questions about the codebase

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
