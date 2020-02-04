FROM python:2.7.16
RUN apt-get update
RUN apt-get install -y cron 
RUN apt-get install -y python-requests
WORKDIR /app
COPY . .
RUN chmod +x *
ENTRYPOINT /app/entrypoint.sh
