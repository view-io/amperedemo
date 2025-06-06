FROM python:3.9-slim-buster

WORKDIR /app

# Install system dependencies and clean up in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    gnupg \
    lsb-release \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY ./App/requirements.txt ./App/nginx.conf /app/

# Install Python dependencies, Set execute permissions for startup script and move nginx config
RUN pip install --no-cache-dir -r requirements.txt && mv /app/nginx.conf /etc/nginx/nginx.conf

# Copy application files, configuration, and startup script
COPY ./App/startup.sh /
COPY ./App /app

# Make the files and directories readable and executable for the nginx server
RUN find /app/shared -type d -exec chmod 755 {} + && find /app/shared -type f -exec chmod 644 {} +

# Use the startup script as the entry point
ENTRYPOINT ["/startup.sh"]
#CMD ["tail", "-f", "/dev/null"]