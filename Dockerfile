FROM python:3.9

WORKDIR /app

# Install Docker CLI
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update && apt-get install -y docker-ce-cli

# Install Nginx
RUN apt-get update && apt-get install -y nginx

# Install Python dependencies
RUN pip install fastapi==0.110.0 uvicorn==0.21.1 pydantic==2.6.4

COPY ./App /app

COPY nginx.conf /etc/nginx/nginx.conf

# Create a startup script
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Use the startup script as the entry point
ENTRYPOINT ["/startup.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]