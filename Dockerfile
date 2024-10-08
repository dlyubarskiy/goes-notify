FROM python:3.11.10
RUN pip install requests python-telegram-bot
WORKDIR /app
COPY . .
RUN chmod +x *
ENTRYPOINT /app/entrypoint.sh
