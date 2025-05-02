# Softwood Lumber Board Document Checker 🌲

This application processes documents related to the wood industry, extracting key information and finding relationships to a database of propositions.

## Docker Setup

The application is containerized using Docker for easy deployment. The Docker image is optimized to be small (< 1GB) while maintaining all functionality.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### API Keys

The application requires the following API keys:
- LlamaParse API Key
- Gemini API Key
- OpenAI API Key

You need to provide these keys in a `.env` file in the project root directory:

```
LLAMA_CLOUD_API_KEY=your_llama_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
```

### Building and Running the Container

1. **Create your `.env` file with the necessary API keys**

2. **Build and run the container:**

```bash
docker-compose up -d
```

3. **Access the application:**
   
   Open your browser and navigate to [http://localhost:8501](http://localhost:8501)

4. **Stop the container when done:**

```bash
docker-compose down
```

### Container Resource Management

The container is configured with resource limits to prevent excessive resource usage:
- CPU: 1 core
- Memory: 1GB

You can adjust these limits in the `docker-compose.yml` file.

## Troubleshooting

- **Container fails to start**: Check logs with `docker-compose logs`
- **Application errors**: Look for error messages in the Streamlit interface
- **Performance issues**: Consider increasing resource limits in docker-compose.yml

## Docker Image Optimization Notes

This Docker setup uses several techniques to keep the image size small:

1. Multi-stage builds to separate build dependencies from runtime dependencies
2. Python slim base image instead of full image
3. Proper layer caching for efficient rebuilds
4. Inclusion of only necessary files via .dockerignore
5. Virtual environment to keep dependencies isolated
6. Non-root user for improved security

## Updating Dependencies

If you need to update the project dependencies, modify the `requirements.txt` file and rebuild the Docker image:

```bash
docker-compose build --no-cache app
docker-compose up -d
```
