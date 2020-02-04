FROM python:2.7.16
RUN apt-get update && apt-get install -y cron
RUN pip install requests
WORKDIR /app
COPY . .
RUN chmod +x *
ENTRYPOINT /app/entrypoint.sh
