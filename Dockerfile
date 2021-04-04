FROM python:3.7

# Create app directory
WORKDIR /app

# Install app dependencies
COPY src/requirements.txt ./

RUN pip install -r requirements.txt

# Copy app source
COPY src/server.py /app

EXPOSE 8080
CMD [ "python3", "server.py" ]