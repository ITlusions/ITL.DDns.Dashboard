# Use an official Python runtime based on Alpine as a parent image
FROM ghcr.io/astral-sh/uv:python3.12-alpine

#Set environment variables for Pydantic (optional for development)
#ENV DNS_DOMAIN=public.k8s.int.itlusions.com
#ENV DNS_NS_SERVER=ns1.public.k8s.int.itlusions.com
#ENV DNS_NS_SERVER_PORT=5354
#ENV DNS_KEY_NAME=externaldns
#ENV DNS_KEY_SECRET=

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./src /app
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN uv pip install --no-cache-dir -r requirements.txt --system

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]
