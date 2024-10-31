# Pixel

A powerful and user-friendly Telegram bot that enables users to download audio and video content from YouTube using the robust yt-dlp library. This bot provides a convenient interface for downloading YouTube content directly through Telegram.

## Prerequisites

### Local Development Requirements
- Python3
- FFmpeg
- Docker
- Docker Compose plugin

### Production Requirements
- Docker
- Docker Compose plugin

## Local Development Setup

### 1. Environment Configuration
First, create your environment file by copying the example:
```bash
cp .env.example .env
```

Edit the `.env` file with your actual configuration values:
```bash
vim .env
```

### 2. Start Required Services
Launch the necessary Docker services:
```bash
docker compose up -d
```

### 3. Run the Application
Execute the Python application:
```bash
python3 main.py
```

## Production Setup

### 1. Environment Configuration
Create your environment file by copying the example:
```bash
cp .env.example .env
```

Edit the `.env` file with your production configuration values:
```bash
vim .env
```

### 2. Build and Run
Build and start the production containers:
```bash
docker compose -f prod.compose.yml up --build -d
```

## Important Notes

- Always ensure your `.env` file contains the correct configuration for your environment
- Never commit the `.env` file to version control
- The production setup uses a separate Docker Compose file (`prod.compose.yml`) optimized for production use
- Make sure all required ports specified in your Docker configuration are available
- Back up any important data before running production deployments

## Troubleshooting

If you encounter issues:
1. Check if all prerequisites are properly installed
2. Verify your `.env` configuration
3. Ensure all required ports are available
4. Check Docker logs if services fail to start:
   ```bash
   docker compose logs
   ```

For production issues:
```bash
docker compose -f prod.compose.yml logs
```
